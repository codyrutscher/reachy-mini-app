"""Tests for the personalized quiz module."""

import pytest
from personal_quiz import PersonalQuiz, is_quiz_trigger, _make_hint, _QUIZ_TRIGGERS


class TestQuizTrigger:

    def test_detects_triggers(self):
        assert is_quiz_trigger("quiz me") is True
        assert is_quiz_trigger("let's do a memory game") is True
        assert is_quiz_trigger("test my memory please") is True

    def test_ignores_non_triggers(self):
        assert is_quiz_trigger("tell me a joke") is False
        assert is_quiz_trigger("what's the weather") is False

    def test_case_insensitive(self):
        assert is_quiz_trigger("QUIZ TIME") is True

    def test_all_triggers_work(self):
        for t in _QUIZ_TRIGGERS:
            assert is_quiz_trigger(t) is True, f"Missed trigger: {t}"


class TestMakeHint:

    def test_strips_prefix(self):
        assert _make_hint("Grateful for: my family") == "my family"
        assert _make_hint("Patient mentioned: dogs") == "dogs"

    def test_truncates_long_text(self):
        long_text = "a" * 200
        result = _make_hint(long_text)
        assert len(result) <= 80

    def test_normal_text_unchanged(self):
        assert _make_hint("my daughter Sarah") == "my daughter Sarah"


class TestPersonalQuiz:

    def test_starts_inactive(self, quiz):
        assert not quiz.is_active

    def test_start_with_facts(self, quiz):
        prompt = quiz.start()
        assert quiz.is_active
        assert quiz.total == 5  # we have 5 mock facts
        assert "quiz" in prompt.lower() or "memory" in prompt.lower()

    def test_start_without_facts(self, monkeypatch):
        """When there aren't enough facts, quiz should decline gracefully."""
        import sys
        import types
        fake = types.ModuleType("db_supabase")
        fake.is_available = lambda: True
        fake.get_facts = lambda pid: []  # no facts
        monkeypatch.setitem(sys.modules, "db_supabase", fake)

        q = PersonalQuiz(patient_id="empty")
        prompt = q.start()
        assert not q.is_active
        assert "enough" in prompt.lower() or "know" in prompt.lower()

    def test_check_answer_advances(self, quiz):
        quiz.start()
        prompt = quiz.check_answer("Sarah lives in Boston")
        assert quiz.current == 1
        # Should contain the next question or follow-up
        assert prompt

    def test_always_counts_as_correct(self, quiz):
        quiz.start()
        quiz.check_answer("anything at all")
        assert quiz.score == 1

    def test_full_quiz_flow(self, quiz):
        quiz.start()
        total = quiz.total
        for i in range(total):
            prompt = quiz.check_answer(f"answer {i}")
        # Should be done
        assert not quiz.is_active
        assert quiz.score == total
        assert "wonderfully" in prompt.lower() or "special" in prompt.lower()

    def test_check_answer_when_inactive(self, quiz):
        result = quiz.check_answer("hello")
        assert result == ""

    def test_questions_use_fact_content(self, quiz):
        quiz.start()
        # Each question should reference a fact
        for q, _follow, fact in quiz.questions:
            assert fact  # original fact is preserved
