"""Holiday Awareness — knows what holiday it is and brings it up naturally.

Provides today's holiday (if any) for the brain to weave into conversation.
Covers major US/international holidays plus some fun ones.
"""

from datetime import date, timedelta
from core.log_config import get_logger

logger = get_logger("holidays")

# Fixed-date holidays: (month, day) -> name
_FIXED = {
    (1, 1): "New Year's Day",
    (2, 2): "Groundhog Day",
    (2, 14): "Valentine's Day",
    (3, 17): "St. Patrick's Day",
    (4, 1): "April Fools' Day",
    (4, 22): "Earth Day",
    (5, 5): "Cinco de Mayo",
    (6, 19): "Juneteenth",
    (7, 4): "Independence Day",
    (10, 31): "Halloween",
    (11, 11): "Veterans Day",
    (12, 24): "Christmas Eve",
    (12, 25): "Christmas Day",
    (12, 31): "New Year's Eve",
}


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Get the nth occurrence of a weekday in a month (1-indexed). weekday: 0=Mon."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Get the last occurrence of a weekday in a month."""
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    offset = (last_day.weekday() - weekday) % 7
    return last_day - timedelta(days=offset)


def _easter(year: int) -> date:
    """Compute Easter Sunday using the Anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _floating_holidays(year: int) -> dict[date, str]:
    """Compute floating holidays for a given year."""
    holidays = {}
    # MLK Day: 3rd Monday of January
    holidays[_nth_weekday(year, 1, 0, 3)] = "Martin Luther King Jr. Day"
    # Presidents' Day: 3rd Monday of February
    holidays[_nth_weekday(year, 2, 0, 3)] = "Presidents' Day"
    # Mother's Day: 2nd Sunday of May
    holidays[_nth_weekday(year, 5, 6, 2)] = "Mother's Day"
    # Memorial Day: last Monday of May
    holidays[_last_weekday(year, 5, 0)] = "Memorial Day"
    # Father's Day: 3rd Sunday of June
    holidays[_nth_weekday(year, 6, 6, 3)] = "Father's Day"
    # Labor Day: 1st Monday of September
    holidays[_nth_weekday(year, 9, 0, 1)] = "Labor Day"
    # Columbus Day: 2nd Monday of October
    holidays[_nth_weekday(year, 10, 0, 2)] = "Columbus Day"
    # Thanksgiving: 4th Thursday of November
    holidays[_nth_weekday(year, 11, 3, 4)] = "Thanksgiving"
    # Easter
    easter = _easter(year)
    holidays[easter] = "Easter Sunday"
    holidays[easter - timedelta(days=2)] = "Good Friday"
    return holidays


def get_today_holiday(today: date | None = None) -> str | None:
    """Return today's holiday name, or None if it's not a holiday."""
    today = today or date.today()
    # Check fixed holidays
    key = (today.month, today.day)
    if key in _FIXED:
        return _FIXED[key]
    # Check floating holidays
    floating = _floating_holidays(today.year)
    return floating.get(today)


def get_holiday_context(today: date | None = None) -> str:
    """Build a context string about today's holiday for the LLM."""
    holiday = get_today_holiday(today)
    if not holiday:
        return ""
    return f"Today is {holiday}. You might mention it naturally if it fits the conversation."


def get_upcoming_holidays(days: int = 14) -> list[tuple[date, str]]:
    """Get holidays in the next N days."""
    today = date.today()
    upcoming = []
    for d in range(days + 1):
        check = today + timedelta(days=d)
        h = get_today_holiday(check)
        if h:
            upcoming.append((check, h))
    return upcoming
