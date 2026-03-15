"""Tests for the Autonomy Engine — verifies Reachy proactively checks in
with the patient, detects silence, offers hydration, responds to mood
patterns, and runs time-based routines without any user input."""

import time
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from autonomy import AutonomyEngine, ProactiveAction


@pytest.fixture
def engine():
    """Autonomy engine with very short intervals for testing."""
    return AutonomyEngine(profile_config={
        "idle_anim_interval": 999999,  # disable idle anims for cleaner tests
        "hydration_interval": 1,       # 1 second
        "exercise_interval": 1,
        "checkin_interval": 1,
        "min_proactive_gap": 0,        # no cooldown between proactive actions
        "silence_threshold": 1,        # 1 second
        "long_silence_threshold": 2,
    })


class TestCheckinSuggestion:
    """Verify Reachy autonomously suggests a wellness check-in."""

    def test_checkin_fires_after_interval(self, engine):
        """After the checkin interval elapses, a check-in suggestion should be queued."""
        engine._last_checkin_suggest = time.time() - 10  # pretend it's been a while
        engine._last_proactive = 0  # allow proactive

        from unittest.mock import patch
        from datetime import datetime as dt

        # Simulate hour=10 (within 9-20 range)
        with patch("autonomy.datetime") as mock_dt:
            mock_dt.now.return_value = dt(2026, 3, 14, 10, 0, 0)
            mock_dt.side_effect = lambda *a, **kw: dt(*a, **kw)
            engine._check_checkin_suggestion(time.time(), 10)

        action = engine.get_next_action()
        assert action is not None, "Expected a check-in suggestion to be queued"
        assert action.action_type == "checkin_suggest"
        assert "check-in" in action.message.lower() or "wellness" in action.message.lower()

    def test_checkin_does_not_fire_too_soon(self, engine):
        """Check-in should NOT fire if the interval hasn't elapsed."""
        engine._last_checkin_suggest = time.time()  # just happened
        engine.checkin_interval = 99999
        engine._last_proactive = 0

        engine._check_checkin_suggestion(time.time(), 10)

        action = engine.get_next_action()
        assert action is None, "Check-in should not fire before interval elapses"

    def test_checkin_does_not_fire_at_night(self, engine):
        """Check-in should NOT fire outside waking hours (before 9 or after 20)."""
        engine._last_checkin_suggest = 0
        engine._last_proactive = 0

        engine._check_checkin_suggestion(time.time(), 3)  # 3 AM

        action = engine.get_next_action()
        assert action is None, "Check-in should not fire at 3 AM"


class TestSilenceDetection:
    """Verify Reachy reaches out when the patient has been quiet."""

    def test_gentle_check_after_silence(self, engine):
        """After silence_threshold, a gentle check should be queued."""
        engine._last_interaction = time.time() - 5  # 5 seconds of silence
        engine._last_proactive = 0

        engine._check_silence(time.time())

        action = engine.get_next_action()
        assert action is not None, "Expected a silence check action"
        # Could be gentle_check or long_silence depending on thresholds
        assert action.action_type in ("gentle_check", "long_silence")
        assert len(action.message) > 0

    def test_long_silence_triggers_conversation_starter(self, engine):
        """After long_silence_threshold, Reachy should try to start a conversation."""
        engine._last_interaction = time.time() - 10  # well past long_silence_threshold of 2s
        engine._last_proactive = 0

        engine._check_silence(time.time())

        action = engine.get_next_action()
        assert action is not None
        assert action.action_type == "long_silence"
        assert "here" in action.message.lower() or "while" in action.message.lower()

    def test_no_check_if_recently_active(self, engine):
        """No silence check if the patient just spoke."""
        engine._last_interaction = time.time()  # just now
        engine._last_proactive = 0

        engine._check_silence(time.time())

        action = engine.get_next_action()
        assert action is None


class TestHydrationReminder:
    """Verify Reachy reminds the patient to drink water."""

    def test_hydration_reminder_fires(self, engine):
        engine._last_hydration = 0
        engine._last_proactive = 0

        from unittest.mock import patch
        from datetime import datetime as dt

        with patch("autonomy.datetime") as mock_dt:
            mock_dt.now.return_value = dt(2026, 3, 14, 14, 0, 0)
            engine._check_hydration(time.time())

        action = engine.get_next_action()
        assert action is not None
        assert action.action_type == "hydration"
        assert "water" in action.message.lower()

    def test_no_hydration_at_night(self, engine):
        engine._last_hydration = 0
        engine._last_proactive = 0

        from unittest.mock import patch
        from datetime import datetime as dt

        with patch("autonomy.datetime") as mock_dt:
            mock_dt.now.return_value = dt(2026, 3, 14, 2, 0, 0)
            engine._check_hydration(time.time())

        action = engine.get_next_action()
        assert action is None


