"""Sundowning detection — tracks evening confusion/agitation."""

_SUNDOWNING_KEYWORDS = [
    "confused", "don't understand", "what's happening",
    "who are you", "where am i", "i want to go home",
    "leave me alone", "go away", "stop it",
    "i don't know", "what day is it", "what time is it",
    "i'm scared", "something's wrong", "help me",
    "i don't like this", "who is that", "what is this",
    "i can't remember", "nothing makes sense",
]

def check_sundowning(text, hour):
    """Return True if text contains confusion keywords and it's after 4pm."""
    if hour < 16:
        return False
    lower = text.lower()
    for kw in _SUNDOWNING_KEYWORDS:
        if kw in lower:
            return True
    return False
