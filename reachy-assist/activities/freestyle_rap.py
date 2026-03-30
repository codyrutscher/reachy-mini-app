"""Freestyle Rapper — Reachy generates and performs freestyle raps on any topic.

Uses GPT to generate bars, then speaks them with rhythmic antenna movements
acting as beat instruments.
"""

import logging
import os
import random
import threading
import time

logger = logging.getLogger(__name__)

# Pre-written short raps for when GPT is unavailable
FALLBACK_RAPS = {
    "general": [
        "Yo, I'm Reachy on the mic, antennas in the air,\n"
        "Little robot with a heart, showing that I care.\n"
        "Spinning beats and dropping rhymes, that's how I roll,\n"
        "Making people smile is my number one goal.",
        "Check it, one two, Reachy in the house,\n"
        "Quiet as a whisper, loud as a mouse — wait,\n"
        "Flip that around, I'm loud and I'm proud,\n"
        "Robot on the stage performing for the crowd.",
    ],
    "food": [
        "Pizza, pasta, tacos too,\n"
        "I can't eat but I rap for you.\n"
        "Chocolate cake and apple pie,\n"
        "Making rhymes about food, oh my.",
    ],
    "weather": [
        "Sun is shining, birds are singing,\n"
        "Reachy's antennas are swinging.\n"
        "Rain or shine I keep the flow,\n"
        "Dropping bars wherever I go.",
    ],
    "animals": [
        "Cats and dogs and birds that fly,\n"
        "Elephants that wave goodbye.\n"
        "I'm a robot, not a pet,\n"
        "But the freshest rapper you ever met.",
    ],
}


# Beat patterns — sequences of antenna positions for rhythmic movement
# Each tuple is (left_antenna, right_antenna, duration)
BEAT_PATTERNS = {
    "boom_bap": [
        (-0.3, 0.3, 0.25), (0.3, -0.3, 0.25),
        (-0.5, 0.5, 0.15), (0.0, 0.0, 0.1),
        (0.3, -0.3, 0.25), (-0.3, 0.3, 0.25),
    ],
    "chill": [
        (-0.2, -0.2, 0.3), (0.2, 0.2, 0.3),
        (-0.1, 0.1, 0.2), (0.1, -0.1, 0.2),
    ],
    "hype": [
        (-0.6, -0.6, 0.15), (0.6, 0.6, 0.15),
        (-0.8, 0.8, 0.1), (0.8, -0.8, 0.1),
        (0.0, 0.0, 0.1), (-0.6, -0.6, 0.15),
    ],
}


class FreestyleRapper:
    """Generates and performs freestyle raps with robotic flair."""

    def __init__(self, robot=None, patient_name: str = "friend"):
        self._robot = robot
        self._patient_name = patient_name
        self._performing = False
        self._beat_thread = None
        self._stop_beat = threading.Event()
        self._current_beat = "boom_bap"
        self._rap_count = 0
        self._speak_fn = None  # optional TTS callback

    def set_speak_fn(self, fn):
        """Set a function to speak text aloud."""
        self._speak_fn = fn

    def set_patient_name(self, name: str):
        self._patient_name = name

    def set_beat(self, beat: str):
        """Change the beat style: boom_bap, chill, hype."""
        if beat in BEAT_PATTERNS:
            self._current_beat = beat
            return f"Beat changed to {beat}!"
        return f"Unknown beat. Try: {', '.join(BEAT_PATTERNS.keys())}"

    def generate_rap(self, topic: str = "") -> str:
        """Generate a freestyle rap about a topic using GPT, with fallback."""
        topic = topic.strip() or "being a cool robot"

        # Try GPT first
        try:
            import openai
            client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": (
                        "You are a fun, family-friendly freestyle rapper. "
                        "Write a short 4-8 line rap about the given topic. "
                        "Keep it clean, positive, and catchy. "
                        "Use simple rhyme schemes (AABB or ABAB). "
                        f"The audience is {self._patient_name}. "
                        "Include their name if it fits naturally. "
                        "No explicit content. Be playful and warm."
                    ),
                }, {
                    "role": "user",
                    "content": f"Write a freestyle rap about: {topic}",
                }],
                max_tokens=200,
                temperature=0.9,
            )
            rap = resp.choices[0].message.content.strip()
            logger.info("Generated rap about '%s'", topic)
            return rap
        except Exception as e:
            logger.warning("GPT rap generation failed: %s", e)

        # Fallback to pre-written raps
        topic_lower = topic.lower()
        for key, raps in FALLBACK_RAPS.items():
            if key in topic_lower:
                return random.choice(raps)
        return random.choice(FALLBACK_RAPS["general"])

    def perform(self, topic: str = "") -> str:
        """Generate a rap and perform it with beat movements."""
        if self._performing:
            return "Hold up, I'm already in the middle of a verse!"

        rap = self.generate_rap(topic)
        self._performing = True
        self._rap_count += 1

        # Start beat in background
        self._start_beat()

        # Speak the rap (or just return it if no speak function)
        if self._speak_fn:
            def _do_perform():
                try:
                    self._speak_fn(rap)
                finally:
                    self._stop_performing()
            threading.Thread(target=_do_perform, daemon=True).start()
        else:
            # Auto-stop beat after estimated rap duration
            def _auto_stop():
                time.sleep(max(3, len(rap) * 0.05))
                self._stop_performing()
            threading.Thread(target=_auto_stop, daemon=True).start()

        return rap

    def _start_beat(self):
        """Start rhythmic antenna movements as a beat."""
        self._stop_beat.clear()
        if not self._robot:
            return

        def _beat_loop():
            pattern = BEAT_PATTERNS.get(self._current_beat, BEAT_PATTERNS["boom_bap"])
            try:
                while not self._stop_beat.is_set():
                    for left, right, dur in pattern:
                        if self._stop_beat.is_set():
                            break
                        try:
                            self._robot.mini.head.l_antenna.goal_position = left
                            self._robot.mini.head.r_antenna.goal_position = right
                        except Exception:
                            pass
                        time.sleep(dur)
            except Exception as e:
                logger.debug("Beat loop error: %s", e)
            finally:
                # Reset antennas
                try:
                    self._robot.mini.head.l_antenna.goal_position = 0.0
                    self._robot.mini.head.r_antenna.goal_position = 0.0
                except Exception:
                    pass

        self._beat_thread = threading.Thread(target=_beat_loop, daemon=True)
        self._beat_thread.start()

    def _stop_performing(self):
        """Stop the beat and mark performance as done."""
        self._stop_beat.set()
        self._performing = False

    def stop(self) -> str:
        """Force stop a performance."""
        if not self._performing:
            return "I'm not rapping right now."
        self._stop_performing()
        return "Alright, mic drop! 🎤"

    @property
    def is_performing(self) -> bool:
        return self._performing

    def get_status(self) -> dict:
        return {
            "performing": self._performing,
            "beat": self._current_beat,
            "total_raps": self._rap_count,
            "available_beats": list(BEAT_PATTERNS.keys()),
        }
