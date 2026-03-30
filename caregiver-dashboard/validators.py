"""Input validation & sanitization helpers for the dashboard API."""

import html
import re
from functools import wraps
from typing import Any, Optional
from flask import request, jsonify, Response

# ── Limits ──────────────────────────────────────────────────────────

MAX_TEXT: int = 2000       # general text fields
MAX_SHORT: int = 200       # names, usernames, short strings
MAX_NOTE: int = 5000       # notes, reports
MAX_PASSWORD: int = 128
MIN_PASSWORD: int = 4


# ── Sanitization ────────────────────────────────────────────────────

def sanitize(value: Any, max_len: int = MAX_TEXT) -> Any:
    """Strip leading/trailing whitespace, escape HTML entities, enforce length."""
    if not isinstance(value, str):
        return value
    value = value.strip()
    value = html.escape(value, quote=True)
    return value[:max_len]


def sanitize_short(value: Any) -> Any:
    return sanitize(value, MAX_SHORT)


# ── Validation helpers ──────────────────────────────────────────────

def require_json() -> tuple[Optional[dict], Optional[tuple[Response, int]]]:
    """Return parsed JSON body or (error_response, 400)."""
    try:
        data = request.get_json(force=True)
        if not isinstance(data, dict):
            return None, (jsonify({"error": "Request body must be a JSON object"}), 400)
        return data, None
    except Exception:
        return None, (jsonify({"error": "Invalid JSON in request body"}), 400)


def require_fields(data: dict, *fields: str) -> Optional[tuple[Response, int]]:
    """Check that required fields are present and non-empty strings.
    Returns (None) on success or (error_response, 400) on failure."""
    missing = [f for f in fields if not data.get(f, "").strip()]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
    return None


def validate_time_format(value: str) -> bool:
    """Check HH:MM format."""
    return bool(re.match(r"^\d{2}:\d{2}$", value))


def validate_role(role: str) -> bool:
    return role in ("admin", "caregiver", "family")


def validate_username(username: str) -> bool:
    """Alphanumeric + underscore, 2-50 chars."""
    return bool(re.match(r"^[a-zA-Z0-9_]{2,50}$", username))


def validate_repeat(value: str) -> bool:
    return value in ("once", "daily", "weekdays", "weekly")


def validate_med_status(value: str) -> bool:
    return value in ("taken", "missed", "skipped", "late")


def validate_priority(value: str) -> bool:
    return value in ("normal", "high", "urgent", "low")


def validate_patient_type(value: str) -> bool:
    return value in ("elderly", "disabled", "pediatric", "general")


def validate_int_range(value: Any, low: int, high: int) -> bool:
    """Check that value is an int (or None) within range."""
    if value is None:
        return True
    try:
        v = int(value)
        return low <= v <= high
    except (TypeError, ValueError):
        return False


def validate_float_range(value: Any, low: float, high: float) -> bool:
    if value is None:
        return True
    try:
        v = float(value)
        return low <= v <= high
    except (TypeError, ValueError):
        return False


# ── Rate limiting (in-memory, per-IP) ──────────────────────────────

import time
import threading

_login_attempts: dict[str, list[float]] = {}  # ip -> [(timestamp, ...)]
_lock: threading.Lock = threading.Lock()
LOGIN_WINDOW: int = 300    # 5 minutes
LOGIN_MAX: int = 10        # max attempts per window


def check_login_rate_limit(ip: str) -> bool:
    """Returns True if the IP is rate-limited."""
    now = time.time()
    with _lock:
        attempts = _login_attempts.get(ip, [])
        # Prune old attempts
        attempts = [t for t in attempts if now - t < LOGIN_WINDOW]
        _login_attempts[ip] = attempts
        if len(attempts) >= LOGIN_MAX:
            return True
        attempts.append(now)
        _login_attempts[ip] = attempts
        return False
