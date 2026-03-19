"""Daily affirmations and motivational quotes — Reachy shares
uplifting messages to brighten the patient's day.

Context-aware: picks affirmations based on the patient's recent mood
from Supabase when available, falls back to random otherwise."""

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
    "I am enough, exactly as I am right now.",
    "My value isn't determined by my productivity.",
    "I bring something unique to every room I'm in.",
    "I can figure out hard things — I've done it before.",
    "Challenges are shaping me, not breaking me.",
    "Every step forward counts, no matter how small.",
    "I am becoming a better version of myself every day.",
    "My skills are real and they matter.",
    "I am capable of building things that make a difference.",
    "I trust my instincts and my problem-solving ability.",
    "I don't have to have everything figured out today.",
    "I am allowed to rest without guilt.",
    "I choose to focus on what I can control.",
    "Peace is available to me in this moment.",
    "I was made with intention and for a reason.",
    "My life has meaning beyond what I can see right now.",
    "I am not walking this road alone.",
]

# ── Mood-specific affirmations ──────────────────────────────────

_MOOD_AFFIRMATIONS = {
    "sadness": [
        "It's okay to feel sad. Your feelings are valid and they will pass.",
        "Even on hard days, you are still worthy of love and kindness.",
        "Tears are not weakness — they show how deeply you feel.",
        "You don't have to be strong all the time. I'm here with you.",
        "Gentle days are still good days. Be kind to yourself.",
        "The sun always comes back, even after the longest night.",
        "You are held and cared for, even when it doesn't feel that way.",
    ],
    "fear": [
        "You are safe right now, in this moment. Take a deep breath.",
        "Courage isn't the absence of fear — it's moving forward anyway.",
        "Whatever is worrying you, you don't have to face it alone.",
        "One breath at a time. You've got this.",
        "Fear is just a feeling, not a fact. You are okay.",
        "You've been through hard things before and made it through.",
    ],
    "anger": [
        "Your frustration makes sense. It's okay to feel this way.",
        "You have every right to your feelings. Let's take a breath together.",
        "Even when things are unfair, you handle them with grace.",
        "It's okay to be upset. What matters is that you're still here.",
        "Your feelings are heard. You don't have to carry this alone.",
    ],
    "joy": [
        "Your happiness is contagious — keep shining!",
        "What a wonderful mood you're in! You deserve every bit of it.",
        "Joy looks so good on you. Let's keep this energy going!",
        "You're glowing today. The world is brighter because of you.",
        "Celebrate this feeling — you've earned it!",
        "Your laughter is the best sound. Never stop.",
    ],
    "neutral": AFFIRMATIONS,  # fall back to the general pool
}

def _get_recent_dominant_mood(patient_id: str = "default") -> str:
    """Query the last few moods from Supabase and return the dominant one."""
    try:
        import db_supabase as _db
        if not _db.is_available():
            return "neutral"
        moods = _db.get_moods(patient_id, limit=5)
        if not moods:
            return "neutral"
        counts = {}
        for m in moods:
            mood = m.get("mood", "neutral")
            counts[mood] = counts.get(mood, 0) + 1
        return max(counts, key=counts.get)
    except Exception:
        return "neutral"

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

EVENING_REFLECTIONS = [
    "You did great today. Time to rest.",
    "The day is done. Let your mind be at peace.",
    "You deserve a good night's sleep.",
    "Tomorrow is a fresh start. Tonight, just relax.",
    "Close your eyes and let go of today's worries.",
    "You are safe, you are loved, you are enough.",
    "Rest well. You've earned it.",
]

_daily_affirmation = None
_daily_date = None

def evening_reflection() -> str:
    """Get a calming evening reflection."""
    return random.choice(EVENING_REFLECTIONS)

def get_daily_affirmation(patient_id: str = "default") -> str:
    """Get today's affirmation (same one all day), mood-aware."""
    global _daily_affirmation, _daily_date
    today = datetime.now().strftime("%Y-%m-%d")
    if _daily_date != today:
        _daily_date = today
        mood = _get_recent_dominant_mood(patient_id)
        pool = _MOOD_AFFIRMATIONS.get(mood, AFFIRMATIONS)
        _daily_affirmation = random.choice(pool)
    return _daily_affirmation


def get_affirmation(patient_id: str = "default") -> str:
    """Get a mood-aware random affirmation."""
    mood = _get_recent_dominant_mood(patient_id)
    pool = _MOOD_AFFIRMATIONS.get(mood, AFFIRMATIONS)
    return random.choice(pool)


def get_contextual_affirmation(patient_id: str = "default") -> str:
    """Get an affirmation with a mood-aware intro line."""
    mood = _get_recent_dominant_mood(patient_id)
    affirmation = random.choice(_MOOD_AFFIRMATIONS.get(mood, AFFIRMATIONS))
    intros = {
        "sadness": "I know things feel heavy right now. Here's something for you: ",
        "fear": "Take a breath with me. I want you to hear this: ",
        "anger": "I hear you. Before we go on, remember this: ",
        "joy": "You're in such a great mood! Here's one to match: ",
    }
    intro = intros.get(mood, "Here's something I want you to hear: ")
    return intro + affirmation


def get_motivation() -> str:
    """Get a motivational quote."""
    return random.choice(MOTIVATIONAL)


def get_gratitude_prompt() -> str:
    """Get a gratitude reflection prompt."""
    return random.choice(GRATITUDE_PROMPTS)


def morning_affirmation(patient_id: str = "default") -> str:
    """Full morning affirmation with greeting, mood-aware."""
    aff = get_daily_affirmation(patient_id)
    return f"Here's your affirmation for today: {aff}"



