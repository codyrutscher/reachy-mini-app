"""Autonomy engine — proactive behavior scheduler that makes Reachy
act on its own based on time of day, patient patterns, and context.
Runs in a background thread and queues actions for the main loop."""

import random
import threading
import time
from datetime import datetime, timedelta
from core.log_config import get_logger

logger = get_logger("autonomy")


class ProactiveAction:
    """A single queued action for the main loop to execute."""
    def __init__(self, action_type, message="", robot_action="", priority=0):
        self.action_type = action_type  # speak, move, music, exercise, etc.
        self.message = message
        self.robot_action = robot_action
        self.priority = priority  # higher = more urgent
        self.created = time.time()


class AutonomyEngine:
    def __init__(self, profile_config: dict = None):
        self._running = False
        self._thread = None
        self._action_queue = []
        self._queue_lock = threading.Lock()

        # Tracking state
        self._last_interaction = time.time()
        self._last_proactive = time.time()
        self._last_idle_anim = time.time()
        self._last_hydration = 0
        self._last_exercise_suggest = 0
        self._last_checkin_suggest = 0
        self._last_news_offer = 0
        self._morning_done = False
        self._afternoon_done = False
        self._evening_done = False
        self._mood_history = []
        self._consecutive_sad = 0

        # Apply profile config or defaults
        cfg = profile_config or {}
        self.idle_anim_interval = cfg.get("idle_anim_interval", 45)
        self.hydration_interval = cfg.get("hydration_interval", 3600)
        self.exercise_interval = cfg.get("exercise_interval", 7200)
        self.checkin_interval = cfg.get("checkin_interval", 14400)
        self.min_proactive_gap = cfg.get("min_proactive_gap", 300)
        self.silence_threshold = cfg.get("silence_threshold", 600)
        self.long_silence_threshold = cfg.get("long_silence_threshold", 1800)
        self._morning_start = cfg.get("morning_hour_start", 7)
        self._morning_end = cfg.get("morning_hour_end", 9)
        self._evening_start = cfg.get("evening_hour_start", 20)
        self._evening_end = cfg.get("evening_hour_end", 22)

    def start(self):
        """Start the autonomy engine background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Proactive behavior engine started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Engine stopped")

    def notify_interaction(self):
        """Called when the patient speaks — resets silence timers."""
        self._last_interaction = time.time()

    def notify_mood(self, mood: str):
        """Track mood for pattern detection."""
        self._mood_history.append((mood, time.time()))
        # Keep last 20
        self._mood_history = self._mood_history[-20:]
        if mood in ("sadness", "fear", "anger"):
            self._consecutive_sad += 1
        else:
            self._consecutive_sad = 0

    def get_next_action(self) -> ProactiveAction | None:
        """Get the next queued action (called by main loop)."""
        with self._queue_lock:
            if not self._action_queue:
                return None
            # Sort by priority (highest first), then by creation time
            self._action_queue.sort(key=lambda a: (-a.priority, a.created))
            return self._action_queue.pop(0)

    def _queue_action(self, action: ProactiveAction):
        with self._queue_lock:
            # Don't queue duplicates
            for existing in self._action_queue:
                if existing.action_type == action.action_type:
                    return
            self._action_queue.append(action)

    def _can_be_proactive(self) -> bool:
        """Check if enough time has passed since last proactive message."""
        return (time.time() - self._last_proactive) > self.min_proactive_gap

    def _mark_proactive(self):
        self._last_proactive = time.time()

    # ── Main background loop ────────────────────────────────────────

    def _run_loop(self):
        while self._running:
            try:
                now = datetime.now()
                hour = now.hour
                ts = time.time()

                # ── Time-based routines ─────────────────────────────
                self._check_morning_routine(hour)
                self._check_midday_routine(hour, ts)
                self._check_evening_routine(hour)

                # ── Reset daily flags at midnight ───────────────────
                if hour == 0:
                    self._morning_done = False
                    self._afternoon_done = False
                    self._evening_done = False

                # ── Silence detection ───────────────────────────────
                self._check_silence(ts)

                # ── Mood pattern detection ──────────────────────────
                self._check_mood_patterns()

                # ── Periodic suggestions ────────────────────────────
                self._check_hydration(ts)
                self._check_exercise_suggestion(ts, hour)
                self._check_checkin_suggestion(ts, hour)

                # ── Idle animations ─────────────────────────────────
                self._check_idle_animation(ts)

            except Exception as e:
                logger.error("Error: %s", e)

            time.sleep(10)  # check every 10 seconds

    # ── Time-based routines ─────────────────────────────────────────

    def _check_morning_routine(self, hour: int):
        if self._morning_done or not (self._morning_start <= hour <= self._morning_end):
            return
        if not self._can_be_proactive():
            return

        from activities.weather import weather_briefing
        from activities.affirmations import morning_affirmation

        weather = weather_briefing()
        affirmation = morning_affirmation()

        msg = (
            f"Good morning! I hope you slept well. "
            f"{weather} "
            f"{affirmation} "
            f"Don't forget to take your morning medication if you have any. "
            f"What would you like to do today?"
        )
        self._queue_action(ProactiveAction(
            "morning_routine", msg, robot_action="wake up", priority=5
        ))
        self._morning_done = True
        self._mark_proactive()

    def _check_midday_routine(self, hour: int, ts: float):
        """12-14: midday check-in with suggestions."""
        if self._afternoon_done or not (12 <= hour <= 14):
            return
        if not self._can_be_proactive():
            return

        options = [
            "It's the middle of the day! How about a little stretch or some exercise?",
            "Afternoon check! Have you had lunch yet? And don't forget to drink some water.",
            "Hey there! Want to hear today's news, play a game, or just chat?",
            "It's a good time for a brain game or a story. What sounds fun?",
        ]
        self._queue_action(ProactiveAction(
            "midday_routine", random.choice(options), robot_action="curious", priority=3
        ))
        self._afternoon_done = True
        self._mark_proactive()

    def _check_evening_routine(self, hour: int):
        if self._evening_done or not (self._evening_start <= hour <= self._evening_end):
            return
        if not self._can_be_proactive():
            return

        options = [
            "It's getting late. Would you like a bedtime story or some calming music before sleep?",
            "Evening time! How about a gentle meditation to wind down? Or I can read you a story.",
            "The day is winding down. Did you take your evening medication? Let me know if you need anything before bed.",
        ]
        self._queue_action(ProactiveAction(
            "evening_routine", random.choice(options), robot_action="rock", priority=3
        ))
        self._evening_done = True
        self._mark_proactive()

    # ── Silence detection ───────────────────────────────────────────

    def _check_silence(self, ts: float):
        silence = ts - self._last_interaction
        if not self._can_be_proactive():
            return

        if silence > self.long_silence_threshold:
            from brain.companion import get_conversation_starter
            starter = get_conversation_starter()
            self._queue_action(ProactiveAction(
                "long_silence",
                f"Hey, it's been a while! I'm still here. {starter}",
                robot_action="curious", priority=2
            ))
            self._mark_proactive()
            self._last_interaction = ts  # reset so we don't spam

        elif silence > self.silence_threshold:
            gentle = [
                "Just checking — everything okay over there?",
                "I'm here if you need anything!",
                "How are you doing? Want to chat or play a game?",
            ]
            self._queue_action(ProactiveAction(
                "gentle_check", random.choice(gentle),
                robot_action="listen", priority=1
            ))
            self._mark_proactive()
            self._last_interaction = ts

    # ── Mood pattern detection ──────────────────────────────────────

    def _check_mood_patterns(self):
        if self._consecutive_sad >= 3 and self._can_be_proactive():
            comfort = [
                "I've noticed you seem a bit down. Would you like to talk about it, or maybe listen to some calming music?",
                "Hey, I care about you. Want me to play something soothing, or would a joke help?",
                "I'm here for you. Sometimes a breathing exercise can help. Want to try one together?",
            ]
            self._queue_action(ProactiveAction(
                "mood_comfort", random.choice(comfort),
                robot_action="empathy", priority=4
            ))
            self._consecutive_sad = 0  # reset after offering comfort
            self._mark_proactive()

    # ── Periodic suggestions ────────────────────────────────────────

    def _check_hydration(self, ts: float):
        if (ts - self._last_hydration) < self.hydration_interval:
            return
        if not self._can_be_proactive():
            return
        hour = datetime.now().hour
        if not (8 <= hour <= 21):  # only during waking hours
            return

        nudges = [
            "Quick reminder — have you had some water recently? Staying hydrated is important!",
            "Water break! Try to drink a glass of water. Your body will thank you.",
            "Hey, just a gentle nudge to drink some water!",
        ]
        self._queue_action(ProactiveAction(
            "hydration", random.choice(nudges), priority=1
        ))
        self._last_hydration = ts
        self._mark_proactive()

    def _check_exercise_suggestion(self, ts: float, hour: int):
        if (ts - self._last_exercise_suggest) < self.exercise_interval:
            return
        if not self._can_be_proactive():
            return
        if not (9 <= hour <= 18):
            return

        suggestions = [
            "How about some gentle exercises? We could do neck rolls, shoulder shrugs, or a seated march!",
            "It's been a while since we moved around. Want to do a quick stretch together?",
            "Your body would love some movement! Want me to guide you through some exercises?",
        ]
        self._queue_action(ProactiveAction(
            "exercise_suggest", random.choice(suggestions),
            robot_action="stretch", priority=1
        ))
        self._last_exercise_suggest = ts
        self._mark_proactive()

    def _check_checkin_suggestion(self, ts: float, hour: int):
        if (ts - self._last_checkin_suggest) < self.checkin_interval:
            return
        if not self._can_be_proactive():
            return
        if not (9 <= hour <= 20):
            return

        self._queue_action(ProactiveAction(
            "checkin_suggest",
            "How about a quick wellness check-in? It only takes a minute and helps me take better care of you.",
            robot_action="listen", priority=2
        ))
        self._last_checkin_suggest = ts
        self._mark_proactive()

    # ── Idle animations ─────────────────────────────────────────────

    def _check_idle_animation(self, ts: float):
        """Queue subtle idle movements so Reachy looks alive."""
        if (ts - self._last_idle_anim) < self.idle_anim_interval:
            return

        animations = [
            ProactiveAction("idle_anim", "", robot_action="idle_look"),
            ProactiveAction("idle_anim", "", robot_action="idle_tilt"),
            ProactiveAction("idle_anim", "", robot_action="idle_breathe"),
        ]
        self._queue_action(random.choice(animations))
        self._last_idle_anim = ts
