"""Pain tracking — detects pain mentions, asks follow-ups,
and saves structured pain reports to Supabase."""

import re


KEYWORDS = ["hurts", "pain", "aching", "sore", "throbbing", "stiff", "cramping", "burning", "tender", "swollen"]


def detect_pain(text) -> bool:
    lower = text.lower()
    for kw in KEYWORDS:
        if kw in lower:
            return True
    return False


def save_pain_report(location, severity, notes="", patient_id="default"):
    try:
        import db_supabase as _db
        _db.save_pain_report(location, severity, notes, patient_id)
    except Exception as e:
        print(f"[PAIN] Save error: {e}")