class TestMoodComfort:
    """Verify Reachy offers comfort after sustained negative mood."""

    def test_comfort_after_3_sad(self, engine):
        engine._last_proactive = 0
        engine.notify_mood("sadness")
        engine.notify_mood("sadness")
        engine.notify_mood("sadness")

        engine._check_mood_patterns()

        action = engine.get_next_action()
        assert action is not None
        assert action.action_type == "mood_comfort"
        assert action.priority == 4  # high priority

    def test_no_comfort_if_mood_improves(self, engine):
        engine._last_proactive = 0
        engine.notify_mood("sadness")
        engine.notify_mood("sadness")
        engine.notify_mood("joy")  # mood improved, resets counter

        engine._check_mood_patterns()

        action = engine.get_next_action()
        assert action is None


class TestExerciseSuggestion:
    """Verify Reachy suggests exercises during the day."""

    def test_exercise_suggestion_fires(self, engine):
        engine._last_exercise_suggest = 0
        engine._last_proactive = 0

        engine._check_exercise_suggestion(time.time(), 10)

        action = engine.get_next_action()
        assert action is not None
        assert action.action_type == "exercise_suggest"
        assert "exercise" in action.message.lower() or "stretch" in action.message.lower() or "move" in action.message.lower()


class TestTimeBasedRoutines:
    """Verify morning, midday, and evening routines fire at the right times."""

    def test_midday_routine(self, engine):
        engine._afternoon_done = False
        engine._last_proactive = 0

        engine._check_midday_routine(13, time.time())

        action = engine.get_next_action()
        assert action is not None
        assert action.action_type == "midday_routine"
        assert engine._afternoon_done is True

    def test_midday_only_fires_once(self, engine):
        engine._afternoon_done = False
        engine._last_proactive = 0

        engine._check_midday_routine(13, time.time())
        engine._check_midday_routine(13, time.time())

        # First action
        action1 = engine.get_next_action()
        assert action1 is not None
        # Second should be None (already done)
        action2 = engine.get_next_action()
        assert action2 is None

    def test_evening_routine(self, engine):
        engine._evening_done = False
        engine._last_proactive = 0

        engine._check_evening_routine(21)

        action = engine.get_next_action()
        assert action is not None
        assert action.action_type == "evening_routine"

    def test_no_evening_routine_at_noon(self, engine):
        engine._evening_done = False
        engine._last_proactive = 0

        engine._check_evening_routine(12)

        action = engine.get_next_action()
        assert action is None


class TestActionQueue:
    """Verify the action queue prioritization works correctly."""

    def test_higher_priority_first(self, engine):
        engine._queue_action(ProactiveAction("low", "low priority", priority=1))
        engine._queue_action(ProactiveAction("high", "high priority", priority=5))

        action = engine.get_next_action()
        assert action.action_type == "high"

    def test_no_duplicate_actions(self, engine):
        engine._queue_action(ProactiveAction("checkin_suggest", "first"))
        engine._queue_action(ProactiveAction("checkin_suggest", "duplicate"))

        action1 = engine.get_next_action()
        action2 = engine.get_next_action()
        assert action1 is not None
        assert action2 is None  # duplicate was rejected

    def test_empty_queue_returns_none(self, engine):
        assert engine.get_next_action() is None


class TestInteractionNotifications:
    """Verify that interaction/mood notifications update engine state."""

    def test_notify_interaction_resets_timer(self, engine):
        engine._last_interaction = 0
        engine.notify_interaction()
        assert time.time() - engine._last_interaction < 1

    def test_notify_mood_tracks_history(self, engine):
        engine.notify_mood("joy")
        engine.notify_mood("sadness")
        assert len(engine._mood_history) == 2
        assert engine._mood_history[0][0] == "joy"
        assert engine._mood_history[1][0] == "sadness"

    def test_consecutive_sad_counter(self, engine):
        engine.notify_mood("sadness")
        engine.notify_mood("sadness")
        assert engine._consecutive_sad == 2
        engine.notify_mood("joy")
        assert engine._consecutive_sad == 0
