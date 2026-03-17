"""Sleep tracking — logs bedtime and wake time, reports sleep quality."""

import json
import os
import urllib.request
from datetime import datetime, timedelta

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:5555")


def _post(endpoint, data):
    try:
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            f"{DASHBOARD_URL}{endpoint}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass


def log_bedtime() -> str:
    """Log when the patient goes to sleep."""
    now = datetime.now()
    _post("/api/activity", {
        "action": "sleep_bedtime",
        "details": f"Bedtime logged at {now.strftime('%I:%M %p')}",
    })
    try:
        import db_supabase as _db
        if _db.is_available():
            _db.save_sleep_event("bedtime")
    except Exception:
        pass
    hour = now.hour
    if hour < 20:
        comment = "That's a bit early, but rest is important!"
    elif hour < 22:
        comment = "Perfect bedtime! Getting good sleep is so important."
    elif hour < 24:
        comment = "Time to rest. Sweet dreams!"
    else:
        comment = "It's quite late! Try to get to bed earlier tomorrow."
    return f"I've noted your bedtime at {now.strftime('%I:%M %p')}. {comment} Goodnight! Sleep well."


def log_wake_time() -> str:
    """Log when the patient wakes up."""
    now = datetime.now()
    _post("/api/activity", {
        "action": "sleep_wake",
        "details": f"Wake time logged at {now.strftime('%I:%M %p')}",
    })
    try:
        import db_supabase as _db
        if _db.is_available():
            _db.save_sleep_event("wake")
    except Exception:
        pass
    hour = now.hour
    if hour < 6:
        comment = "You're up early! Did you sleep okay?"
    elif hour < 9:
        comment = "Good morning! That's a healthy wake-up time."
    else:
        comment = "Rise and shine! I hope you had a good rest."
    return f"Good morning! Wake time noted at {now.strftime('%I:%M %p')}. {comment}"


def sleep_report() -> str:
    """Give a simple sleep summary based on logged data."""
    return (
        "I've been tracking your sleep patterns. "
        "For the best health, try to go to bed before 10 PM and wake up around 7 AM. "
        "Consistent sleep helps with mood, memory, and overall wellbeing. "
        "Would you like me to remind you at bedtime?"
    )


def sleep_duration(bedtime: str, wake_time: str) -> str:
    """Calculate how long the patient slept.
    Times are in '%I:%M %p' format, e.g. '10:30 PM' and '7:15 AM'."""
    bed = datetime.strptime(bedtime, "%I:%M %p")
    wake = datetime.strptime(wake_time, "%I:%M %p")
    # if wake is earlier, they slept past midnight
    if wake <= bed:
        wake += timedelta(days=1)
    diff = wake - bed
    total_minutes = int(diff.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"You slept for {hours} hours and {minutes} minutes."
