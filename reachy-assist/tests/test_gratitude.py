"""Tests for the gratitude practice module."""

import pytest
from gratitude import GratitudeSession


class TestGratitudeSession:

    def test_starts_inactive(self, gratitude):
        assert not gratitude.is_active
        assert gratitude.remaining == 3

    def test_start_activates(self, gratitude):
        prompt = gratitude.start()
        assert gratitude.is_active
        assert gratitude.remaining == 3
        assert "grateful" in prompt.lower() or "gratitude" in prompt.lower()

    def test_first_answer(self, gratitude):
        gratitude.start()
        prompt = gratitude.record_answer("my family")
        assert gratitude.remaining == 2
        assert gratitude.is_active
        assert "second" in prompt.lower()

    def test_second_answer(self, gratitude):
        gratitude.start()
        gratitude.record_answer("my family")
        prompt = gratitude.record_answer("sunny weather")
        assert gratitude.remaining == 1
        assert gratitude.is_active
        assert "third" in prompt.lower()

    def test_third_answer_completes(self, gratitude):
        gratitude.start()
        gratitude.record_answer("my family")
        gratitude.record_answer("sunny weather")
        prompt = gratitude.record_answer("my dog Biscuit")
        assert not gratitude.is_active
        assert gratitude.remaining == 0
        # Summary should reference all three
        assert "family" in prompt.lower() or "3" in prompt or "three" in prompt.lower()

    def test_answers_stored(self, gratitude):
        gratitude.start()
        gratitude.record_answer("coffee")
        gratitude.record_answer("music")
        gratitude.record_answer("friends")
        assert len(gratitude.answers) == 3
        assert gratitude.answers == ["coffee", "music", "friends"]

    def test_record_answer_when_inactive(self, gratitude):
        result = gratitude.record_answer("hello")
        assert result is None

    def test_full_flow_returns_prompts(self, gratitude):
        p0 = gratitude.start()
        p1 = gratitude.record_answer("a")
        p2 = gratitude.record_answer("b")
        p3 = gratitude.record_answer("c")
        # All prompts should be non-empty strings
        for p in [p0, p1, p2, p3]:
            assert isinstance(p, str)
            assert len(p) > 10
