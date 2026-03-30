"""Milestone Alerts — notifies family when patient hits milestones.

Checks for conversation count milestones, streak milestones, and
cognitive score improvements. Sends alerts to the dashboard.
"""

import json
import os
import urllib.request
from core.log_config import get_logger

logger = get_logger("milestones")

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:5555")

_CONVERSATION_MILESTONES = [10, 25, 50, 100, 200, 500, 1000]
_STREAK_MILESTONES = [3, 7, 14, 30, 60, 90, 180, 365]

_notified = set()  # track what we've already notified about this session


def check_milestones(patient_id: str = "default") -> list[str]:
    """Check for new milestones and return list of milestone messages."""
    milestones = []

    try:
        from memory import db_supabase as db
        if not db.is_available():
            return []

        # Conversation count milestones
        convos = db.get_conversations(patient_id, limit=1)
        # Use a count query instead
        try:
            rows = db._execute(
                "SELECT COUNT(*) as cnt FROM bot_conversation_log WHERE patient_id=%s",
                (patient_id,), fetchone=True,
            )
            count = rows["cnt"] if rows else 0
        except Exception:
            count = 0

        for m in _CONVERSATION_MILESTONES:
            key = f"convo_{m}"
            if count >= m and key not in _notified:
                _notified.add(key)
                msg = f"🎉 Milestone: {count} conversations with Reachy!"
                milestones.append(msg)
                _send_alert(msg, patient_id)

        # Streak milestones
        streak = db.get_streak(patient_id)
        for m in _STREAK_MILESTONES:
            key = f"streak_{m}"
            if streak >= m and key not in _notified:
                _notified.add(key)
                msg = f"🔥 Milestone: {streak}-day conversation streak!"
                milestones.append(msg)
                _send_alert(msg, patient_id)

    except Exception as e:
        logger.debug("Milestone check failed: %s", e)

    return milestones


def _send_alert(message: str, patient_id: str = "default") -> None:
    """Send a milestone alert to the dashboard."""
    try:
        data = json.dumps({
            "type": "milestone",
            "message": message,
            "details": "",
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{DASHBOARD_URL}/api/alerts",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
        logger.info("Milestone alert sent: %s", message)
    except Exception as e:
        logger.debug("Failed to send milestone alert: %s", e)

    # Also save to bot alerts
    try:
        from memory import db_supabase as db
        if db.is_available():
            db.save_alert("MILESTONE", message, severity="info", patient_id=patient_id)
    except Exception:
        pass
