"""This Day in History — shares an interesting historical event from today's date.

Uses a curated set of events plus optional API/GPT lookup for variety.
"""

import os
import random
from datetime import date
from core.log_config import get_logger

logger = get_logger("this_day")

# Curated events: (month, day) -> list of events
_EVENTS = {
    (1, 1): ["The Euro currency was introduced in 1999."],
    (1, 20): ["The first US presidential inauguration was held in 1937."],
    (2, 12): ["Abraham Lincoln was born in 1809."],
    (2, 14): ["The first telephone patent was filed by Alexander Graham Bell in 1876."],
    (3, 14): ["Albert Einstein was born in 1879. It's also Pi Day!"],
    (4, 12): ["Yuri Gagarin became the first human in space in 1961."],
    (4, 15): ["Leonardo da Vinci was born in 1452."],
    (5, 5): ["Astronaut Alan Shepard became the first American in space in 1961."],
    (6, 6): ["D-Day: Allied forces landed in Normandy in 1944."],
    (7, 20): ["Neil Armstrong walked on the Moon in 1969."],
    (7, 4): ["The Declaration of Independence was adopted in 1776."],
    (8, 28): ["Martin Luther King Jr. gave his 'I Have a Dream' speech in 1963."],
    (9, 2): ["World War II officially ended in 1945."],
    (10, 29): ["The internet was born — the first ARPANET message was sent in 1969."],
    (11, 9): ["The Berlin Wall fell in 1989."],
    (12, 17): ["The Wright Brothers made their first flight in 1903."],
    (12, 25): ["Isaac Newton was born in 1642."],
}


def get_today_event(today: date | None = None) -> str | None:
    """Get a historical event for today's date. Returns None if nothing curated."""
    today = today or date.today()
    key = (today.month, today.day)
    events = _EVENTS.get(key)
    if events:
        return random.choice(events)
    return None


def get_today_event_gpt(today: date | None = None) -> str | None:
    """Use GPT to generate a 'this day in history' fact."""
    today = today or date.today()
    date_str = today.strftime("%B %d")

    try:
        from openai import OpenAI
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            return get_today_event(today)
        client = OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"Tell me one interesting historical event that happened on {date_str}. "
                           f"Keep it to one sentence, warm and conversational. "
                           f"Start with 'On this day in [year]...'",
            }],
            max_tokens=80,
            temperature=0.8,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return get_today_event(today)


def get_this_day_context(today: date | None = None) -> str:
    """Build context for the LLM about today in history."""
    event = get_today_event(today)
    if event:
        return f"Fun fact for today: {event} You could share this if the moment feels right."
    return ""
