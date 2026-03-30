"""Joke teller — Reachy tells clean, family-friendly jokes."""

import random

JOKES = [
    ("Why don't scientists trust atoms?", "Because they make up everything!"),
    ("What do you call a bear with no teeth?", "A gummy bear!"),
    ("Why did the scarecrow win an award?", "Because he was outstanding in his field!"),
    ("What do you call a fake noodle?", "An impasta!"),
    ("Why couldn't the bicycle stand up by itself?", "Because it was two-tired!"),
    ("What did the ocean say to the beach?", "Nothing, it just waved."),
    ("Why do cows have hooves instead of feet?", "Because they lactose!"),
    ("What do you call a dog that does magic tricks?", "A Labracadabrador!"),
    ("Why did the math book look so sad?", "Because it had too many problems."),
    ("What do you call a sleeping dinosaur?", "A dino-snore!"),
    ("Why don't eggs tell jokes?", "They'd crack each other up!"),
    ("What did one wall say to the other wall?", "I'll meet you at the corner!"),
    ("Why did the cookie go to the hospital?", "Because it felt crummy."),
    ("What do you call a fish without eyes?", "A fsh!"),
    ("Why can't you give Elsa a balloon?", "Because she will let it go!"),
    ("What did the left eye say to the right eye?", "Between us, something smells!"),
    ("Why do bananas have to put on sunscreen?", "Because they might peel!"),
    ("What do you call a boomerang that won't come back?", "A stick."),
    ("Why was the math teacher late?", "She took the rhombus."),
    ("What do you call a lazy kangaroo?", "A pouch potato!"),
    ("Why did the golfer bring two pairs of pants?", "In case he got a hole in one!"),
    ("What do you call a snowman with a six-pack?", "An abdominal snowman!"),
    ("Why don't skeletons fight each other?", "They don't have the guts."),
    ("What did the grape do when it got stepped on?", "Nothing, it just let out a little wine."),
    ("How does a penguin build its house?", "Igloos it together!"),
]

_told = []

def tell_joke() -> str:
    """Return a joke. Avoids repeats until all have been told."""
    global _told
    available = [j for j in JOKES if j not in _told]
    if not available:
        _told = []
        available = JOKES
    joke = random.choice(available)
    _told.append(joke)
    setup, punchline = joke
    return f"{setup}\n\n... {punchline}"


def tell_joke_setup_punchline() -> tuple[str, str]:
    """Return (setup, punchline) separately for dramatic timing."""
    global _told
    available = [j for j in JOKES if j not in _told]
    if not available:
        _told = []
        available = JOKES
    joke = random.choice(available)
    _told.append(joke)
    return joke


def get_joke_count() -> int:
    """Return how many jokes have been told."""
    return len(_told)


def reset_jokes():
    """Clear the told list so all jokes are available again."""
    global _told
    _told = []


# ── Patient joke memory ──────────────────────────────────────────

_patient_jokes = []  # jokes the patient has told us

_JOKE_INDICATORS = [
    "want to hear a joke", "here's a joke", "knock knock",
    "have you heard this one", "a man walks into", "why did the",
    "what do you call", "what's the difference between",
    "how many", "did you hear about", "so a guy walks",
    "let me tell you a joke", "i've got a joke", "here's a good one",
    "you'll love this one", "stop me if you've heard this",
]

_LAUGH_RESPONSES = [
    "Ha! That's a good one! I'm going to remember that.",
    "Oh that's wonderful! You really got me with that one.",
    "I love it! You should do stand-up comedy.",
    "That made me laugh! Tell me another one sometime.",
    "Ha ha! That's brilliant. I'll have to remember that.",
    "Oh my, that's funny! You always know how to make me smile.",
    "That's hilarious! Where did you hear that one?",
    "You crack me up! That's going in my favorites.",
]


def is_patient_joke(text: str) -> bool:
    """Check if the patient is telling a joke."""
    lower = text.lower()
    return any(t in lower for t in _JOKE_INDICATORS)


def remember_patient_joke(text: str, patient_id: str = "default") -> str:
    """Save a joke the patient told and return a laugh response."""
    _patient_jokes.append(text)

    # Persist to Supabase
    try:
        from memory import db_supabase as db
        if db.is_available():
            db._execute(
                "INSERT INTO patient_jokes (patient_id, joke_text) VALUES (%s, %s)",
                (patient_id, text),
            )
    except Exception:
        pass

    return random.choice(_LAUGH_RESPONSES)


def get_patient_jokes(patient_id: str = "default", limit: int = 50) -> list[str]:
    """Get jokes the patient has told (so we never repeat them back)."""
    try:
        from memory import db_supabase as db
        if db.is_available():
            rows = db._execute(
                "SELECT joke_text FROM patient_jokes WHERE patient_id=%s ORDER BY created_at DESC LIMIT %s",
                (patient_id, limit), fetch=True,
            )
            if rows:
                return [r["joke_text"] for r in rows]
    except Exception:
        pass
    return list(_patient_jokes[-limit:])


def is_patient_joke_repeat(joke_text: str, patient_id: str = "default") -> bool:
    """Check if a joke we're about to tell is one the patient already told us."""
    patient_jokes = get_patient_jokes(patient_id)
    lower = joke_text.lower()
    return any(lower in pj.lower() or pj.lower() in lower for pj in patient_jokes)
