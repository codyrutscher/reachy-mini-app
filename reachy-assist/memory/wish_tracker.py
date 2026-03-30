"""Wish List Tracker — captures "I wish..." statements and shares with family.

Detects wish-like statements in conversation, saves them, and makes them
available to the dashboard for family members to see and potentially fulfill.
"""

import json
import os
import re
import time
from datetime import date
from core.log_config import get_logger

logger = get_logger("wish_tracker")

_WISH_PATTERNS = [
    r"i wish i could (.+)",
    r"i wish (.+)",
    r"i'd love to (.+)",
    r"i would love to (.+)",
    r"if only i could (.+)",
    r"i've always wanted to (.+)",
    r"i want to (.+)",
    r"i hope i can (.+)",
    r"my dream is to (.+)",
    r"one day i'd like to (.+)",
    r"i really want to (.+)",
]


def detect_wish(text: str) -> str | None:
    """Extract a wish from user text. Returns the wish content or None."""
    lower = text.lower().strip()
    for pattern in _WISH_PATTERNS:
        m = re.search(pattern, lower)
        if m:
            wish = m.group(1).strip().rstrip(".")
            # Filter out very short or generic wishes
            if len(wish) > 5:
                return wish
    return None


def save_wish(wish: str, full_text: str = "", patient_id: str = "default") -> str:
    """Save a detected wish and return acknowledgment."""
    entry = {
        "date": date.today().isoformat(),
        "wish": wish,
        "full_text": full_text,
        "fulfilled": False,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    try:
        from memory import db_supabase as db
        if db.is_available():
            db._execute(
                """INSERT INTO wish_list (patient_id, wish, full_text)
                   VALUES (%s, %s, %s)""",
                (patient_id, wish, full_text),
            )
            logger.info("Wish saved: %s", wish[:50])
            return ""  # silent save, don't interrupt conversation
    except Exception:
        pass

    # Fallback: local JSON
    path = os.path.join(os.path.dirname(__file__), "..", "wish_list.json")
    try:
        existing = []
        if os.path.exists(path):
            with open(path) as f:
                existing = json.load(f)
        entry["patient_id"] = patient_id
        existing.append(entry)
        existing = existing[-200:]
        with open(path, "w") as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        logger.error("Failed to save wish locally: %s", e)

    return ""


def get_wishes(patient_id: str = "default", limit: int = 30) -> list[dict]:
    """Get saved wishes for a patient."""
    try:
        from memory import db_supabase as db
        if db.is_available():
            rows = db._execute(
                "SELECT wish, full_text, fulfilled, created_at FROM wish_list "
                "WHERE patient_id=%s ORDER BY created_at DESC LIMIT %s",
                (patient_id, limit), fetch=True,
            )
            if rows:
                return [{"wish": r["wish"], "full_text": r.get("full_text", ""),
                         "fulfilled": r.get("fulfilled", False),
                         "date": str(r.get("created_at", ""))} for r in rows]
    except Exception:
        pass

    path = os.path.join(os.path.dirname(__file__), "..", "wish_list.json")
    try:
        if os.path.exists(path):
            with open(path) as f:
                entries = json.load(f)
            return [e for e in entries if e.get("patient_id") == patient_id][-limit:]
    except Exception:
        pass
    return []


def fulfill_wish(wish_id: int) -> bool:
    """Mark a wish as fulfilled (called from dashboard)."""
    try:
        from memory import db_supabase as db
        if db.is_available():
            db._execute("UPDATE wish_list SET fulfilled=TRUE WHERE id=%s", (wish_id,))
            return True
    except Exception:
        pass
    return False
