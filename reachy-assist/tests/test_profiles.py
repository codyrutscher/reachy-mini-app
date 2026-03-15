"""Tests for the patient profiles module."""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from profiles import get_profile, list_profiles, get_care_response, PROFILES


class TestProfiles:

    def test_elderly_profile_exists(self):
        p = get_profile("elderly")
        assert p["name"] == "Elderly Care"
        assert p["tts_rate"] == 130

    def test_disabled_profile_exists(self):
        p = get_profile("disabled")
        assert p["name"] == "Disability Support"
        assert p["tts_rate"] == 145

    def test_unknown_profile_defaults_to_elderly(self):
        p = get_profile("nonexistent")
        assert p["name"] == "Elderly Care"

    def test_list_profiles(self):
        profiles = list_profiles()
        assert "elderly" in profiles
        assert "disabled" in profiles

    def test_elderly_has_required_keys(self):
        p = get_profile("elderly")
        required = ["system_prompt_addon", "tts_rate", "listen_duration",
                     "features", "exercise_types", "autonomy", "greeting"]
        for key in required:
            assert key in p, f"Missing key: {key}"

    def test_disabled_has_extra_care_words(self):
        p = get_profile("disabled")
        assert "extra_care_words" in p
        assert "equipment" in p["extra_care_words"]
        assert "mobility" in p["extra_care_words"]
        assert "pain" in p["extra_care_words"]
        assert "personal_care" in p["extra_care_words"]


class TestCareResponse:

    def test_equipment_care_response(self):
        p = get_profile("disabled")
        resp = get_care_response(p, "care", "my wheelchair is broken")
        assert resp is not None
        assert "caregiver" in resp.lower()

    def test_mobility_care_response(self):
        p = get_profile("disabled")
        resp = get_care_response(p, "care", "help me up please")
        assert resp is not None
        assert "mobility" in resp.lower() or "caregiver" in resp.lower()

    def test_pain_care_response(self):
        p = get_profile("disabled")
        resp = get_care_response(p, "care", "I'm in pain, it hurts")
        assert resp is not None
        assert "pain" in resp.lower() or "caregiver" in resp.lower()

    def test_no_care_response_for_elderly(self):
        p = get_profile("elderly")
        resp = get_care_response(p, "care", "my wheelchair is broken")
        assert resp is None

    def test_no_care_response_for_normal_text(self):
        p = get_profile("disabled")
        resp = get_care_response(p, "care", "the weather is nice today")
        assert resp is None
