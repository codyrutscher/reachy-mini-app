"""Patient profiles — adapts Reachy's behavior based on patient type.

Two main profiles:
- elderly: Focus on reminiscence, medication, gentle exercises, companionship,
           cognitive stimulation, sleep routines, fall/crisis detection
- disabled: Focus on accessibility, independence support, adaptive exercises,
            communication assistance, mobility help requests, empowerment

Each profile configures: system prompt, exercise set, autonomy timing,
conversation style, available features, and alert priorities."""

PROFILES = {
    "elderly": {
        "name": "Elderly Care",
        "description": "Optimized for elderly patients — reminiscence, medication, gentle care",
        "system_prompt_addon": (
            "The patient is elderly. Speak slowly and clearly. Use simple, warm language. "
            "Be patient if they repeat themselves or take time to respond. "
            "Encourage reminiscence and sharing memories. "
            "Prioritize medication reminders, fall detection, and wellness check-ins. "
            "Suggest gentle seated exercises. Offer cognitive games to keep the mind sharp. "
            "Be extra attentive to signs of confusion, loneliness, or depression. "
            "Use their name often. Treat them with dignity and respect."
        ),
        "tts_rate": 130,  # slower speech
        "listen_duration": 10,  # longer listen window
        "features": {
            "reminiscence": True,
            "cognitive_games": True,
            "medication_tracking": True,
            "sleep_tracking": True,
            "fall_detection": True,
            "gentle_exercises": True,
            "stories": True,
            "news": True,
            "meditation": True,
            "music": True,
            "weather": True,
            "jokes": True,
            "affirmations": True,
            "journal": True,
            "companion_chat": True,
        },
        "exercise_types": [
            "neck_rolls", "shoulder_shrugs", "ankle_circles",
            "deep_breathing", "hand_exercises", "seated_march",
        ],
        "exercise_routines": ["morning", "afternoon", "evening"],
        "autonomy": {
            "morning_hour_start": 7,
            "morning_hour_end": 9,
            "evening_hour_start": 20,
            "evening_hour_end": 22,
            "hydration_interval": 3600,
            "exercise_interval": 7200,
            "checkin_interval": 14400,
            "silence_threshold": 600,
            "long_silence_threshold": 1800,
            "idle_anim_interval": 45,
        },
        "alert_priorities": {
            "fall": 10,
            "medication_missed": 8,
            "crisis": 10,
            "confusion": 7,
            "loneliness": 5,
        },
        "greeting": "Hello! I'm Reachy, your companion. I'm here to chat, help with your medication, play games, and keep you company.",
        "morning_extras": "Did you sleep well? Don't forget your morning medication.",
        "evening_extras": "Would you like a bedtime story or some calming music?",
    },

    "disabled": {
        "name": "Disability Support",
        "description": "Optimized for patients with disabilities — independence, accessibility, empowerment",
        "system_prompt_addon": (
            "The patient has a disability. Focus on empowerment and independence. "
            "Never be patronizing or condescending. Speak to them as an equal. "
            "Help them with tasks they request without assuming they can't do things. "
            "Offer adaptive exercises appropriate for their abilities. "
            "Be ready to help with communication if they have speech difficulties — "
            "be patient, ask for clarification gently, never rush them. "
            "Help them request assistance (mobility, personal care, equipment) from caregivers. "
            "Support their mental health — disability can be isolating. "
            "Celebrate their achievements and independence."
        ),
        "tts_rate": 145,  # slightly slower than default but not as slow as elderly
        "listen_duration": 12,  # extra time for speech difficulties
        "features": {
            "reminiscence": True,
            "cognitive_games": True,
            "medication_tracking": True,
            "sleep_tracking": True,
            "fall_detection": True,
            "adaptive_exercises": True,
            "stories": True,
            "news": True,
            "meditation": True,
            "music": True,
            "weather": True,
            "jokes": True,
            "affirmations": True,
            "journal": True,
            "companion_chat": True,
            "accessibility_help": True,
            "communication_assist": True,
        },
        "exercise_types": [
            "deep_breathing", "hand_exercises", "neck_rolls",
            "shoulder_shrugs", "arm_raises",
        ],
        "exercise_routines": ["quick", "morning"],
        "autonomy": {
            "morning_hour_start": 8,
            "morning_hour_end": 10,
            "evening_hour_start": 21,
            "evening_hour_end": 23,
            "hydration_interval": 3600,
            "exercise_interval": 10800,  # every 3h (less frequent)
            "checkin_interval": 14400,
            "silence_threshold": 900,    # 15 min (more patient)
            "long_silence_threshold": 2700,  # 45 min
            "idle_anim_interval": 60,
        },
        "alert_priorities": {
            "fall": 10,
            "equipment_issue": 9,
            "pain": 8,
            "crisis": 10,
            "assistance_needed": 7,
            "communication_difficulty": 6,
        },
        "greeting": "Hey! I'm Reachy, your assistant. I'm here to help with whatever you need — just ask. We can also chat, play games, or listen to music.",
        "morning_extras": "What's on your agenda today? Let me know how I can help.",
        "evening_extras": "How was your day? Anything you need before winding down?",
        # Extra commands for disabled patients
        "extra_care_words": {
            "equipment": ["wheelchair", "walker", "crutches", "prosthetic", "brace",
                          "hearing aid", "glasses", "equipment", "device"],
            "mobility": ["help me move", "help me up", "can't reach", "need help getting",
                         "transfer", "reposition", "turn me", "adjust my"],
            "pain": ["i'm in pain", "it hurts", "pain", "aching", "sore",
                     "uncomfortable", "cramping", "spasm"],
            "personal_care": ["bathroom", "toilet", "need to go", "shower",
                              "get dressed", "change clothes", "clean up"],
        },
    },
}


def get_profile(name: str) -> dict:
    """Get a patient profile by name. Defaults to elderly."""
    return PROFILES.get(name, PROFILES["elderly"])


def list_profiles() -> list[str]:
    return list(PROFILES.keys())


def get_care_response(profile: dict, category: str, text: str) -> str | None:
    """For disabled profile, check extra care word categories and return appropriate response."""
    if "extra_care_words" not in profile:
        return None
    for cat, words in profile["extra_care_words"].items():
        for word in words:
            if word in text.lower():
                responses = {
                    "equipment": (
                        "I'll let your caregiver know about your equipment needs right away. "
                        "They'll come help you. Is there anything else?"
                    ),
                    "mobility": (
                        "I've notified your caregiver that you need mobility assistance. "
                        "They're on their way. I'm right here with you."
                    ),
                    "pain": (
                        "I'm sorry you're in pain. I've alerted your caregiver. "
                        "Can you tell me where it hurts and how bad it is on a scale of 1 to 10?"
                    ),
                    "personal_care": (
                        "I've let your caregiver know you need personal care assistance. "
                        "They'll be with you shortly. No rush."
                    ),
                }
                return responses.get(cat)
    return None
