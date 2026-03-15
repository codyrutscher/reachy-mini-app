"""Tests for the cognitive exercises module."""

import pytest


class TestCognitiveExercises:

    def test_starts_inactive(self, cognitive):
        assert not cognitive.is_active

    def test_list_games(self, cognitive):
        result = cognitive.list_games()
        assert "word association" in result.lower()
        assert "trivia" in result.lower()
        assert "story" in result.lower()
        assert "categories" in result.lower()
        assert "memory" in result.lower()

    def test_start_word_association(self, cognitive):
        result = cognitive.start_game("word association")
        assert cognitive.is_active
        assert cognitive.active_game == "word_association"
        assert "word" in result.lower()

    def test_play_word_association(self, cognitive):
        cognitive.start_game("word association")
        result = cognitive.play_turn("sunshine")
        assert cognitive.is_active
        assert "your turn" in result.lower() or "nice" in result.lower()

    def test_word_association_ends_after_8_turns(self, cognitive):
        cognitive.start_game("word association")
        for i in range(8):
            cognitive.play_turn(f"word{i}")
        assert not cognitive.is_active

    def test_start_trivia(self, cognitive):
        result = cognitive.start_game("trivia")
        assert cognitive.active_game == "trivia"
        assert "?" in result  # should contain a question

    def test_trivia_correct_answer(self, cognitive):
        cognitive.start_game("trivia")
        # First question is random, but we can answer with the known answer
        idx = cognitive.game_state["index"]
        answer = cognitive._TRIVIA[idx]["a"]
        result = cognitive.play_turn(answer)
        assert "right" in result.lower() or "correct" in result.lower() or "well done" in result.lower()

    def test_trivia_wrong_then_hint(self, cognitive):
        cognitive.start_game("trivia")
        result = cognitive.play_turn("completely wrong answer xyz")
        assert "hint" in result.lower()

    def test_start_categories(self, cognitive):
        result = cognitive.start_game("categories")
        assert cognitive.active_game == "categories"
        assert "category" in result.lower()

    def test_categories_counting(self, cognitive):
        cognitive.start_game("categories")
        result = cognitive.play_turn("apple")
        assert "1" in result
        result = cognitive.play_turn("banana")
        assert "2" in result

    def test_categories_done(self, cognitive):
        cognitive.start_game("categories")
        cognitive.play_turn("apple")
        cognitive.play_turn("done")
        assert not cognitive.is_active

    def test_start_memory_game(self, cognitive):
        result = cognitive.start_game("memory game")
        assert cognitive.active_game == "memory"
        assert "remember" in result.lower()

    def test_memory_game_scoring(self, cognitive):
        cognitive.start_game("memory game")
        items = cognitive.game_state["items"]
        # Remember all items
        result = cognitive.play_turn(" ".join(items))
        assert "all" in result.lower() or str(len(items)) in result

    def test_stop_game(self, cognitive):
        cognitive.start_game("trivia")
        result = cognitive.stop_game()
        assert not cognitive.is_active
        assert "fun" in result.lower()

    def test_start_story(self, cognitive):
        result = cognitive.start_game("story builder")
        assert cognitive.active_game == "story"
        assert "what happens next" in result.lower()

    def test_story_progresses(self, cognitive):
        cognitive.start_game("story builder")
        result = cognitive.play_turn("The cat found a golden key")
        assert cognitive.is_active
        assert "what happened next" in result.lower() or "love that" in result.lower()
