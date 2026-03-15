"""Tests for the daily check-in module."""

import pytest


class TestDailyCheckIn:

    def test_starts_inactive(self, checkin):
        assert not checkin.is_active

    def test_start_activates(self, checkin):
        result = checkin.start()
        assert checkin.is_active
        assert "check-in" in result.lower() or "sleep" in result.lower()
        assert checkin.step == 0

    def test_process_good_answer(self, checkin):
        checkin.start()
        response = checkin.process_answer("I slept great, really well")
        assert checkin.results.get("sleep") == "good"
        assert checkin.step == 1
        # Should contain followup + next question
        assert "pain" in response.lower() or "discomfort" in response.lower()

    def test_process_bad_answer(self, checkin):
        checkin.start()
        checkin.process_answer("Terrible, I didn't sleep at all")
        assert checkin.results.get("sleep") == "bad"

    def test_process_neutral_answer(self, checkin):
        checkin.start()
        checkin.process_answer("It was alright I guess")
        assert checkin.results.get("sleep") == "neutral"

    def test_full_checkin_flow(self, checkin):
        checkin.start()
        # Answer all 6 questions
        answers = [
            "I slept well",           # sleep -> good
            "No pain at all",         # pain -> good
            "I'm feeling happy",      # mood -> good
            "Yes I had breakfast",    # eating -> good
            "I talked to my daughter",# social -> good
            "I went for a walk",      # movement -> good
        ]
        for answer in answers:
            response = checkin.process_answer(answer)

        # Should be done
        assert not checkin.is_active
        assert len(checkin.results) == 6
        # Last response should contain summary
        assert "check-in done" in response.lower() or "noticed" in response.lower()

    def test_negation_handling(self, checkin):
        """'no pain' should be classified as good, not bad."""
        checkin.start()
        checkin.process_answer("no pain, I feel fine")
        assert checkin.results.get("sleep") == "good"

    def test_classify_method(self, checkin):
        assert checkin._classify("I slept great") == "good"
        assert checkin._classify("terrible awful night") == "bad"
        assert checkin._classify("it was okay") == "neutral"
