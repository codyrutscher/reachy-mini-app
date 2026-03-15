"""Tests for the emotion detection module."""

import pytest


class TestKeywordEmotionDetector:
    """Test the keyword-based emotion backend."""

    def test_empty_text_returns_neutral(self, emotion_detector):
        assert emotion_detector.detect("") == "neutral"

    def test_detects_joy(self, emotion_detector):
        assert emotion_detector.detect("I'm so happy today!") == "joy"
        assert emotion_detector.detect("That's wonderful news") == "joy"
        assert emotion_detector.detect("I love spending time with my grandchild") == "joy"

    def test_detects_sadness(self, emotion_detector):
        assert emotion_detector.detect("I feel so sad and lonely") == "sadness"
        assert emotion_detector.detect("I miss my husband who passed away") == "sadness"
        assert emotion_detector.detect("I feel like a burden to everyone") == "sadness"

    def test_detects_anger(self, emotion_detector):
        assert emotion_detector.detect("I'm so angry and frustrated") == "anger"
        assert emotion_detector.detect("Nobody listens to me, it's unfair") == "anger"

    def test_detects_fear(self, emotion_detector):
        assert emotion_detector.detect("I'm scared about my surgery") == "fear"
        assert emotion_detector.detect("I'm worried about my test results") == "fear"
        assert emotion_detector.detect("I feel dizzy and confused") == "fear"

    def test_detects_surprise(self, emotion_detector):
        assert emotion_detector.detect("Wow, I can't believe it!") == "surprise"
        assert emotion_detector.detect("That's really unexpected, no way!") == "surprise"

    def test_detects_disgust(self, emotion_detector):
        assert emotion_detector.detect("That food was disgusting and gross") == "disgust"

    def test_neutral_for_ambiguous(self, emotion_detector):
        assert emotion_detector.detect("The weather is okay") == "neutral"
        assert emotion_detector.detect("I had lunch") == "neutral"

    def test_strongest_emotion_wins(self, emotion_detector):
        # "happy" + "glad" + "wonderful" (3 joy) vs "sad" (1 sadness)
        result = emotion_detector.detect("I'm happy and glad, it's wonderful even though I was sad")
        assert result == "joy"

    def test_eldercare_specific_keywords(self, emotion_detector):
        """Ensure eldercare-specific keywords are detected."""
        assert emotion_detector.detect("I used to be able to walk, now I can't do anything") == "sadness"
        assert emotion_detector.detect("My grandson visited for my birthday, I'm so proud") == "joy"
        assert emotion_detector.detect("I'm nervous about going to the hospital") == "fear"
