"""Tests for the interactive storytelling module."""

import pytest
from interactive_story import InteractiveStory, is_story_trigger, _STORY_TRIGGERS


class TestStoryTrigger:

    def test_detects_triggers(self):
        assert is_story_trigger("tell me a story about me") is True
        assert is_story_trigger("let's create a story") is True
        assert is_story_trigger("make me the hero") is True

    def test_ignores_non_triggers(self):
        assert is_story_trigger("tell me a joke") is False
        assert is_story_trigger("what time is it") is False

    def test_case_insensitive(self):
        assert is_story_trigger("INTERACTIVE STORY") is True

    def test_all_triggers_work(self):
        for t in _STORY_TRIGGERS:
            assert is_story_trigger(t) is True, f"Missed trigger: {t}"


class TestInteractiveStory:

    def test_starts_inactive(self, story):
        assert not story.is_active

    def test_start_activates(self, story):
        prompt = story.start()
        assert story.is_active
        assert story.turn_count == 0
        assert "Margaret" in prompt

    def test_start_includes_facts(self, story):
        prompt = story.start()
        assert "gardening" in prompt or "daughter" in prompt or "Sarah" in prompt

    def test_continue_story_advances(self, story):
        story.start()
        prompt = story.continue_story("I'll go through the garden gate")
        assert story.turn_count == 1
        assert story.is_active
        assert "Margaret" in prompt

    def test_continue_records_choice(self, story):
        story.start()
        story.continue_story("open the door")
        assert len(story.turns) == 1
        assert story.turns[0] == ("patient", "open the door")

    def test_story_wraps_up_after_max_turns(self, story):
        story.start()
        for i in range(story.max_turns - 1):
            prompt = story.continue_story(f"choice {i}")
            assert story.is_active
        # Final turn
        prompt = story.continue_story("final choice")
        assert not story.is_active
        assert "Margaret" in prompt
        assert "hero" in prompt.lower() or "ending" in prompt.lower()

    def test_record_narration(self, story):
        story.start()
        story.record_narration("Once upon a time...")
        assert ("narrator", "Once upon a time...") in story.turns

    def test_default_patient_name(self):
        s = InteractiveStory()
        assert s.patient_name == "our hero"

    def test_save_with_no_turns(self, story, monkeypatch):
        """Save with empty turns should not crash."""
        import sys, types
        fake = types.ModuleType("db_supabase")
        fake.is_available = lambda: True
        fake.save_fact = lambda *a, **kw: None
        fake.save_conversation = lambda *a, **kw: None
        monkeypatch.setitem(sys.modules, "db_supabase", fake)
        story.save()  # should not raise

    def test_save_with_turns(self, story, monkeypatch):
        """Save should call Supabase with story content."""
        import sys, types
        saved = []
        fake = types.ModuleType("db_supabase")
        fake.is_available = lambda: True
        fake.save_fact = lambda *a, **kw: saved.append(("fact", a))
        fake.save_conversation = lambda *a, **kw: saved.append(("conv", a))
        monkeypatch.setitem(sys.modules, "db_supabase", fake)

        story.start()
        story.record_narration("The adventure begins...")
        story.continue_story("go left")
        story.save()
        assert len(saved) == 2  # one fact + one conversation
