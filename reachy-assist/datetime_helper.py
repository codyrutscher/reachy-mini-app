"""Date, time, and holiday awareness."""

from datetime import datetime, date

HOLIDAYS = {
    (1, 1): "New Year's Day",
    (2, 14): "Valentine's Day",
    (3, 17): "St. Patrick's Day",
    (4, 1): "April Fools' Day",
    (5, 5): "Cinco de Mayo",
    (7, 4): "Independence Day",
    (10, 31): "Halloween",
    (11, 11): "Veterans Day",
    (12, 24): "Christmas Eve",
    (12, 25): "Christmas Day",
    (12, 31): "New Year's Eve",
}


def get_time_response() -> str:
    now = datetime.now()
    time_str = now.strftime("%I:%M %p")
    return f"It's {time_str} right now."


def get_date_response() -> str:
    now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")
    holiday = HOLIDAYS.get((now.month, now.day))
    response = f"Today is {date_str}."
    if holiday:
        response += f" And it's {holiday}! 🎉"
    return response


def get_day_response() -> str:
    now = datetime.now()
    return f"Today is {now.strftime('%A')}."


def get_full_briefing() -> str:
    now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")
    time_str = now.strftime("%I:%M %p")
    holiday = HOLIDAYS.get((now.month, now.day))
    parts = [f"It's {time_str} on {date_str}."]
    if holiday:
        parts.append(f"Today is {holiday}!")
    # Time of day context
    hour = now.hour
    if hour < 6:
        parts.append("It's still very early. Are you having trouble sleeping?")
    elif hour < 12:
        parts.append("It's morning time.")
    elif hour < 17:
        parts.append("It's the afternoon.")
    elif hour < 21:
        parts.append("It's evening time.")
    else:
        parts.append("It's getting late. Are you ready for bed soon?")
    return " ".join(parts)
