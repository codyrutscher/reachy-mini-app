"""Tests for the pain tracker module."""

import pytest
from health.pain_tracker import detect_pain, KEYWORDS


class TestPainDetection:

    def test_detects_pain_keywords(self):
        assert detect_pain("my back hurts") is True
        assert detect_pain("I have a lot of pain today") is True
        assert detect_pain("my knee is sore") is True

    def test_ignores_non_pain(self):
        assert detect_pain("I feel great today") is False
        assert detect_pain("tell me a joke") is False
        assert detect_pain("what's for lunch") is False

    def test_case_insensitive(self):
        assert detect_pain("MY BACK HURTS") is True
        assert detect_pain("Aching all over") is True

    def test_all_keywords_detected(self):
        for kw in KEYWORDS:
            assert detect_pain(f"I have {kw} in my leg") is True, f"Missed: {kw}"

    def test_empty_text(self):
        assert detect_pain("") is False

    def test_keyword_embedded_in_sentence(self):
        assert detect_pain("there's a burning sensation in my arm") is True
        assert detect_pain("my shoulder is really stiff today") is True
