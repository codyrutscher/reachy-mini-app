"""Tests for the sing-along module."""

import pytest
from activities.singalong import SingAlong, is_singalong_trigger, SONGS, _SINGALONG_TRIGGERS


class TestSingalongTrigger:

    def test_detects_triggers(self):
        assert is_singalong_trigger("let's sing a song") is True
        assert is_singalong_trigger("sing along with me") is True
        assert is_singalong_trigger("karaoke time") is True

    def test_ignores_non_triggers(self):
        assert is_singalong_trigger("tell me a story") is False
        assert is_singalong_trigger("how's the weather") is False

    def test_case_insensitive(self):
        assert is_singalong_trigger("LET'S SING") is True

    def test_all_triggers_work(self):
        for t in _SINGALONG_TRIGGERS:
            assert is_singalong_trigger(t) is True, f"Missed trigger: {t}"


class TestSingAlong:

    def test_starts_inactive(self, singalong):
        assert not singalong.is_active

    def test_start_activates(self, singalong):
        prompt = singalong.start()
        assert singalong.is_active
        assert prompt  # non-empty string

    def test_start_picks_requested_song(self, singalong):
        prompt = singalong.start("sing Moon River")
        assert "Moon River" in prompt
        assert singalong._song_key == "moon_river"

    def test_start_picks_random_if_no_match(self, singalong):
        prompt = singalong.start("sing something")
        assert singalong.is_active
        assert singalong._song_key in SONGS

    def test_next_line_advances(self, singalong):
        singalong.start("You Are My Sunshine")
        # Line index starts at 1 after start (first line already given)
        assert singalong._line_index == 1
        prompt = singalong.next_line()
        assert singalong._line_index == 2
        assert prompt  # non-empty

    def test_next_line_contains_lyric(self, singalong):
        singalong.start("You Are My Sunshine")
        prompt = singalong.next_line()
        # The second line of the song should be in the prompt
        second_line = SONGS["you_are_my_sunshine"]["lines"][1]
        assert second_line in prompt

    def test_song_ends_after_all_lines(self, singalong):
        singalong.start("Moon River")
        song = SONGS["moon_river"]
        # start() delivered line[0], set index=1
        # next_line() delivers lines[1] through lines[8] (8 calls)
        # One more call after that triggers the wrap-up
        for _ in range(len(song["lines"])):
            prompt = singalong.next_line()
        assert not singalong.is_active
        assert "beautiful" in prompt.lower() or "lovely" in prompt.lower()

    def test_stop_deactivates(self, singalong):
        singalong.start()
        prompt = singalong.stop()
        assert not singalong.is_active
        assert "fun" in prompt.lower() or "anytime" in prompt.lower()

    def test_next_line_when_inactive_returns_empty(self, singalong):
        assert singalong.next_line() == ""

    def test_all_songs_have_lines(self):
        for key, song in SONGS.items():
            assert "title" in song, f"Song {key} missing title"
            assert "lines" in song, f"Song {key} missing lines"
            assert len(song["lines"]) >= 4, f"Song {key} has too few lines"
