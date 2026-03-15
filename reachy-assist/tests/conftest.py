"""Shared fixtures for the Reachy test suite."""

import sys
import os
import pytest

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def emotion_detector():
    """Keyword-based emotion detector (no model download)."""
    from emotion import EmotionDetector
    return EmotionDetector(backend="keywords")


@pytest.fixture
def checkin():
    """Fresh DailyCheckIn instance."""
    from checkin import DailyCheckIn
    return DailyCheckIn()


@pytest.fixture
def cognitive():
    """Fresh CognitiveExercises instance."""
    from cognitive import CognitiveExercises
    return CognitiveExercises()


@pytest.fixture
def reminder_manager(tmp_path, monkeypatch):
    """ReminderManager that uses a temp file instead of the real one."""
    import reminders
    monkeypatch.setattr(reminders, "REMINDERS_FILE", str(tmp_path / "reminders.json"))
    from reminders import ReminderManager
    return ReminderManager()


@pytest.fixture
def brain_fallback():
    """Brain with no LLM backend (uses smart fallback)."""
    from brain import Brain
    return Brain(backend="none")


@pytest.fixture
def brain_with_memory():
    """Brain with conversation memory (no LLM backend)."""
    from brain import Brain
    return Brain(backend="none")
