"""Worry Jar — patient shares worries, Reachy "puts them in the jar"
and checks back later to see if they've resolved.

Detects worry/anxiety statements, saves them, and provides context
so the brain can follow up on past worries naturally.
"""

import json
import os
import random
import time
from datetime import date
from core.log_config import get_logger

logger = get_logger("worry_jar")

_WORRY_TRIGGERS = [
    "i'm worried", "i worry", "i'm anxious", "i'm nervous",
    "i'm scared", "i'm afraid", "what if", "i can't stop thinking",
    "it keeps me up", "i'm concerned", "i'm stressed",
    "that bothers me", "that scares me", "i dread",
]

_JAR_RESPONSES = [
    "I'm putting that worry in our worry jar. We can check on it later. For now, it's safe in there.",
    "Into the worry jar it goes. You don't have to carry it alone right now.",
    "I've got it. It's in the jar now. Let's give it some time and come back to it.",
    "Worry jar is holding that for you. Sometimes worries shrink when we set them down for a bit.",
    "That's in the jar now. We'll check on it together later, okay?",
]


def is_worry(text: str) -> bool:
    """Check if the text expresses a worry."""
    lower = text.lower()
    return any(t in lower for t in _WORRY_TRIGGERS)


def save_worry(text: str, patient_id: str = "default") -> str:
    """Save a worry and return a comforting response."""
    try:
        from memory import db_supabase as db
        if db.is_available():
            db._execute(
                "INSERT INTO worry_jar (patient_id, worry, resolved) VALUES (%s, %s, FALSE)",
                (patient_id, text),
            )
    except Exception:
        # Fallback
        path = os.path.join(os.path.dirname(__file__), "..", "worry_jar.json")
        try:
            existing = []
            if os.path.exists(path):
                with open(path) as f:
                    existing = json.load(f)
            existing.append({
                "patient_id": patient_id, "worry": text,
                "date": date.today().isoformat(), "resolved": False,
            })
            existing = existing[-100:]
            with open(path, "w") as f:
                json.dump(existing, f, indent=2)
        except Exception:
            pass

    logger.info("Worry saved for %s", patient_id)
    return random.choice(_JAR_RESPONSES)


def get_worries(patient_id: str = "default", unresolved_only: bool = True,
                limit: int = 20) -> list[dict]:
    """Get saved worries."""
    try:
        from memory import db_supabase as db
        if db.is_available():
            if unresolved_only:
                rows = db._execute(
                    "SELECT id, worry, created_at FROM worry_jar "
                    "WHERE patient_id=%s AND resolved=FALSE ORDER BY created_at DESC LIMIT %s",
                    (patient_id, limit), fetch=True,
                )
            else:
                rows = db._execute(
                    "SELECT id, worry, resolved, created_at FROM worry_jar "
                    "WHERE patient_id=%s ORDER BY created_at DESC LIMIT %s",
                    (patient_id, limit), fetch=True,
                )
            if rows:
                return [{"id": r.get("id"), "worry": r["worry"],
                         "resolved": r.get("resolved", False),
                         "date": str(r.get("created_at", ""))} for r in rows]
    except Exception:
        pass
    return []


def resolve_worry(worry_id: int) -> bool:
    """Mark a worry as resolved."""
    try:
        from memory import db_supabase as db
        if db.is_available():
            db._execute("UPDATE worry_jar SET resolved=TRUE WHERE id=%s", (worry_id,))
            return True
    except Exception:
        pass
    return False


def get_worry_context(patient_id: str = "default") -> str:
    """Build context about unresolved worries for the brain to follow up on."""
    worries = get_worries(patient_id, limit=3)
    if not worries:
        return ""
    parts = [w["worry"][:80] for w in worries]
    return "Patient's recent worries (check in gently if appropriate): " + " | ".join(parts)
