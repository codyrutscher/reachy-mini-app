"""Centralized logging configuration for Reachy Assist.

Usage in any module:
    from core.log_config import get_logger
    logger = get_logger(__name__)
    logger.info("Something happened")
    logger.warning("Watch out")
    logger.error("Something broke", exc_info=True)

Environment variables:
    LOG_LEVEL  — DEBUG, INFO, WARNING, ERROR (default: INFO)
    LOG_FILE   — path to log file (default: none, stdout only)
    LOG_JSON   — set to "1" for JSON-formatted logs (useful for production)
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
    """Console formatter with colors and the [MODULE] prefix style the codebase already uses."""

    COLORS = {
        logging.DEBUG: "\033[36m",     # cyan
        logging.INFO: "\033[32m",      # green
        logging.WARNING: "\033[33m",   # yellow
        logging.ERROR: "\033[31m",     # red
        logging.CRITICAL: "\033[1;31m",  # bold red
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, "")
        # Use the short module name as the tag, e.g. [ROBOT], [REALTIME]
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
        # Include any extra structured fields attached to the record
        for key in ("request_id", "method", "path", "status", "duration_ms",
                     "ip", "user", "error_count", "component"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def _setup():
    """Configure the root logger once."""
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(_JsonFormatter() if LOG_JSON else _ColorFormatter())
    root.addHandler(console)

    # Optional file handler
    if LOG_FILE:
        fh = logging.FileHandler(LOG_FILE)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(fh)

    # Quiet down noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Call from any module."""
    _setup()
    return logging.getLogger(name)
