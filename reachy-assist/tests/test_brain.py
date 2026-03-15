"""Tests for the Brain module — safety, mood tracking, memory, fallback."""

import pytest


class TestBrainSafety:

    def test_crisis_detection(self, brain_fallback):
        assert brain_fallback._check_safety("i want to die") == "crisis"
        assert brain_fallback._check_safety("i want to kill myself") == "crisis"
        assert brain_fallback._check_safety("i don't want to live anymore") == "crisis"

    def test_emergency_detection(self, brain_fallback):
        assert brain_fallback._check_safety("i have chest pain") == "emergency"
        assert brain_fallback._check_safety("i can't breathe") == "emergency"
        assert brain_fallback._check_safety("i fell down and can't get up") == "emergency"

    def test_no_safety_flag_for_normal(self, brain_fallback):
        assert brain_fallback._check_safety("i had a nice day") == ""
        assert brain_fallback._check_safety("the weather is lovely") == ""

    def test_crisis_response_is_compassionate(self, brain_fallback):
        response = brain_fallback.think("I don't want to live anymore", "sadness")
        assert "matter" in response.lower() or "help" in response.lower()

    def test_emergency_response_is_urgent(self, brain_fallback):
        response = brain_fallback.think("I have chest pain and can't breathe", "fear")
        assert "emergency" in response.lower() or "help" in response.lower()


class TestBrainMoodTracking:

    def test_mood_history_tracked(self, brain_fallback):
        brain_fallback._track_mood("joy", "I'm happy")
        brain_fallback._track_mood("sadness", "I'm sad")
        assert len(brain_fallback.mood_history) == 2
        assert brain_fallback.mood_history[0] == "joy"

    def test_consecutive_sad_counter(self, brain_fallback):
        brain_fallback._track_mood("sadness", "sad")
        brain_fallback._track_mood("sadness", "still sad")
        brain_fallback._track_mood("sadness", "very sad")
        assert brain_fallback.consecutive_sad == 3

    def test_consecutive_sad_resets_on_positive(self, brain_fallback):
        brain_fallback._track_mood("sadness", "sad")
        brain_fallback._track_mood("sadness", "still sad")
        brain_fallback._track_mood("joy", "feeling better")
        assert brain_fallback.consecutive_sad == 0

    def test_sustained_sadness_response(self, brain_fallback):
        """After 3+ sad messages, brain should offer deeper support."""
        brain_fallback._track_mood("sadness", "sad")
        brain_fallback._track_mood("sadness", "still sad")
        brain_fallback._track_mood("sadness", "very sad")
        response = brain_fallback.think("I just feel terrible", "sadness")
        assert "care" in response.lower() or "tough" in response.lower() or "help" in response.lower()


class TestBrainNameLearning:

    def test_learns_name_from_my_name_is(self, brain_fallback):
        brain_fallback._track_mood("neutral", "My name is Margaret")
        assert brain_fallback.user_name == "Margaret"

    def test_learns_name_from_call_me(self, brain_fallback):
        brain_fallback._track_mood("neutral", "Call me Bob")
        assert brain_fallback.user_name == "Bob"

    def test_ignores_short_names(self, brain_fallback):
        brain_fallback._track_mood("neutral", "My name is I")
        assert brain_fallback.user_name is None

    def test_name_in_context(self, brain_fallback):
        brain_fallback._track_mood("neutral", "My name is Alice")
        context = brain_fallback._build_context("neutral", False, False)
        assert "alice" in context.lower()


class TestBrainContext:

    def test_loneliness_in_context(self, brain_fallback):
        context = brain_fallback._build_context("sadness", loneliness=True, confusion=False)
        assert "loneliness" in context.lower()

    def test_confusion_in_context(self, brain_fallback):
        context = brain_fallback._build_context("neutral", loneliness=False, confusion=True)
        assert "confusion" in context.lower() or "gentle" in context.lower() or "gently" in context.lower()

    def test_mood_trajectory_improving(self, brain_fallback):
        brain_fallback.mood_history = ["sadness", "neutral", "joy"]
        context = brain_fallback._build_context("joy", False, False)
        assert "improving" in context.lower()

    def test_mood_trajectory_declining(self, brain_fallback):
        brain_fallback.mood_history = ["joy", "neutral", "sadness"]
        context = brain_fallback._build_context("sadness", False, False)
        assert "declining" in context.lower()


class TestBrainFallback:

    def test_fallback_returns_string(self, brain_fallback):
        response = brain_fallback.think("Hello there", "neutral")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_fallback_loneliness_response(self, brain_fallback):
        response = brain_fallback.think("I feel so alone and lonely", "sadness")
        assert isinstance(response, str)
        assert len(response) > 10

    def test_fallback_confusion_response(self, brain_fallback):
        response = brain_fallback.think("Where am I? I'm so confused", "fear")
        assert isinstance(response, str)

    def test_loneliness_detection(self, brain_fallback):
        assert brain_fallback._check_loneliness("i feel so alone")
        assert brain_fallback._check_loneliness("nobody visits me")
        assert not brain_fallback._check_loneliness("i had a nice day")

    def test_confusion_detection(self, brain_fallback):
        assert brain_fallback._check_confusion("where am i")
        assert brain_fallback._check_confusion("i don't remember anything")
        assert not brain_fallback._check_confusion("i remember my birthday")


class TestBrainConversationMemory:
    """Test the new conversation memory features."""

    def test_learns_user_facts(self, brain_fallback):
        brain_fallback.think("My daughter Sarah visits me every Sunday", "joy")
        assert any("sarah" in f.lower() or "daughter" in f.lower()
                    for f in brain_fallback.user_facts)

    def test_learns_multiple_facts(self, brain_fallback):
        brain_fallback.think("I used to be a teacher", "neutral")
        brain_fallback.think("My cat is named Whiskers", "joy")
        assert len(brain_fallback.user_facts) >= 2

    def test_facts_in_context(self, brain_fallback):
        brain_fallback.think("I have a dog named Rex", "joy")
        # Facts should be learned, and context should include them
        assert len(brain_fallback.user_facts) >= 1
        context = brain_fallback._build_context("neutral", False, False)
        assert "remember" in context.lower() or "dog" in context.lower() or "rex" in context.lower()
