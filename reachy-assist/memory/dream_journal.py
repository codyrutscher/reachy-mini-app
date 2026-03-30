"""Dream Journal — detects when a patient describes a dream and logs it.

Dreams are stored with date, content, mood, and recurring themes.
The brain can reference past dreams in conversation.
"""

import json
import os
import re
import time
from datetime import date
from core.log_config import get_logger

logger = get_logger("dream_journal")

_DREAM_TRIGGERS = [
    "i had a dream", "i dreamed", "i dreamt", "last night i",
    "in my dream", "i was dreaming", "weird dream", "bad dream",
    "nightmare", "i keep dreaming", "dream about", "dreamed about",
    "woke up from a dream", "strangest dream",
]


def is_dream_mention(text: str) -> bool:
    """Check if the user is describing a dream."""
    lower = text.lower()
    return any(t in lower for t in _DREAM_TRIGGERS)


def log_dream(text: str, mood: str = "neutral", patient_id: str = "default") -> str:
    """Save a dream entry and return an acknowledgment."""
    entry = {
        "date": date.today().isoformat(),
        "content": text,
        "mood": mood,
        "logged_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Try Supabase
    try:
        from memory import db_supabase as db
        if db.is_available():
            db._execute(
                """INSERT INTO dream_journal (patient_id, dream_date, content, mood)
                   VALUES (%s, %s, %s, %s)""",
                (patient_id, entry["date"], text, mood),
            )
            logger.info("Dream logged for %s", patient_id)
            return "I've written that dream down in your dream journal. Dreams are fascinating."
    except Exception:
        pass

    # Fallback: local JSON
    path = os.path.join(os.path.dirname(__file__), "..", "dream_journal.json")
    try:
        existing = []
        if os.path.exists(path):
            with open(path) as f:
                existing = json.load(f)
        entry["patient_id"] = patient_id
        existing.append(entry)
        existing = existing[-100:]
        with open(path, "w") as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        logger.error("Failed to save dream locally: %s", e)

    return "I've written that dream down in your dream journal. Dreams are fascinating."


def get_dreams(patient_id: str = "default", limit: int = 20) -> list[dict]:
    """Get recent dream entries."""
    try:
        from memory import db_supabase as db
        if db.is_available():
            rows = db._execute(
                "SELECT dream_date, content, mood, created_at FROM dream_journal "
                "WHERE patient_id=%s ORDER BY dream_date DESC LIMIT %s",
                (patient_id, limit), fetch=True,
            )
            if rows:
                return [{"date": str(r["dream_date"]), "content": r["content"],
                         "mood": r.get("mood", "")} for r in rows]
    except Exception:
        pass

    # Fallback
    path = os.path.join(os.path.dirname(__file__), "..", "dream_journal.json")
    try:
        if os.path.exists(path):
            with open(path) as f:
                entries = json.load(f)
            return [e for e in entries if e.get("patient_id") == patient_id][-limit:]
    except Exception:
        pass
    return []


def get_dream_context(patient_id: str = "default") -> str:
    """Build a context string about recent dreams for the LLM."""
    dreams = get_dreams(patient_id, limit=5)
    if not dreams:
        return ""
    parts = []
    for d in dreams[:3]:
        parts.append(f"[{d['date']}] {d['content'][:100]}")
    return "Recent dreams: " + " | ".join(parts)
