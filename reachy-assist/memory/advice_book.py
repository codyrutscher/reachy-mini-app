"""Advice Book — collects wisdom and advice the patient shares.

Detects when a patient shares life advice, wisdom, or lessons learned,
and saves them. Can be compiled into a "book" for family.
"""

import json
import os
import re
import time
from datetime import date
from core.log_config import get_logger

logger = get_logger("advice_book")

_WISDOM_TRIGGERS = [
    r"my advice (?:is|would be)",
    r"(?:the best|most important) thing i(?:'ve)? learned",
    r"if i could tell (?:young people|my younger self)",
    r"(?:the key|the secret) (?:to|is)",
    r"(?:always|never) forget (?:to|that)",
    r"what i(?:'ve)? learned (?:is|in life)",
    r"i always (?:say|tell)",
    r"my (?:mother|father|grandmother|grandfather) (?:always )?(?:said|told|used to say)",
    r"(?:one thing|something) i(?:'ve)? learned",
    r"(?:the trick|the thing) (?:is|about)",
    r"let me tell you (?:something|what)",
    r"(?:you know what|here's what) i(?:'ve)? (?:found|learned|realized)",
    r"life (?:taught|has taught) me",
]

_COMPILED = re.compile("|".join(_WISDOM_TRIGGERS), re.IGNORECASE)


def is_wisdom(text: str) -> bool:
    """Check if the text contains wisdom or advice."""
    return bool(_COMPILED.search(text))


def save_wisdom(text: str, patient_id: str = "default") -> None:
    """Save a piece of wisdom silently."""
    try:
        from memory import db_supabase as db
        if db.is_available():
            db._execute(
                "INSERT INTO advice_book (patient_id, content) VALUES (%s, %s)",
                (patient_id, text),
            )
            logger.info("Wisdom saved: %s", text[:50])
            return
    except Exception:
        pass

    path = os.path.join(os.path.dirname(__file__), "..", "advice_book.json")
    try:
        existing = []
        if os.path.exists(path):
            with open(path) as f:
                existing = json.load(f)
        existing.append({
            "patient_id": patient_id,
            "content": text,
            "date": date.today().isoformat(),
        })
        existing = existing[-200:]
        with open(path, "w") as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        logger.error("Failed to save wisdom: %s", e)


def get_wisdom(patient_id: str = "default", limit: int = 50) -> list[dict]:
    """Get collected wisdom entries."""
    try:
        from memory import db_supabase as db
        if db.is_available():
            rows = db._execute(
                "SELECT content, created_at FROM advice_book "
                "WHERE patient_id=%s ORDER BY created_at DESC LIMIT %s",
                (patient_id, limit), fetch=True,
            )
            if rows:
                return [{"content": r["content"], "date": str(r.get("created_at", ""))}
                        for r in rows]
    except Exception:
        pass

    path = os.path.join(os.path.dirname(__file__), "..", "advice_book.json")
    try:
        if os.path.exists(path):
            with open(path) as f:
                entries = json.load(f)
            return [{"content": e["content"], "date": e.get("date", "")}
                    for e in entries if e.get("patient_id") == patient_id][-limit:]
    except Exception:
        pass
    return []
