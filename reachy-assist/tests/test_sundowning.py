"""Tests for the sundowning detection module."""

import pytest
from sundowning import check_sundowning, _SUNDOWNING_KEYWORDS


class TestSundowning:

    def test_detects_confusion_in_evening(self):
        assert check_sundowning("I don't know where am i", 18) is True

    def test_detects_agitation_in_evening(self):
        assert check_sundowning("leave me alone", 20) is True

    def test_ignores_keywords_before_4pm(self):
        assert check_sundowning("where am i", 10) is False
        assert check_sundowning("i'm scared", 15) is False

    def test_detects_at_exactly_4pm(self):
        assert check_sundowning("i'm scared", 16) is True

    def test_detects_at_late_night(self):
        assert check_sundowning("who are you", 23) is True

    def test_no_keywords_returns_false(self):
        assert check_sundowning("I had a lovely dinner", 19) is False
        assert check_sundowning("Tell me a story", 21) is False

    def test_case_insensitive(self):
        assert check_sundowning("WHO ARE YOU", 18) is True
        assert check_sundowning("I Don't Understand", 17) is True

    def test_empty_text(self):
        assert check_sundowning("", 20) is False

    def test_all_keywords_detected_in_evening(self):
        """Every keyword in the list should be detected after 4pm."""
        for kw in _SUNDOWNING_KEYWORDS:
            assert check_sundowning(kw, 18) is True, f"Missed keyword: {kw}"

    def test_all_keywords_ignored_before_4pm(self):
        """No keyword should trigger before 4pm."""
        for kw in _SUNDOWNING_KEYWORDS:
            assert check_sundowning(kw, 12) is False, f"False positive: {kw}"

    def test_keyword_embedded_in_sentence(self):
        assert check_sundowning("I just don't understand what's going on", 19) is True

    def test_boundary_hour_15(self):
        """3pm (hour=15) should NOT trigger."""
        assert check_sundowning("i'm scared", 15) is False
