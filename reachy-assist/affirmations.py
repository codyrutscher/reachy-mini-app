"""Daily affirmations and motivational quotes — Reachy shares
uplifting messages to brighten the patient's day."""

import random
from datetime import datetime

AFFIRMATIONS = [
    "You are loved and valued, just as you are.",
    "Today is a new day full of possibilities.",
    "You have the strength to handle whatever comes your way.",
    "Your smile brightens the room.",
    "You matter more than you know.",
    "Every day is a gift, and you make the most of it.",
    "You are brave, kind, and wonderful.",
    "The world is better because you're in it.",
    "You deserve happiness and peace.",
    "Your life has touched so many people in beautiful ways.",
    "It's okay to take things one step at a time.",
    "You are never alone. People care about you deeply.",
    "Your wisdom and experience are treasures.",
    "Today, choose to be gentle with yourself.",
    "You've overcome so much already. You're stronger than you think.",
    "Every moment is a chance to feel joy.",
    "You bring light to the people around you.",
    "Rest when you need to. You've earned it.",
    "Your stories and memories are precious gifts.",
    "Tomorrow holds new adventures, but today is beautiful too.",
]

MOTIVATIONAL = [
    "The secret of getting ahead is getting started.",
    "Believe you can and you're halfway there.",
    "It does not matter how slowly you go as long as you do not stop.",
    "The best time to plant a tree was 20 years ago. The second best time is now.",
    "You are never too old to set another goal or to dream a new dream.",
    "Happiness is not something ready-made. It comes from your own actions.",
    "The only way to do great work is to love what you do.",
    "In the middle of difficulty lies opportunity.",
    "What lies behind us and what lies before us are tiny matters compared to what lies within us.",
    "Life is what happens when you're busy making other plans.",
]

GRATITUDE_PROMPTS = [
    "What's one thing you're grateful for today?",
    "Can you think of a happy memory from this week?",
    "Who is someone that makes you smile?",
    "What's something small that brought you joy recently?",
    "What's your favorite thing about today so far?",
]

_daily_affirmation = None
_daily_date = None


def get_daily_affirmation() -> str:
    """Get today's affirmation (same one all day)."""
    global _daily_affirmation, _daily_date
    today = datetime.now().strftime("%Y-%m-%d")
    if _daily_date != today:
        _daily_date = today
        _daily_affirmation = random.choice(AFFIRMATIONS)
    return _daily_affirmation


def get_affirmation() -> str:
    """Get a random affirmation."""
    return random.choice(AFFIRMATIONS)


def get_motivation() -> str:
    """Get a motivational quote."""
    return random.choice(MOTIVATIONAL)


def get_gratitude_prompt() -> str:
    """Get a gratitude reflection prompt."""
    return random.choice(GRATITUDE_PROMPTS)


def morning_affirmation() -> str:
    """Full morning affirmation with greeting."""
    aff = get_daily_affirmation()
    return f"Here's your affirmation for today: {aff}"
