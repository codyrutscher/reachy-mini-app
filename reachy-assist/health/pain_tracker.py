"""Pain tracking — detects pain mentions, asks follow-ups,
and saves structured pain reports to Supabase."""

import re
from core.log_config import get_logger

logger = get_logger("pain_tracker")


KEYWORDS = ["hurts", "pain", "aching", "sore", "throbbing", "stiff", "cramping", "burning", "tender", "swollen"]


def detect_pain(text) -> bool:
    lower = text.lower()
    for kw in KEYWORDS:
        if kw in lower:
            return True
    return False


def save_pain_report(location, severity, notes="", patient_id="default"):
    try:
        import memory.db_supabase as _db
        _db.save_pain_report(location, severity, notes, patient_id)
    except Exception as e:
        logger.error("Save error: %s", e)
