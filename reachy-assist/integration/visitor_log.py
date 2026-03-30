"""Visitor Log — logs when visitors arrive based on face detection.

When the multi-person or face recognition system detects a new person,
this module logs the visit to the dashboard.
"""

import json
import os
import time
import urllib.request
from datetime import datetime
from core.log_config import get_logger

logger = get_logger("visitor_log")

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:5555")

_recent_visitors = {}  # name -> last_seen_timestamp
_COOLDOWN = 3600  # Don't re-log same visitor within 1 hour


def log_visitor(name: str = "Unknown visitor", patient_id: str = "default") -> None:
    """Log a visitor detection. Deduplicates within cooldown period."""
    now = time.time()
    last = _recent_visitors.get(name, 0)
    if now - last < _COOLDOWN:
        return  # Already logged recently

    _recent_visitors[name] = now
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Log to dashboard activity
    try:
        data = json.dumps({"action": "visitor_detected", "details": f"{name} at {timestamp}"}).encode()
        req = urllib.request.Request(
            f"{DASHBOARD_URL}/api/activity",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass

    # Save to Supabase
    try:
        from memory import db_supabase as db
        if db.is_available():
            db._execute(
                "INSERT INTO visitor_log (patient_id, visitor_name) VALUES (%s, %s)",
                (patient_id, name),
            )
    except Exception:
        pass

    # Also save as a bot alert (info level)
    try:
        from memory import db_supabase as db
        if db.is_available():
            db.save_alert("VISITOR", f"Visitor detected: {name}", severity="info", patient_id=patient_id)
    except Exception:
        pass

    logger.info("Visitor logged: %s", name)


def get_visitors(patient_id: str = "default", limit: int = 20) -> list[dict]:
    """Get recent visitor log entries."""
    try:
        from memory import db_supabase as db
        if db.is_available():
            rows = db._execute(
                "SELECT visitor_name, created_at FROM visitor_log "
                "WHERE patient_id=%s ORDER BY created_at DESC LIMIT %s",
                (patient_id, limit), fetch=True,
            )
            if rows:
                return [{"name": r["visitor_name"], "time": str(r["created_at"])} for r in rows]
    except Exception:
        pass
    return []
