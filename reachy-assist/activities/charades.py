"""Emotion Charades — Reachy acts out emotions, patient guesses.

Reachy performs an emotion using body language (head tilt, antenna position,
movements) and the patient tries to guess what emotion it is. Then they
can switch — patient acts out an emotion and Reachy guesses using the camera.
"""

import logging
import random
import threading
import time

logger = logging.getLogger(__name__)

EMOTIONS = {
    "happy": {
        "action": "celebrate",
        "hints": ["I'm feeling really good", "Something wonderful happened", "This is the best day"],
    },
    "sad": {
        "action": "empathy",
        "hints": ["I'm feeling down", "Something made me blue", "I need a hug"],
    },
    "excited": {
        "action": "excited",
        "hints": ["I can barely contain myself", "Something amazing is about to happen", "I'm buzzing"],
    },
    "scared": {
        "action": "worried",
        "hints": ["Something startled me", "I heard a strange noise", "I'm a bit nervous"],
    },
    "surprised": {
        "action": "surprised",
        "hints": ["I didn't expect that", "Whoa, what just happened", "I can't believe it"],
    },
    "curious": {
        "action": "curious",
        "hints": ["I wonder what that is", "Something caught my attention", "Tell me more"],
    },
    "sleepy": {
        "action": "sleepy",
        "hints": ["I could use a nap", "My eyes are getting heavy", "It's been a long day"],
    },
    "proud": {
        "action": "proud",
        "hints": ["I did something great", "Look what I accomplished", "I'm standing tall"],
    },
    "silly": {
        "action": "wiggle",
        "hints": ["I'm being goofy", "I can't stop being playful", "Everything is funny right now"],
    },
    "thinking": {
        "action": "think",
        "hints": ["I'm pondering something", "Let me figure this out", "Hmm, interesting question"],
    },
}


class EmotionCharades:
    """Emotion guessing game with Reachy's body language."""

    def __init__(self, robot=None, sound_effects=None):
        self._robot = robot
        self._sfx = sound_effects
        self._active = False
        self._current_emotion = ""
        self._score = 0
        self._rounds = 0
        self._max_rounds = 8
        self._used = []
        self._hints_given = 0
        self._mode = "reachy_acts"  # or "patient_acts"

    def start(self, mode: str = "reachy_acts") -> str:
        self._active = True
        self._score = 0
        self._rounds = 0
        self._used = []
        self._mode = mode
        if mode == "reachy_acts":
            return self._next_round()
        else:
            return (
                "Your turn to act! Show me an emotion with your face and body. "
                "I'll try to guess what you're feeling. Ready? Go!"
            )

    def _next_round(self) -> str:
        available = [e for e in EMOTIONS if e not in self._used]
        if not available or self._rounds >= self._max_rounds:
            return self.end()

        emotion = random.choice(available)
        self._used.append(emotion)
        self._current_emotion = emotion
        self._rounds += 1
        self._hints_given = 0

        # Perform the emotion
        if self._robot:
            action = EMOTIONS[emotion]["action"]
            threading.Thread(
                target=self._robot.perform, args=(action,), daemon=True
            ).start()

        return (
            f"Round {self._rounds}! Watch my body language carefully... "
            f"What emotion am I showing? Take your best guess!"
        )

    def check_guess(self, text: str) -> str:
        if not self._active or not self._current_emotion:
            return ""

        lower = text.lower()

        if any(p in lower for p in ["give up", "i don't know", "skip", "pass", "no idea"]):
            answer = self._current_emotion
            if self._sfx:
                self._sfx.play("whoops")
            result = f"It was '{answer}'! "
            if self._rounds >= self._max_rounds or len(self._used) >= len(EMOTIONS):
                return result + self.end()
            return result + self._next_round()

        if any(p in lower for p in ["hint", "clue", "help me"]):
            hints = EMOTIONS[self._current_emotion]["hints"]
            if self._hints_given < len(hints):
                hint = hints[self._hints_given]
                self._hints_given += 1
                # Re-perform the emotion
                if self._robot:
                    action = EMOTIONS[self._current_emotion]["action"]
                    threading.Thread(
                        target=self._robot.perform, args=(action,), daemon=True
                    ).start()
                return f"Here's a hint: '{hint}'. Watch me again..."
            return "No more hints! Take your best guess."

        if "again" in lower or "show me again" in lower or "one more time" in lower:
            if self._robot:
                action = EMOTIONS[self._current_emotion]["action"]
                threading.Thread(
                    target=self._robot.perform, args=(action,), daemon=True
                ).start()
            return "Watch carefully..."

        # Check answer
        if self._current_emotion in lower or any(
            syn in lower for syn in self._get_synonyms(self._current_emotion)
        ):
            self._score += 1
            if self._sfx:
                self._sfx.play("ding")
            result = f"Yes! I was showing '{self._current_emotion}'! Score: {self._score}/{self._rounds}. "
            if self._rounds >= self._max_rounds or len(self._used) >= len(EMOTIONS):
                return result + self.end()
            return result + self._next_round()

        if self._sfx:
            self._sfx.play("buzzer")
        return "Not quite! Try again, or say 'hint' for a clue."

    def end(self) -> str:
        self._active = False
        if self._rounds == 0:
            return "Game over!"
        pct = int(self._score / self._rounds * 100)
        if self._sfx:
            self._sfx.play("tada" if pct >= 60 else "goodbye")
        return (
            f"Game over! You got {self._score} out of {self._rounds} ({pct}%). "
            f"{'You really know your emotions!' if pct >= 75 else 'Great effort!' if pct >= 50 else 'Nice try!'}"
        )

    @property
    def is_active(self) -> bool:
        return self._active

    def _get_synonyms(self, emotion: str) -> list[str]:
        syns = {
            "happy": ["joy", "joyful", "cheerful", "glad", "delighted"],
            "sad": ["unhappy", "down", "blue", "upset", "gloomy"],
            "excited": ["thrilled", "pumped", "hyped", "enthusiastic"],
            "scared": ["afraid", "frightened", "nervous", "anxious", "fearful"],
            "surprised": ["shocked", "amazed", "astonished", "startled"],
            "curious": ["interested", "intrigued", "wondering", "nosy"],
            "sleepy": ["tired", "drowsy", "exhausted", "yawning"],
            "proud": ["accomplished", "confident", "triumphant"],
            "silly": ["goofy", "playful", "funny", "ridiculous"],
            "thinking": ["thoughtful", "pondering", "contemplating", "deep in thought"],
        }
        return syns.get(emotion, [])
