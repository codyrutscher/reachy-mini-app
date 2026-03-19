"""Tests for the vision module (trigger detection only — no camera/API calls)."""

import pytest
from vision import is_vision_request, _VISION_TRIGGERS


class TestVisionTrigger:

    def test_detects_triggers(self):
        assert is_vision_request("what do you see") is True
        assert is_vision_request("look at this photo") is True
        assert is_vision_request("can you see this") is True
        assert is_vision_request("who is this") is True

    def test_ignores_non_triggers(self):
        assert is_vision_request("tell me a joke") is False
        assert is_vision_request("how are you today") is False
        assert is_vision_request("what time is it") is False

    def test_case_insensitive(self):
        assert is_vision_request("WHAT DO YOU SEE") is True
        assert is_vision_request("Look At This") is True

    def test_all_triggers_work(self):
        for t in _VISION_TRIGGERS:
            assert is_vision_request(t) is True, f"Missed trigger: {t}"

    def test_trigger_embedded_in_sentence(self):
        assert is_vision_request("hey reachy, what do you see here?") is True
        assert is_vision_request("can you look at this picture for me") is True

    def test_empty_text(self):
        assert is_vision_request("") is False
