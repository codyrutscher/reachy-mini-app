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
