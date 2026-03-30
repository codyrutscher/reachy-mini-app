"""Tests for conversational intelligence features in RealtimeConversation.

Tests the tracking logic (humor learning, emotional repair, engagement scoring,
topic avoidance, name detection, celebration detection, deep topic detection,
confusion recovery, energy trajectory, etc.) without needing a real WebSocket
or OpenAI API connection.
"""

import sys
import os
import types
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_convo(monkeypatch):
    """Create a RealtimeConversation with all backends mocked out."""
    # Mock heavy imports
    for mod_name in [
        "db_supabase", "memory", "vector_memory", "knowledge_graph",
        "temporal_patterns", "caregiver", "robot", "webapp",
        "music", "radio", "voice_clone", "night_mode", "photo_album",
        "ambient_movement", "freestyle_rap", "personalities", "metronome",
        "coding_assistant", "translator", "hand_tracker", "dance_routines",
        "chess_player", "home_monitor", "stargazing", "routine_coach",
        "sketch_render", "drawing", "gait_analysis", "speech_analysis",
        "nutrition", "attention_tracker", "adaptive_trivia", "video_call",
        "weather", "followups",
    ]:
        if mod_name not in sys.modules:
            monkeypatch.setitem(sys.modules, mod_name, types.ModuleType(mod_name))

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)

    from integration.realtime_conversation import RealtimeConversation
    convo = RealtimeConversation(
        system_prompt="You are a test bot.",
        patient_id="test-patient",
    )
    # Don't call _init_backend — we want a bare instance
    return convo


# ── Humor Learning ────────────────────────────────────────────────

class TestHumorLearning:

    def test_humor_hit_recorded_on_joy_with_laugh_words(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._current_topic = "family"
        # Simulate a joy emotion detection
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "joy")
        convo._process_user_transcript("haha that's so funny")
        assert "family" in convo._humor_hits

    def test_humor_not_recorded_without_laugh_words(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._current_topic = "food"
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "joy")
        convo._process_user_transcript("I love pasta")
        assert "food" not in convo._humor_hits

    def test_humor_not_recorded_on_sadness(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._current_topic = "family"
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "sadness")
        convo._process_user_transcript("haha that's funny")
        assert len(convo._humor_hits) == 0

    def test_humor_hits_capped_at_20(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "joy")
        for i in range(25):
            convo._current_topic = f"topic_{i}"
            convo._process_user_transcript("haha good one")
        assert len(convo._humor_hits) == 20


# ── Deep Topic Detection ─────────────────────────────────────────

class TestDeepTopicDetection:

    def test_deep_topic_activated(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "sadness")
        convo._process_user_transcript("My wife passed away last year")
        assert convo._deep_topic_active is True

    def test_deep_topic_clears_on_positive_mood(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "sadness")
        convo._process_user_transcript("My mother passed away")
        assert convo._deep_topic_active is True
        # Now mood shifts to joy
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "joy")
        convo._process_user_transcript("But I have great memories of her")
        assert convo._deep_topic_active is False

    def test_deep_topic_stays_active_during_sadness(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "sadness")
        convo._process_user_transcript("I lost my husband")
        convo._process_user_transcript("I miss him every day")
        assert convo._deep_topic_active is True


# ── Engagement Scoring ────────────────────────────────────────────

