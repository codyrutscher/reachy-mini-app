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
def brain_fallback(monkeypatch):
    """Brain with no LLM backend (uses smart fallback)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from brain import Brain
    # Reset memory module globals so it uses hash fallback
    try:
        import memory
        memory._embedder = None
        memory._embed_backend = None
    except Exception:
        pass
    return Brain(backend="none")


@pytest.fixture
def brain_with_memory(monkeypatch):
    """Brain with conversation memory (no LLM backend)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from brain import Brain
    try:
        import memory
        memory._embedder = None
        memory._embed_backend = None
    except Exception:
        pass
    return Brain(backend="none")


# ── New module fixtures ───────────────────────────────────────────

@pytest.fixture
def gratitude(monkeypatch):
    """GratitudeSession with Supabase mocked out."""
    _mock_supabase(monkeypatch)
    from gratitude import GratitudeSession
    return GratitudeSession(patient_id="test")


@pytest.fixture
def quiz(monkeypatch):
    """PersonalQuiz with Supabase mocked to return sample facts."""
    _mock_supabase(monkeypatch)
    from personal_quiz import PersonalQuiz
    return PersonalQuiz(patient_id="test")


@pytest.fixture
def singalong():
    """Fresh SingAlong instance."""
    from singalong import SingAlong
    return SingAlong()


@pytest.fixture
def story():
    """InteractiveStory with sample patient data."""
    from interactive_story import InteractiveStory
    return InteractiveStory(
        patient_id="test",
        patient_name="Margaret",
        facts=["my daughter Sarah lives in Boston", "I love gardening"],
    )


# ── Supabase mock helper ─────────────────────────────────────────

def _mock_supabase(monkeypatch):
    """Replace db_supabase with a no-op stub so tests don't need a real DB."""
    import types
    fake = types.ModuleType("db_supabase")
    fake.is_available = lambda: True
    fake.get_facts = lambda pid: [
        {"category": "family", "fact": "my daughter Sarah lives in Boston"},
        {"category": "pet", "fact": "my dog is named Biscuit"},
        {"category": "career", "fact": "I used to be a teacher"},
        {"category": "location", "fact": "I grew up in Vermont"},
        {"category": "interest", "fact": "I love gardening"},
    ]
    fake.save_fact = lambda *a, **kw: None
    fake.save_conversation = lambda *a, **kw: None
    fake.get_session_summaries = lambda *a, **kw: []
    monkeypatch.setitem(sys.modules, "db_supabase", fake)
