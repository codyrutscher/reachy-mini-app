"""Tests for the RAG memory system."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def memory_db(tmp_path, monkeypatch):
    """Set up a temp memory database."""
    monkeypatch.setenv("REACHY_MEMORY_DB", str(tmp_path / "test_memory.db"))
    # Ensure no OPENAI_API_KEY so we use hash fallback in tests
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import importlib
    import memory
    # Reset module-level globals so each test gets a fresh embedder
    memory._embedder = None
    memory._embed_backend = None
    memory.EMBED_DIM = 384
    memory._local = __import__("threading").local()
    importlib.reload(memory)
    memory.init_memory_db()
    return memory


class TestMemoryStore:

    def test_store_and_recall(self, memory_db):
        mem = memory_db
        mem.store_memory("Patient's daughter is named Sarah", memory_type="fact")
        results = mem.recall("Tell me about their family")
        assert len(results) >= 1
        assert "sarah" in results[0]["content"].lower()

    def test_no_duplicates(self, memory_db):
        mem = memory_db
        id1 = mem.store_memory("Patient loves gardening", memory_type="fact")
        id2 = mem.store_memory("Patient loves gardening", memory_type="fact")
        # Should return same ID (deduped)
        assert id1 == id2

    def test_recall_by_type(self, memory_db):
        mem = memory_db
        mem.store_memory("Patient takes aspirin daily", memory_type="event")
        mem.store_memory("Patient's cat is named Mittens", memory_type="fact")
        results = mem.recall("medication", memory_type="event")
        assert all(r["memory_type"] == "event" for r in results)

    def test_recall_empty(self, memory_db):
        mem = memory_db
        results = mem.recall("anything at all")
        assert results == []

    def test_importance_scoring(self, memory_db):
        mem = memory_db
        mem.store_memory("Minor note", memory_type="fact", importance=0.2)
        mem.store_memory("Critical health info: patient has diabetes",
                         memory_type="fact", importance=0.9)
        results = mem.recall("health condition", top_k=2)
        if len(results) == 2:
            # Higher importance should score higher
            assert results[0]["importance"] >= results[1]["importance"]


class TestMemoryContext:

    def test_build_memory_context(self, memory_db):
        mem = memory_db
        mem.store_memory("Patient's daughter Sarah visits every Sunday", memory_type="fact")
        mem.store_memory("Patient used to be a teacher", memory_type="fact")
        mem.store_memory("Patient took medication this morning", memory_type="event")
        context = mem.build_memory_context("Tell me about yourself")
        assert isinstance(context, str)
        assert len(context) > 0

    def test_empty_context(self, memory_db):
        mem = memory_db
        context = mem.build_memory_context("random query")
        assert context == ""


class TestSessionSummary:

    def test_save_and_get_summary(self, memory_db):
        mem = memory_db
        mem.save_session_summary(
            summary="10 interactions, mostly happy",
            mood_distribution={"joy": 7, "neutral": 3},
            facts_learned=["name is Margaret"],
            duration_minutes=15.5,
        )
        summaries = mem.get_recent_summaries()
        assert len(summaries) == 1
        assert "happy" in summaries[0]["summary"]

    def test_multiple_summaries(self, memory_db):
        mem = memory_db
        mem.save_session_summary(summary="Session 1")
        mem.save_session_summary(summary="Session 2")
        mem.save_session_summary(summary="Session 3")
        summaries = mem.get_recent_summaries(limit=2)
        assert len(summaries) == 2


class TestConversationProcessing:

    def test_process_family_mention(self, memory_db):
        mem = memory_db
        mem.process_conversation_turn(
            "My daughter Sarah visits me every Sunday",
            "That's lovely!",
            "joy",
        )
        results = mem.recall("family")
        assert len(results) >= 1

    def test_process_emotional_moment(self, memory_db):
        mem = memory_db
        mem.process_conversation_turn(
            "I really miss my husband, he passed away last year",
            "I'm so sorry for your loss",
            "sadness",
        )
        results = mem.recall("loss", memory_type="event")
        assert len(results) >= 1

    def test_process_care_event(self, memory_db):
        mem = memory_db
        mem.process_conversation_turn(
            "I took my medication this morning",
            "Great job!",
            "neutral",
        )
        results = mem.recall("medication", memory_type="event")
        assert len(results) >= 1


class TestMemoryStats:

    def test_stats_empty(self, memory_db):
        mem = memory_db
        stats = mem.get_memory_stats()
        assert stats["total_memories"] == 0

    def test_stats_with_data(self, memory_db):
        mem = memory_db
        mem.store_memory("Fact 1", memory_type="fact")
        mem.store_memory("Event 1", memory_type="event")
        mem.store_memory("Event 2", memory_type="event")
        stats = mem.get_memory_stats()
        assert stats["total_memories"] == 3
        assert stats["by_type"]["fact"] == 1
        assert stats["by_type"]["event"] == 2
