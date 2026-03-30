"""Physical Interaction Games — reaction time, puppet mode, bump detection.

Collection of games that use Reachy's physical body for interaction.
"""

import logging
import random
import threading
import time

logger = logging.getLogger(__name__)


class ReactionTimeGame:
    """Reachy moves suddenly, patient says 'now!' as fast as possible."""

    def __init__(self, robot=None, sound_effects=None):
        self._robot = robot
        self._sfx = sound_effects
        self._active = False
        self._waiting = False
        self._move_time = 0.0
        self._times: list[float] = []
        self._round = 0

    def start(self) -> str:
        self._active = True
        self._times = []
        self._round = 0
        return self._next_round()

    def _next_round(self) -> str:
        self._round += 1
        self._waiting = False
        if self._round > 5:
            return self.end()

        # Random delay before moving
        delay = random.uniform(2.0, 5.0)

        def _do_move():
            time.sleep(delay)
            if not self._active:
                return
            self._move_time = time.time()
            self._waiting = True
            if self._robot:
                action = random.choice(["wiggle", "nod", "surprised", "celebrate"])
                self._robot.perform(action)
            if self._sfx:
                self._sfx.play("ding")

        threading.Thread(target=_do_move, daemon=True).start()
        return f"Round {self._round}! Watch me carefully... say 'now' the instant I move!"

    def player_reacts(self) -> str:
        if not self._active:
            return ""
        if not self._waiting:
            return "Wait for it... I haven't moved yet!"
        reaction_ms = int((time.time() - self._move_time) * 1000)
        self._times.append(reaction_ms)
        self._waiting = False
        if reaction_ms < 500:
            comment = "Lightning fast!"
        elif reaction_ms < 1000:
            comment = "Quick reflexes!"
        elif reaction_ms < 2000:
            comment = "Not bad!"
        else:
            comment = "A bit slow, but that's okay!"
        result = f"{reaction_ms}ms — {comment}"
        if self._round >= 5:
            return result + " " + self.end()
        return result + " " + self._next_round()

    def end(self) -> str:
        self._active = False
        if not self._times:
            return "Game over!"
        avg = int(sum(self._times) / len(self._times))
        best = min(self._times)
        if self._sfx:
            self._sfx.play("tada")
        return (
            f"Game over! Average reaction time: {avg}ms. "
            f"Best: {best}ms. {'Great reflexes!' if avg < 800 else 'Nice effort!'}"
        )

    @property
    def is_active(self) -> bool:
        return self._active


class BumpDetector:
    """Detects when someone bumps or shakes Reachy using the IMU."""

    def __init__(self, robot=None):
        self._robot = robot
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()
        self._on_bump = None  # callback
        self._cooldown = 0.0
        self._min_interval = 5.0

    def start(self, on_bump=None) -> str:
        if self._running:
            return "Already detecting bumps."
        if not self._robot or self._robot._sim_mode or not self._robot.mini:
            return "Need real robot for bump detection."
        self._on_bump = on_bump
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._detect_loop, daemon=True)
        self._thread.start()
        logger.info("Bump detection started")
        return "I can feel when you touch me now!"

    def stop(self):
        self._stop_event.set()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def _detect_loop(self):
        """Poll IMU for sudden acceleration changes."""
        try:
            while not self._stop_event.is_set():
                try:
                    imu = self._robot.mini.imu
                    if imu:
                        # IMU typically provides acceleration data
                        accel = getattr(imu, 'acceleration', None)
                        if accel:
                            # Check for sudden movement (bump)
                            magnitude = sum(a ** 2 for a in accel) ** 0.5
                            # Normal gravity is ~9.8, bump would spike above ~12
                            now = time.time()
                            if magnitude > 12 and now - self._cooldown > self._min_interval:
                                self._cooldown = now
                                logger.info("Bump detected! magnitude=%.1f", magnitude)
                                if self._on_bump:
                                    self._on_bump()
                except Exception:
                    pass
                self._stop_event.wait(0.1)
        except Exception as e:
            logger.error("Bump detection error: %s", e)
        finally:
            self._running = False
