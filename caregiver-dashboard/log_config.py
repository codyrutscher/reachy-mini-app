"""Centralized logging configuration for the Caregiver Dashboard.

Usage:
    from log_config import get_logger
    logger = get_logger(__name__)

Environment variables:
    LOG_LEVEL  — DEBUG, INFO, WARNING, ERROR (default: INFO)
    LOG_FILE   — path to log file (default: none, stdout only)
    LOG_JSON   — set to "1" for JSON-formatted logs
"""

import logging
import os
import sys
from datetime import datetime

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.environ.get("LOG_FILE", "")
LOG_JSON = os.environ.get("LOG_JSON", "") == "1"

_configured = False


class _ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[1;31m",
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, "")
        tag = record.name.split(".")[-1].upper()
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        msg = record.getMessage()
        base = f"{color}[{tag}] {ts} {msg}{self.RESET}"
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            base += f"\n{record.exc_text}"
        return base


class _JsonFormatter(logging.Formatter):
    """JSON log formatter for structured logging in production.
    Includes extra fields when attached to the record (e.g. request_id, duration_ms)."""

    def format(self, record):
        import json
        entry = {
            "ts": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "method", "path", "status", "duration_ms",
                     "ip", "user", "error_count", "component"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


import collections
import threading

# In-memory ring buffer for recent logs (viewable via /api/logs)
_LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "500"))
_log_buffer = collections.deque(maxlen=_LOG_BUFFER_SIZE)
_log_buffer_lock = threading.Lock()


class _BufferHandler(logging.Handler):
    """Stores recent log entries in a ring buffer for the /api/logs endpoint."""

    def emit(self, record):
        entry = {
            "ts": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "method", "path", "status", "duration_ms",
                     "ip", "user"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        if record.exc_info:
            entry["exception"] = self.format(record) if record.exc_text else logging.Formatter().formatException(record.exc_info)
        with _log_buffer_lock:
            _log_buffer.append(entry)


def get_recent_logs(limit=100, level=None, module=None):
    """Return recent log entries, optionally filtered by level or module."""
    with _log_buffer_lock:
        logs = list(_log_buffer)
    if level:
        logs = [l for l in logs if l["level"] == level.upper()]
    if module:
        logs = [l for l in logs if module.lower() in l["module"].lower()]
    return logs[-limit:]


def _setup():
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(_JsonFormatter() if LOG_JSON else _ColorFormatter())
    root.addHandler(console)

    # In-memory buffer for /api/logs
    root.addHandler(_BufferHandler())

    if LOG_FILE:
        fh = logging.FileHandler(LOG_FILE)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(fh)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    _setup()
    return logging.getLogger(name)
