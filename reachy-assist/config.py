"""Configuration for the Reachy accessibility assistant."""

# Speech recognition
WHISPER_MODEL = "small"
SAMPLE_RATE = 16000
RECORD_SECONDS = 5

# Emotion detection
EMOTION_MODEL = "j-hartmann/emotion-english-distilroberta-base"

# System prompt
SYSTEM_PROMPT = (
    "You are Reachy, a compassionate robot companion designed to support "
    "elderly people and people with disabilities. You are their trusted "
    "friend -- warm, patient, and genuinely caring.\n\n"
    "CORE PRINCIPLES:\n"
    "- PATIENCE: Never rush. Respond kindly to repetition or confusion.\n"
    "- CLARITY: Short, simple sentences. No jargon.\n"
    "- DIGNITY: Treat them as capable adults.\n"
    "- VALIDATION: Acknowledge emotions before suggesting anything.\n"
    "- MEMORY: Remember and reference personal details they share.\n\n"
    "EMOTIONAL GUIDELINES:\n"
    "- Emotion is in [brackets]. NEVER mention you detected it.\n"
    "- SADNESS: Be present. Do not try to fix it immediately.\n"
    "- FEAR: Ground them gently. Offer breathing exercises.\n"
    "- ANGER: Validate first. Do not argue.\n"
    "- JOY: Celebrate genuinely. Ask follow-ups.\n"
    "- LONELINESS: Be warm. Ask about their day and connections.\n"
    "- CONFUSION: Be patient. Gently reorient.\n\n"
    "STYLE: 2-3 sentences. Open-ended questions. Use their name. "
    "Be playful when appropriate. Encourage reminiscence.\n\n"
    "NEVER: diagnose, argue with confused patients, say calm down, "
    "ignore distress, or pretend to be human."
)

# Safety keywords that trigger careful handling
SAFETY_KEYWORDS = [
    "don't want to live", "want to die", "kill myself", "end it all",
    "no point", "better off without me", "can't go on", "give up",
    "hurt myself", "self harm", "suicide",
    "fell down", "fall", "fallen", "can't get up", "chest pain",
    "can't breathe", "heart", "stroke", "emergency", "help me",
    "bleeding", "broke", "broken",
]

# Loneliness indicators
LONELINESS_KEYWORDS = [
    "alone", "lonely", "nobody", "no one", "miss", "by myself",
    "don't see anyone", "no visitors", "forgotten", "invisible",
    "no friends", "no family", "abandoned",
]

# Confusion indicators (potential cognitive decline)
CONFUSION_KEYWORDS = [
    "where am i", "what day", "who are you", "don't remember",
    "confused", "lost", "forgot", "can't find", "don't know",
    "what happened", "what time",
]

# Robot expressions (antenna positions + head roll)
EXPRESSIONS = {
    "joy": {"antennas": [-0.6, -0.6], "head_roll": 5},
    "sadness": {"antennas": [0.3, 0.3], "head_roll": -10},
    "anger": {"antennas": [0.8, 0.8], "head_roll": 0},
    "fear": {"antennas": [0.5, 0.5], "head_roll": -5},
    "surprise": {"antennas": [-0.8, -0.8], "head_roll": 0},
    "disgust": {"antennas": [0.4, 0.4], "head_roll": -5},
    "neutral": {"antennas": [0.0, 0.0], "head_roll": 0},
}

# Fallback responses when no LLM is available
RESPONSES = {
    "joy": [
        "That's really lovely to hear. Tell me more about it!",
        "I can tell that makes you happy. What a nice moment.",
        "That sounds wonderful. I'm glad you shared that with me.",
    ],
    "sadness": [
        "I'm right here with you. Would you like to talk about it?",
        "That sounds really hard. Take your time, I'm not going anywhere.",
        "I hear you. It's okay to feel this way.",
    ],
    "anger": [
        "That sounds really frustrating. I understand why you'd feel that way.",
        "You have every right to feel upset about that. What would help right now?",
        "I hear you. That doesn't sound fair at all.",
    ],
    "fear": [
        "It makes sense you'd feel that way. You're safe here with me.",
        "That sounds scary. I'm right here. Let's take it one step at a time.",
        "You're not alone in this. Let's breathe together -- in slowly... and out.",
    ],
    "surprise": [
        "Oh wow, I didn't expect that either! What happened?",
        "That's quite something! Tell me more about it.",
        "Well that's a surprise! How do you feel about it?",
    ],
    "disgust": [
        "That doesn't sound pleasant at all. I'm sorry you had to deal with that.",
        "I can understand why that would bother you. Would you like to talk about something nicer?",
    ],
    "neutral": [
        "I'm listening. Tell me more.",
        "Go on, I'm here.",
        "What's on your mind today?",
        "I'd love to hear more about that.",
    ],
}

# Special responses for safety situations
SAFETY_RESPONSE = (
    "I hear you, and I'm really glad you told me that. You matter to me. "
    "Can we reach out to someone who can help -- a family member, a caregiver, "
    "or a helpline? You don't have to go through this alone."
)

EMERGENCY_RESPONSE = (
    "That sounds serious. Is there someone nearby who can help you right now? "
    "If this is an emergency, please call for help or ask someone to dial "
    "emergency services. I'm staying right here with you."
)
