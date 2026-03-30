"""Calendar and appointments tracker — stores upcoming events
and reminds the patient about them."""

import json
import os
import urllib.request
from datetime import datetime

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:5555")

# In-memory store (also synced to dashboard activity log)
_appointments = []


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


def add_appointment(description: str, date_str: str = "", time_str: str = "") -> str:
    """Add an appointment."""
    apt = {
        "description": description,
        "date": date_str or "TBD",
        "time": time_str or "TBD",
        "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    _appointments.append(apt)
    _post("/api/activity", {
        "action": "appointment_added",
        "details": f"{description} on {apt['date']} at {apt['time']}",
    })
    return (
        f"Got it! I've added: {description}"
        + (f" on {date_str}" if date_str else "")
        + (f" at {time_str}" if time_str else "")
        + ". I'll remind you when it's coming up."
    )


def list_appointments() -> str:
    """List all upcoming appointments."""
    if not _appointments:
        return "You don't have any appointments scheduled. Say 'add appointment' to create one."
    lines = ["Here are your upcoming appointments:"]
    for i, apt in enumerate(_appointments, 1):
        lines.append(f"{i}. {apt['description']} — {apt['date']} at {apt['time']}")
    return "\n".join(lines)


def check_today() -> list[str]:
    """Check if any appointments are today. Returns list of reminders."""
    today = datetime.now().strftime("%Y-%m-%d")
    reminders = []
    for apt in _appointments:
        if apt["date"] == today:
            reminders.append(
                f"Reminder: You have {apt['description']} today at {apt['time']}."
            )
    return reminders


def parse_appointment(text: str) -> str:
    """Try to parse an appointment from natural language."""
    import re
    # Try to find a date
    date_patterns = [
        (r'(?:on\s+)?(\w+ \d{1,2})', None),  # "March 20"
        (r'(?:on\s+)?(\d{1,2}/\d{1,2})', None),  # "3/20"
        (r'(today|tomorrow|next week)', None),
    ]
    date_str = ""
    for pattern, _ in date_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            date_str = m.group(1)
            break

    # Try to find a time
    time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))', text, re.IGNORECASE)
    time_str = time_match.group(1) if time_match else ""

    # Remove date/time to get description
    desc = text
    for pattern, _ in date_patterns:
        desc = re.sub(pattern, "", desc, flags=re.IGNORECASE)
    if time_match:
        desc = desc.replace(time_match.group(0), "")
    # Clean up
    for word in ["appointment", "schedule", "add", "on", "at", "i have", "i have a"]:
        desc = re.sub(rf'\b{word}\b', '', desc, flags=re.IGNORECASE)
    desc = " ".join(desc.split()).strip(" .,!")
    if not desc:
        desc = "Appointment"

    return add_appointment(desc, date_str, time_str)