class TestEngagementScoring:

    def test_engagement_score_recorded(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("I went to the store today and bought some flowers")
        assert len(convo._engagement_scores) == 1
        assert convo._engagement_scores[0] >= 0

    def test_short_reply_low_engagement(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("ok")
        assert convo._engagement_scores[0] < 3

    def test_long_reply_higher_engagement(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "joy")
        convo._process_user_transcript(
            "Oh let me tell you about my wonderful day at the garden "
            "where I planted roses and tomatoes and had a lovely time"
        )
        assert convo._engagement_scores[0] > 2

    def test_engagement_scores_capped(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        for i in range(35):
            convo._process_user_transcript(f"Message number {i}")
        assert len(convo._engagement_scores) == 30

    def test_energy_trajectory_tracked(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("hello there my friend")
        assert len(convo._energy_trajectory) == 1
        assert convo._energy_trajectory[0] == 4  # 4 words


# ── Topic Mood Mapping ───────────────────────────────────────────

class TestTopicMoodMapping:

    def test_topic_mood_recorded(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._current_topic = "health"
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "sadness")
        convo._process_user_transcript("My back hurts today")
        assert "health" in convo._topic_mood_map
        assert convo._topic_mood_map["health"] == ["sadness"]

    def test_general_topic_not_tracked(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._current_topic = "general"
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("Hello")
        assert "general" not in convo._topic_mood_map

    def test_topic_mood_capped(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._current_topic = "family"
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "joy")
        for _ in range(20):
            convo._process_user_transcript("I love my family")
        assert len(convo._topic_mood_map["family"]) == 15


# ── Name Detection ───────────────────────────────────────────────

class TestNameDetection:

    def test_detects_my_daughter_name(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("My daughter Sarah came to visit")
        assert "Sarah" in convo._mentioned_names

    def test_detects_my_friend_name(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("My friend Tom called me yesterday")
        assert "Tom" in convo._mentioned_names

    def test_detects_named_person(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("Her name is Margaret")
        assert "Margaret" in convo._mentioned_names

    def test_no_false_positive_on_lowercase(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("my daughter went to the store")
        assert len(convo._mentioned_names) == 0


# ── Confusion Recovery ───────────────────────────────────────────

class TestConfusionRecovery:

    def test_confusion_detected(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("What? I don't understand")
        assert convo._confusion_count >= 1

    def test_confusion_resets_on_normal_reply(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("Huh? What do you mean?")
        assert convo._confusion_count >= 1
        convo._process_user_transcript("Oh I see, that makes sense now, thank you for explaining")
        assert convo._confusion_count == 0

    def test_confusion_accumulates(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("What?")
        convo._process_user_transcript("I don't understand")
        assert convo._confusion_count >= 2


# ── Celebration Detection ────────────────────────────────────────

class TestCelebrationDetection:

    def test_celebration_on_trigger(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "joy")
        convo._process_user_transcript("Guess what, I walked today all by myself!")
        assert convo._celebration_active is True

    def test_celebration_on_joy_with_long_text(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "joy")
        convo._process_user_transcript(
            "My granddaughter came to visit and we had the most wonderful time together"
        )
        assert convo._celebration_active is True

    def test_no_celebration_on_short_neutral(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("ok fine")
        assert convo._celebration_active is False


# ── Silence / Flat Response Tracking ─────────────────────────────

class TestSilenceTracking:

    def test_silence_increments_on_short_replies(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("ok")
        convo._process_user_transcript("fine")
        convo._process_user_transcript("yes")
        assert convo._silence_turns >= 3

    def test_silence_resets_on_real_reply(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("ok")
        convo._process_user_transcript("fine")
        convo._process_user_transcript("Actually let me tell you about my day at the park")
        assert convo._silence_turns == 0


# ── Flat Emotion Vocabulary ──────────────────────────────────────

class TestFlatEmotionVocabulary:

    def test_flat_emotion_increments(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("I'm fine")
        convo._process_user_transcript("I'm okay")
        convo._process_user_transcript("I'm alright")
        assert convo._flat_emotion_count >= 3

    def test_flat_emotion_resets_on_expressive_reply(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("I'm fine")
        convo._process_user_transcript("I'm okay")
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "joy")
        convo._process_user_transcript("Oh I just remembered something wonderful that happened!")
        assert convo._flat_emotion_count == 0


# ── Repeated Story Detection ────────────────────────────────────

class TestRepeatedStoryDetection:

    def test_repeated_story_counted(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        story = "When I was young we used to go fishing every summer at the lake"
        convo._process_user_transcript(story)
        convo._process_user_transcript(story)
        # Check the fingerprint was counted
        words = story.strip().split()
        fp = " ".join(w.lower() for w in words[:6])
        assert convo._repeated_stories.get(fp, 0) >= 2

    def test_short_messages_not_fingerprinted(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("hello")
        convo._process_user_transcript("hello")
        assert len(convo._repeated_stories) == 0


# ── Question Fatigue (assistant side) ────────────────────────────

class TestQuestionFatigue:

    def test_consecutive_questions_tracked(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._process_assistant_transcript("How are you feeling today?")
        convo._process_assistant_transcript("Did you sleep well?")
        convo._process_assistant_transcript("What would you like to do?")
        assert convo._consecutive_questions >= 3

    def test_question_count_resets_on_statement(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._process_assistant_transcript("How are you?")
        convo._process_assistant_transcript("How did you sleep?")
        convo._process_assistant_transcript("That sounds really lovely.")
        assert convo._consecutive_questions == 0


# ── Encouragement Tracking (assistant side) ──────────────────────

class TestEncouragementTracking:

    def test_encouragement_turn_recorded(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._interaction_count = 5
        convo._process_assistant_transcript("That's wonderful, I'm so proud of you!")
        assert convo._last_encouragement_turn == 5

    def test_no_encouragement_on_normal_response(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._interaction_count = 10
        convo._process_assistant_transcript("Tell me more about that.")
        assert convo._last_encouragement_turn == 0


# ── Build Full Instructions Context ──────────────────────────────

class TestBuildFullInstructions:

    def test_includes_base_prompt(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        result = convo._build_full_instructions()
        assert "test bot" in result

    def test_includes_patient_name(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._user_name = "Margaret"
        result = convo._build_full_instructions()
        assert "Margaret" in result

    def test_includes_humor_context(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._humor_hits = ["family", "family", "pets"]
        result = convo._build_full_instructions()
        assert "HUMOR" in result
        assert "family" in result

    def test_includes_deep_topic_context(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._deep_topic_active = True
        result = convo._build_full_instructions()
        assert "DEEP MOMENT" in result

    def test_includes_question_fatigue(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._consecutive_questions = 4
        result = convo._build_full_instructions()
        assert "QUESTION FATIGUE" in result

    def test_includes_celebration(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._celebration_active = True
        result = convo._build_full_instructions()
        assert "CELEBRATION" in result

    def test_includes_confusion_context(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._confusion_count = 2
        result = convo._build_full_instructions()
        assert "CONFUSION" in result

    def test_includes_silence_context(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._silence_turns = 5
        result = convo._build_full_instructions()
        assert "SILENCE" in result

    def test_includes_topic_avoidance(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._topic_mood_map = {"health": ["sadness", "sadness", "sadness", "anger"]}
        result = convo._build_full_instructions()
        assert "TOPIC AVOIDANCE" in result
        assert "health" in result

    def test_includes_mentioned_names(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._mentioned_names = {"Sarah": "my daughter Sarah"}
        result = convo._build_full_instructions()
        assert "Sarah" in result
        assert "PEOPLE" in result

    def test_includes_engagement_low(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._engagement_scores = [1.0, 1.5, 2.0, 1.0, 1.5]
        result = convo._build_full_instructions()
        assert "ENGAGEMENT" in result
        assert "Low" in result

    def test_includes_engagement_high(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._engagement_scores = [8.0, 9.0, 8.5, 9.0, 8.0]
        result = convo._build_full_instructions()
        assert "ENGAGEMENT" in result
        assert "highly engaged" in result

    def test_includes_encouragement_nudge(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._interaction_count = 15
        convo._last_encouragement_turn = 0
        result = convo._build_full_instructions()
        assert "ENCOURAGEMENT" in result

    def test_includes_emotional_state_sadness(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._mood_history = ["sadness", "sadness", "sadness", "sadness", "sadness", "sadness"]
        result = convo._build_full_instructions()
        assert "EMOTIONAL STATE" in result

    def test_includes_pacing_short(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._chat_history = [
            {"role": "user", "content": "ok"},
            {"role": "assistant", "content": "How are you?"},
            {"role": "user", "content": "fine"},
            {"role": "assistant", "content": "What's up?"},
            {"role": "user", "content": "nothing"},
            {"role": "assistant", "content": "Want to chat?"},
            {"role": "user", "content": "sure"},
            {"role": "assistant", "content": "Great!"},
        ]
        result = convo._build_full_instructions()
        assert "PACING" in result

    def test_includes_flat_emotion_vocab(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._flat_emotion_count = 4
        result = convo._build_full_instructions()
        assert "EMOTIONAL VOCABULARY" in result

    def test_includes_momentum(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._topic_flow_turns = 4
        result = convo._build_full_instructions()
        assert "MOMENTUM" in result

    def test_includes_generational_context(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._patient_birth_year = 1945
        result = convo._build_full_instructions()
        assert "GENERATIONAL" in result
        assert "Elvis" in result

    def test_includes_repetition_avoidance(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._chat_history = [
            {"role": "assistant", "content": "That sounds nice."},
            {"role": "user", "content": "yeah"},
            {"role": "assistant", "content": "That is interesting."},
            {"role": "user", "content": "yeah"},
            {"role": "assistant", "content": "That reminds me."},
            {"role": "user", "content": "yeah"},
        ]
        result = convo._build_full_instructions()
        assert "VARIETY" in result


# ── Expanded Trigger Words ───────────────────────────────────────

class TestExpandedTriggers:

    def test_deep_trigger_passed_on(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "sadness")
        convo._process_user_transcript("She passed on last winter")
        assert convo._deep_topic_active is True

    def test_deep_trigger_my_late(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "sadness")
        convo._process_user_transcript("My late husband loved this song")
        assert convo._deep_topic_active is True

    def test_deep_trigger_nobody_visits(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "sadness")
        convo._process_user_transcript("I don't want to be alone anymore")
        assert convo._deep_topic_active is True

    def test_celebration_trigger_i_finally(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "joy")
        convo._process_user_transcript("I finally managed to walk to the garden today")
        assert convo._celebration_active is True

    def test_celebration_trigger_grandchild(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "joy")
        convo._process_user_transcript("My grandchild is coming to visit this weekend")
        assert convo._celebration_active is True

    def test_confusion_signal_slow_down(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("Can you slow down please")
        assert convo._confusion_count >= 1

    def test_humor_word_classic(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._current_topic = "jokes"
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "joy")
        convo._process_user_transcript("Oh that's classic, you crack me up")
        assert "jokes" in convo._humor_hits


# ── Expanded Name Detection ──────────────────────────────────────

class TestExpandedNameDetection:

    def test_detects_name_first_pattern(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("Sarah, my daughter, came to visit")
        assert "Sarah" in convo._mentioned_names

    def test_detects_late_husband(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("My late husband Robert loved fishing")
        assert "Robert" in convo._mentioned_names

    def test_detects_nurse_name(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("Nurse Karen is very kind to me")
        assert "Karen" in convo._mentioned_names

    def test_detects_grandson(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("My grandson Tommy plays soccer")
        assert "Tommy" in convo._mentioned_names

    def test_detects_buddy(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        convo._process_user_transcript("My buddy Frank and I used to fish together")
        assert "Frank" in convo._mentioned_names


# ── Generational Context Expanded ────────────────────────────────

class TestGenerationalContextExpanded:

    def test_1920s_generation(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._patient_birth_year = 1925
        result = convo._build_full_instructions()
        assert "Depression" in result or "WWII" in result

    def test_1970s_generation(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._patient_birth_year = 1975
        result = convo._build_full_instructions()
        assert "MTV" in result or "Michael Jackson" in result

    def test_1950s_generation(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._patient_birth_year = 1955
        result = convo._build_full_instructions()
        assert "Beatles" in result or "Motown" in result


# ── Energy Trajectory Context ────────────────────────────────────

class TestEnergyTrajectoryContext:

    def test_dropping_energy_detected(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        # First half: long replies, second half: short
        convo._energy_trajectory = [20, 25, 18, 22, 3, 2, 4, 3]
        result = convo._build_full_instructions()
        assert "ENERGY" in result
        assert "dropping" in result

    def test_rising_energy_detected(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._energy_trajectory = [3, 2, 4, 3, 20, 25, 18, 22]
        result = convo._build_full_instructions()
        assert "ENERGY" in result
        assert "rising" in result

    def test_no_energy_context_when_stable(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._energy_trajectory = [10, 11, 10, 12, 10, 11]
        result = convo._build_full_instructions()
        assert "ENERGY" not in result


# ── Retold Story Context ─────────────────────────────────────────

class TestRetoldStoryContext:

    def test_retold_story_in_instructions(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "neutral")
        story = "When I was young we used to go fishing every summer at the lake"
        convo._process_user_transcript(story)
        convo._process_user_transcript(story)
        # Now the last user message is the retold story
        result = convo._build_full_instructions()
        assert "RETOLD STORY" in result


# ── Gentle Challenge Context ─────────────────────────────────────

class TestGentleChallengeContext:

    def test_gentle_challenge_when_engaged(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._engagement_scores = [8.0, 8.5, 9.0, 8.0, 8.5]
        convo._mood_history = ["joy"]
        convo._deep_topic_active = False
        convo._interaction_count = 15  # divisible by 15
        result = convo._build_full_instructions()
        assert "GENTLE CHALLENGE" in result

    def test_no_challenge_during_deep_topic(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._engagement_scores = [8.0, 8.5, 9.0, 8.0, 8.5]
        convo._mood_history = ["joy"]
        convo._deep_topic_active = True
        convo._interaction_count = 15
        result = convo._build_full_instructions()
        assert "GENTLE CHALLENGE" not in result


# ── Session Phase Context ────────────────────────────────────────

class TestSessionPhaseContext:

    def test_early_session_phase(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._interaction_count = 2
        result = convo._build_full_instructions()
        assert "SESSION PHASE" in result
        assert "start" in result

    def test_late_session_phase(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._interaction_count = 35
        result = convo._build_full_instructions()
        assert "SESSION PHASE" in result
        assert "while" in result


# ── Mood Shift Detection ─────────────────────────────────────────

class TestMoodShiftDetection:

    def test_mood_shift_detected(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._mood_history = ["joy", "joy", "sadness", "sadness"]
        result = convo._build_full_instructions()
        assert "MOOD SHIFT" in result

    def test_no_mood_shift_on_stable_mood(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._mood_history = ["joy", "joy", "joy", "joy"]
        result = convo._build_full_instructions()
        assert "MOOD SHIFT" not in result


# ── Time Awareness Context ───────────────────────────────────────

class TestTimeAwarenessContext:

    def test_time_awareness_present(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        result = convo._build_full_instructions()
        assert "TIME AWARENESS" in result


# ── Conversation Momentum ────────────────────────────────────────

class TestConversationMomentum:

    def test_momentum_tracked_on_flowing_topic(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._current_topic = "family"
        convo._prev_topic = "family"
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "joy")
        convo._process_user_transcript("Oh let me tell you more about my daughter and her kids")
        # Should increment since same topic, long reply, positive emotion
        assert convo._topic_flow_turns >= 1

    def test_momentum_resets_on_topic_change(self, monkeypatch):
        convo = _make_convo(monkeypatch)
        convo._current_topic = "family"
        convo._prev_topic = "food"
        convo._topic_flow_turns = 3
        monkeypatch.setattr(convo, "_detect_emotion", lambda t: "joy")
        convo._process_user_transcript("Oh let me tell you about something completely different now")
        assert convo._topic_flow_turns == 0
