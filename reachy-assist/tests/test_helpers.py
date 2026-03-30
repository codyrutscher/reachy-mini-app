"""Tests for helper modules: jokes, affirmations, companion, datetime_helper."""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestJokes:

    def test_tell_joke_returns_string(self):
        from activities.jokes import tell_joke
        joke = tell_joke()
        assert isinstance(joke, str)
        assert len(joke) > 10

    def test_tell_joke_no_repeats(self):
        from activities.jokes import tell_joke, _told
        _told.clear()
        jokes = set()
        for _ in range(10):
            jokes.add(tell_joke())
        assert len(jokes) == 10  # all unique

    def test_joke_setup_punchline(self):
        from activities.jokes import tell_joke_setup_punchline
        setup, punchline = tell_joke_setup_punchline()
        assert isinstance(setup, str)
        assert isinstance(punchline, str)
        assert "?" in setup  # setup is a question


class TestAffirmations:

    def test_get_affirmation(self):
        from activities.affirmations import get_affirmation
        aff = get_affirmation()
        assert isinstance(aff, str)
        assert len(aff) > 10

    def test_get_motivation(self):
        from activities.affirmations import get_motivation
        mot = get_motivation()
        assert isinstance(mot, str)
        assert len(mot) > 10

    def test_get_gratitude_prompt(self):
        from activities.affirmations import get_gratitude_prompt
        prompt = get_gratitude_prompt()
        assert "?" in prompt  # should be a question

    def test_daily_affirmation_consistent(self):
        from activities.affirmations import get_daily_affirmation
        a1 = get_daily_affirmation()
        a2 = get_daily_affirmation()
        assert a1 == a2  # same within one day

    def test_morning_affirmation(self):
        from activities.affirmations import morning_affirmation
        result = morning_affirmation()
        assert "affirmation" in result.lower()


class TestCompanion:

    def test_get_conversation_starter(self):
        from brain.companion import get_conversation_starter, _used_topics
        _used_topics.clear()
        starter = get_conversation_starter()
        assert isinstance(starter, str)
        assert "?" in starter  # should be a question

    def test_no_repeat_topics(self):
        from brain.companion import get_conversation_starter, _used_topics
        _used_topics.clear()
        starters = []
        for _ in range(5):
            starters.append(get_conversation_starter())
        # All should be different (different topics)
        assert len(set(starters)) == 5

    def test_list_topics(self):
        from brain.companion import list_topics
        result = list_topics()
        assert "travel" in result.lower()
        assert "food" in result.lower()
        assert "music" in result.lower()

    def test_get_topic_starter(self):
        from brain.companion import get_topic_starter
        starter = get_topic_starter("food")
        assert isinstance(starter, str)
        assert "?" in starter


class TestDatetimeHelper:

    def test_get_time_response(self):
        from core.datetime_helper import get_time_response
        result = get_time_response()
        assert "it's" in result.lower()
        assert ("am" in result.lower() or "pm" in result.lower())

    def test_get_date_response(self):
        from core.datetime_helper import get_date_response
        result = get_date_response()
        assert "today is" in result.lower()

    def test_get_day_response(self):
        from core.datetime_helper import get_day_response
        result = get_day_response()
        assert "today is" in result.lower()
        # Should contain a day name
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        assert any(d in result.lower() for d in days)

    def test_get_full_briefing(self):
        from core.datetime_helper import get_full_briefing
        result = get_full_briefing()
        assert "it's" in result.lower()

    def test_holidays_dict(self):
        from core.datetime_helper import HOLIDAYS
        assert (12, 25) in HOLIDAYS
        assert HOLIDAYS[(12, 25)] == "Christmas Day"
        assert (1, 1) in HOLIDAYS
