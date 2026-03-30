"""Birthday Tracker — remembers family birthdays and reminds the patient.

Detects birthday mentions in conversation, saves them, and provides
upcoming birthday context to the brain for natural reminders.
"""

import json
import os
import re
from datetime import date, timedelta
from core.log_config import get_logger

logger = get_logger("birthday_tracker")

_BIRTHDAY_PATTERNS = [
    r"(\w+)(?:'s)? birthday is (?:on )?(\w+ \d+)",
    r"(\w+)(?:'s)? birthday (?:is )?(?:in |on )?(\w+)",
    r"(\w+) (?:was born|turns? \d+) (?:on |in )?(\w+ \d+)",
    r"(\w+)(?:'s)? born (?:on )?(\w+ \d+)",
]

_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def detect_birthday(text: str) -> tuple[str, str] | None:
    """Try to extract a (name, date_string) from text. Returns None if no birthday found."""
    lower = text.lower()
    if "birthday" not in lower and "born" not in lower and "turns" not in lower:
        return None

    for pattern in _BIRTHDAY_PATTERNS:
        m = re.search(pattern, lower)
        if m:
            name = m.group(1).strip().title()
            date_str = m.group(2).strip()
            if name.lower() in ("my", "the", "a", "our", "his", "her", "their"):
                continue
            return (name, date_str)
    return None


def _parse_date(date_str: str) -> tuple[int, int] | None:
    """Parse 'March 15' or 'march 15' into (month, day)."""
    parts = date_str.lower().split()
    if len(parts) >= 2:
        month_name = parts[0]
        month = _MONTH_MAP.get(month_name)
        try:
            day = int(parts[1].rstrip("stndrdth"))
        except ValueError:
            return None
        if month and 1 <= day <= 31:
            return (month, day)
    return None


def save_birthday(name: str, date_str: str, patient_id: str = "default") -> str:
    """Save a birthday. Returns acknowledgment."""
    parsed = _parse_date(date_str)
    month_day = f"{parsed[0]:02d}-{parsed[1]:02d}" if parsed else date_str

    try:
        from memory import db_supabase as db
        if db.is_available():
            db._execute(
                """INSERT INTO birthday_tracker (patient_id, person_name, birthday_date)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (patient_id, person_name)
                   DO UPDATE SET birthday_date = EXCLUDED.birthday_date""",
                (patient_id, name, month_day),
            )
            logger.info("Birthday saved: %s on %s", name, month_day)
            return ""
    except Exception:
        pass

    # Fallback
    path = os.path.join(os.path.dirname(__file__), "..", "birthdays.json")
    try:
        existing = {}
        if os.path.exists(path):
            with open(path) as f:
                existing = json.load(f)
        key = f"{patient_id}:{name}"
        existing[key] = {"name": name, "date": month_day, "patient_id": patient_id}
        with open(path, "w") as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        logger.error("Failed to save birthday: %s", e)

    return ""


def get_upcoming(patient_id: str = "default", days: int = 30) -> list[dict]:
    """Get birthdays coming up in the next N days."""
    today = date.today()
    results = []

    birthdays = _get_all(patient_id)
    for b in birthdays:
        parsed = _parse_date_from_stored(b["date"])
        if not parsed:
            continue
        month, day = parsed
        try:
            this_year = date(today.year, month, day)
        except ValueError:
            continue
        if this_year < today:
            this_year = date(today.year + 1, month, day)
        diff = (this_year - today).days
        if 0 <= diff <= days:
            results.append({"name": b["name"], "date": b["date"], "days_away": diff})

    results.sort(key=lambda x: x["days_away"])
    return results


def get_birthday_context(patient_id: str = "default") -> str:
    """Build context string about upcoming birthdays for the LLM."""
    upcoming = get_upcoming(patient_id, days=14)
    if not upcoming:
        return ""
    parts = []
    for b in upcoming[:3]:
        if b["days_away"] == 0:
            parts.append(f"Today is {b['name']}'s birthday!")
        elif b["days_away"] == 1:
            parts.append(f"Tomorrow is {b['name']}'s birthday.")
        else:
            parts.append(f"{b['name']}'s birthday is in {b['days_away']} days.")
    return "Upcoming birthdays: " + " ".join(parts)


def _parse_date_from_stored(stored: str) -> tuple[int, int] | None:
    """Parse stored format 'MM-DD' or 'month day'."""
    if "-" in stored and len(stored) <= 5:
        parts = stored.split("-")
        try:
            return (int(parts[0]), int(parts[1]))
        except ValueError:
            return None
    return _parse_date(stored)


def _get_all(patient_id: str) -> list[dict]:
    """Get all saved birthdays."""
    try:
        from memory import db_supabase as db
        if db.is_available():
            rows = db._execute(
                "SELECT person_name, birthday_date FROM birthday_tracker WHERE patient_id=%s",
                (patient_id,), fetch=True,
            )
            if rows:
                return [{"name": r["person_name"], "date": r["birthday_date"]} for r in rows]
    except Exception:
        pass

    path = os.path.join(os.path.dirname(__file__), "..", "birthdays.json")
    try:
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            return [v for v in data.values() if v.get("patient_id") == patient_id]
    except Exception:
        pass
    return []
