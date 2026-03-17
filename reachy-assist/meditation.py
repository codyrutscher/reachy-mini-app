"""Guided meditation and mindfulness sessions."""

import random

SESSIONS = {
    "body_scan": {
        "name": "Body Scan",
        "duration": "5 minutes",
        "steps": [
            "Let's do a body scan meditation. Find a comfortable position and close your eyes.",
            "Take a deep breath in... and slowly let it out.",
            "Bring your attention to your feet. Notice any sensations there. Just observe, don't judge.",
            "Now move your attention up to your legs. Feel the weight of them. Let any tension melt away.",
            "Bring your awareness to your stomach and chest. Notice your breathing. In... and out.",
            "Now focus on your hands and arms. Let them feel heavy and relaxed.",
            "Move to your shoulders and neck. If there's tension, imagine it dissolving with each breath.",
            "Finally, bring attention to your face. Relax your jaw, your forehead, your eyes.",
            "Now feel your whole body at once. You are calm, you are safe, you are at peace.",
            "When you're ready, slowly open your eyes. How do you feel?",
        ],
    },
    "gratitude": {
        "name": "Gratitude Meditation",
        "duration": "4 minutes",
        "steps": [
            "Let's practice gratitude together. Close your eyes and take a slow breath.",
            "Think of one person you're grateful for. Picture their face. Feel the warmth.",
            "Now think of one place that makes you happy. Imagine yourself there right now.",
            "Think of one simple thing you enjoyed today. Maybe a meal, a sound, a feeling.",
            "Now think of something about yourself you appreciate. You have so many good qualities.",
            "Hold all of these grateful feelings together. Let them fill your heart.",
            "Take one more deep breath... and slowly open your eyes.",
            "Gratitude is a powerful thing. Thank you for sharing that moment with me.",
        ],
    },
    "peaceful_place": {
        "name": "Peaceful Place",
        "duration": "5 minutes",
        "steps": [
            "Let's visit your peaceful place. Close your eyes and breathe deeply.",
            "Imagine a place where you feel completely safe and happy. It could be real or imaginary.",
            "Look around this place. What do you see? Notice the colors, the light.",
            "What do you hear? Maybe birds singing, waves crashing, or gentle wind.",
            "What do you smell? Fresh flowers, ocean air, warm bread baking?",
            "Feel the ground beneath you. Is it soft grass, warm sand, a cozy chair?",
            "You are completely safe here. Nothing can bother you. Just peace.",
            "Stay here for a moment. Breathe it all in.",
            "This place is always here for you. Whenever you need it, just close your eyes.",
            "Slowly come back now. Open your eyes when you're ready. Welcome back.",
        ],
    },
    "loving_kindness": {
        "name": "Loving Kindness",
        "duration": "4 minutes",
        "steps": [
            "This is a loving kindness meditation. Get comfortable and close your eyes.",
            "First, send love to yourself. Say in your mind: May I be happy. May I be healthy. May I be at peace.",
            "Now think of someone you love. Send them the same wish: May you be happy. May you be healthy. May you be at peace.",
            "Think of someone you see often but don't know well. Send them kindness too.",
            "Now extend that love to everyone. All people, everywhere. May all beings be happy.",
            "Feel that warmth spreading from your heart outward, like ripples in a pond.",
            "Take a deep breath and hold onto that feeling of love and connection.",
            "Open your eyes when you're ready. You just made the world a little kinder.",
        ],
    },
    "quick_calm": {
        "name": "Quick Calm (2 min)",
        "duration": "2 minutes",
        "steps": [
            "Let's do a quick calming exercise. Just two minutes.",
            "Close your eyes. Breathe in for 4 counts... 1, 2, 3, 4.",
            "Hold for 4... 1, 2, 3, 4.",
            "Out for 6... 1, 2, 3, 4, 5, 6.",
            "Again. In... 1, 2, 3, 4. Hold... 1, 2, 3, 4. Out... 1, 2, 3, 4, 5, 6.",
            "One more time. In... hold... and out slowly.",
            "Open your eyes. You did great. Even two minutes of calm makes a difference.",
        ],
    },
}


class MeditationGuide:
    def __init__(self):
        self.active = False
        self._current = None
        self._step = 0

    @property
    def is_active(self):
        return self.active

    def list_sessions(self) -> str:
        lines = ["Here are the meditation sessions I can guide you through:"]
        for key, s in SESSIONS.items():
            lines.append(f"- {s['name']} ({s['duration']})")
        lines.append("\nJust say the name, or say 'meditate' for a random one.")
        return "\n".join(lines)

    def start(self, text: str = "") -> str:
        lower = text.lower() if text else ""
        chosen = None
        for key, s in SESSIONS.items():
            if s["name"].lower() in lower or key.replace("_", " ") in lower:
                chosen = key
                break
        if not chosen:
            chosen = random.choice(list(SESSIONS.keys()))
        s = SESSIONS[chosen]
        self.active = True
        self._current = chosen
        self._step = 1
        return f"Let's begin: {s['name']} ({s['duration']}).\n\n{s['steps'][0]}"

    def next_step(self) -> str:
        if not self.active or not self._current:
            return "No meditation in progress. Say 'meditate' to start."
        s = SESSIONS[self._current]
        if self._step >= len(s["steps"]):
            self.active = False
            return f"That completes our {s['name']} session. Namaste."
        text = s["steps"][self._step]
        self._step += 1
        return text

    def stop(self) -> str:
        self.active = False
        return "Okay, we'll stop here. Remember, even a little mindfulness goes a long way."

def get_session_names() -> list:
    return [s["name"] for s in SESSIONS.values()]
