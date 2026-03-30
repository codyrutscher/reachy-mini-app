"""Emotion-Reactive Ambient Movements — Reachy feels alive.

Continuous subtle movements that match the conversation mood in real-time.
Reachy breathes, tilts, leans in when interested, droops when sad,
and does little happy wiggles when the patient laughs.

Usage:
    from robot.ambient_movement import AmbientMovement
    am = AmbientMovement(robot)
    am.start()                    # begin ambient movement loop
    am.set_emotion("joy")        # update current emotion
    am.on_listening()            # patient is speaking
    am.on_thinking()             # GPT is generating
    am.on_speaking()             # Reachy is talking
    am.stop()
"""

import random
import threading
import time
from typing import Any, Optional

from core.log_config import get_logger

logger = get_logger("ambient_movement")

# How often to do an ambient movement (seconds)
AMBIENT_INTERVAL = 4.0

# Emotion to movement style mapping
EMOTION_STYLES: dict[str, dict] = {
    "joy": {
        "moves": ["happy_wiggle", "antenna_perk", "slight_bounce"],
        "head_roll_range": (-5, 5),
        "antenna_base": [-0.3, -0.3],  # perky
        "energy": 1.2,
    },
    "sadness": {
        "moves": ["gentle_droop", "slow_tilt", "soft_breathe"],
        "head_roll_range": (-8, -2),
        "antenna_base": [0.2, 0.2],  # droopy
        "energy": 0.6,
    },
    "fear": {
        "moves": ["slight_retreat", "antenna_flatten", "small_tremble"],
        "head_roll_range": (-3, 3),
        "antenna_base": [0.4, 0.4],
        "energy": 0.8,
    },
    "anger": {
        "moves": ["firm_stance", "antenna_back"],
        "head_roll_range": (-2, 2),
        "antenna_base": [0.5, 0.5],
        "energy": 0.7,
    },
    "surprise": {
        "moves": ["quick_perk", "antenna_up", "slight_lean"],
        "head_roll_range": (-3, 3),
        "antenna_base": [-0.5, -0.5],
        "energy": 1.3,
    },
    "neutral": {
        "moves": ["idle_breathe", "idle_tilt", "idle_look"],
        "head_roll_range": (-3, 3),
        "antenna_base": [0.0, 0.0],
        "energy": 0.8,
    },
}


class AmbientMovement:
    """Continuous emotion-reactive movement system for Reachy."""

    def __init__(self, robot: Any) -> None:
        self._robot = robot
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._emotion: str = "neutral"
        self._state: str = "idle"  # idle, listening, thinking, speaking
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the ambient movement loop in a background thread."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Ambient movement started")

    def stop(self) -> None:
        """Stop the ambient movement loop."""
        self._running = False
        self._stop_event.set()
        logger.info("Ambient movement stopped")

    def set_emotion(self, emotion: str) -> None:
        """Update the current emotion — affects movement style."""
        with self._lock:
            if emotion != self._emotion:
                self._emotion = emotion
                logger.debug("Emotion updated: %s", emotion)

    def on_listening(self) -> None:
        """Patient is speaking — Reachy leans in attentively."""
        with self._lock:
            self._state = "listening"

    def on_thinking(self) -> None:
        """GPT is generating — Reachy does a thinking animation."""
        with self._lock:
            self._state = "thinking"

    def on_speaking(self) -> None:
        """Reachy is talking — subtle movements while speaking."""
        with self._lock:
            self._state = "speaking"

    def on_idle(self) -> None:
        """No one is talking — gentle ambient movements."""
        with self._lock:
            self._state = "idle"

    def trigger_mirror(self, emotion: str) -> None:
        """Mirror the patient's emotion with a quick reactive movement.
        Called when a strong emotion is detected."""
        if not self._robot or self._robot._sim_mode:
            return
        try:
            if emotion == "joy":
                self._robot.moves.happy_wiggle()
            elif emotion == "sadness":
                self._robot.moves.empathy_lean()
            elif emotion == "surprise":
                self._robot.moves.surprised()
            elif emotion == "fear":
                self._robot.moves.comfort_pat()
        except Exception as e:
            logger.debug("Mirror movement error: %s", e)

    def _loop(self) -> None:
        """Main ambient movement loop."""
        while self._running and not self._stop_event.is_set():
            with self._lock:
                emotion = self._emotion
                state = self._state

            style = EMOTION_STYLES.get(emotion, EMOTION_STYLES["neutral"])
            interval = AMBIENT_INTERVAL / style["energy"]

            try:
                if state == "listening":
                    self._do_listening_move(style)
                elif state == "thinking":
                    self._do_thinking_move()
                elif state == "speaking":
                    self._do_speaking_move(style)
                else:
                    self._do_idle_move(style)
            except Exception as e:
                logger.debug("Ambient movement error: %s", e)

            self._stop_event.wait(timeout=interval)

        logger.info("Ambient movement loop ended")

    def _do_idle_move(self, style: dict) -> None:
        """Gentle idle movements — breathing, small tilts."""
        if not self._robot or not self._robot.moves:
            return
        if self._robot._sim_mode:
            return
        move = random.choice(["breathe", "tilt", "antenna"])
        try:
            if move == "breathe":
                self._robot.moves.idle_breathe()
            elif move == "tilt":
                self._robot.moves.idle_tilt()
            elif move == "antenna":
                self._robot.moves.idle_antenna_twitch()
        except Exception:
            pass

    def _do_listening_move(self, style: dict) -> None:
        """Attentive movements while patient speaks — lean in, nod slightly."""
        if not self._robot or not self._robot.moves:
            return
        if self._robot._sim_mode:
            return
        try:
            move = random.choice(["lean", "nod", "tilt"])
            if move == "lean":
                self._robot.moves.listening()
            elif move == "nod":
                self._robot.moves.nod_yes()
            elif move == "tilt":
                self._robot.moves.curious_look()
        except Exception:
            pass

    def _do_thinking_move(self) -> None:
        """Thinking animation while GPT generates."""
        if not self._robot or not self._robot.moves:
            return
        if self._robot._sim_mode:
            return
        try:
            self._robot.moves.thinking()
        except Exception:
            pass

    def _do_speaking_move(self, style: dict) -> None:
        """Subtle movements while Reachy speaks — small head tilts."""
        if not self._robot or not self._robot.moves:
            return
        if self._robot._sim_mode:
            return
        try:
            move = random.choice(["tilt", "antenna", "look"])
            if move == "tilt":
                self._robot.moves.idle_tilt()
            elif move == "antenna":
                self._robot.moves.idle_antenna_twitch()
            elif move == "look":
                self._robot.moves.idle_look()
        except Exception:
            pass

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "emotion": self._emotion,
            "state": self._state,
        }
