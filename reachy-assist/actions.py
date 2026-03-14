"""Actions Reachy can perform — gestures, routines, and knowledge lookups."""

import time


# ── Knowledge base: things Reachy "knows" ──────────────────────────
KNOWLEDGE = {
    "name": "My name is Reachy! I'm a small robot made by Pollen Robotics.",
    "creator": "I was made by Pollen Robotics, a company in France.",
    "purpose": (
        "I'm here to help and keep you company. I can chat, do breathing "
        "exercises, dance, tell jokes, and more!"
    ),
    "help": (
        "You can ask me to: do a breathing exercise, dance, tell a joke, "
        "nod yes, shake no, or just chat with me about anything."
    ),
    "emergency": (
        "If this is an emergency, please call for a caregiver or dial "
        "emergency services right away. I'll stay with you."
    ),
}

# ── Jokes ───────────────────────────────────────────────────────────
JOKES = [
    "Why do robots never get scared? Because they have nerves of steel!",
    "What do you call a robot that always takes the longest route? R2-Detour!",
    "I told my robot friend a joke. It didn't laugh. Turns out it had a dry sense of humor.",
    "Why did the robot go on vacation? To recharge its batteries!",
    "What's a robot's favorite type of music? Heavy metal!",
]

_joke_index = 0


def _next_joke() -> str:
    global _joke_index
    joke = JOKES[_joke_index % len(JOKES)]
    _joke_index += 1
    return joke
