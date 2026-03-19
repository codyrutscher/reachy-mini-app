"""Tests for the behavioral anomaly detection module."""

import sys
import types
import pytest
from anomaly_detection import check_anomalies, build_baseline


def _make_fake_db(sessions):
    """Create a fake db_supabase module that returns the given sessions."""
    fake = types.ModuleType("db_supabase")
    fake.get_session_summaries = lambda pid, limit=14: sessions
    return fake


def _sample_sessions(n=7, interactions=20, duration=15.0, topics=3, sadness_pct=10):
    """Generate n fake session summaries with consistent stats."""
    sessions = []
    for _ in range(n):
        mood_dist = {"neutral": 70, "joy": 20 - sadness_pct, "sadness": sadness_pct}
        sessions.append({
            "interactions": interactions,
            "duration_minutes": duration,
            "topics_discussed": [f"topic_{i}" for i in range(topics)],
            "mood_distribution": mood_dist,
        })
    return sessions


class TestBuildBaseline:

    def test_returns_empty_with_few_sessions(self, monkeypatch):
        fake = _make_fake_db([{"interactions": 10}])
        monkeypatch.setitem(sys.modules, "db_supabase", fake)
        result = build_baseline("test")
        assert result == {}

    def test_builds_baseline_from_sessions(self, monkeypatch):
        sessions = _sample_sessions(n=5, interactions=20, duration=15.0)
        fake = _make_fake_db(sessions)
        monkeypatch.setitem(sys.modules, "db_supabase", fake)
        result = build_baseline("test")
        assert result["sessions"] == 5
        assert result["avg_interactions"] == 20.0
        assert result["avg_duration"] == 15.0

    def test_baseline_calculates_mood_pct(self, monkeypatch):
        sessions = _sample_sessions(n=4, sadness_pct=20)
        fake = _make_fake_db(sessions)
        monkeypatch.setitem(sys.modules, "db_supabase", fake)
        result = build_baseline("test")
        assert "sadness" in result["mood_pct"]
        assert result["mood_pct"]["sadness"] > 0


class TestCheckAnomalies:

    def test_no_anomalies_when_normal(self, monkeypatch):
        sessions = _sample_sessions(n=7, interactions=20, duration=15.0, topics=3)
        fake = _make_fake_db(sessions)
        monkeypatch.setitem(sys.modules, "db_supabase", fake)
        today = {"interactions": 18, "duration_minutes": 14, "topic_count": 3, "sadness_pct": 10}
        result = check_anomalies("test", today)
        assert result == []

    def test_flags_low_interactions(self, monkeypatch):
        sessions = _sample_sessions(n=7, interactions=20)
        fake = _make_fake_db(sessions)
        monkeypatch.setitem(sys.modules, "db_supabase", fake)
        today = {"interactions": 5, "duration_minutes": 15, "topic_count": 3, "sadness_pct": 10}
        result = check_anomalies("test", today)
        metrics = [a["metric"] for a in result]
        assert "interactions" in metrics

    def test_flags_short_duration(self, monkeypatch):
        sessions = _sample_sessions(n=7, duration=20.0)
        fake = _make_fake_db(sessions)
        monkeypatch.setitem(sys.modules, "db_supabase", fake)
        today = {"interactions": 20, "duration_minutes": 5, "topic_count": 3, "sadness_pct": 10}
        result = check_anomalies("test", today)
        metrics = [a["metric"] for a in result]
        assert "duration" in metrics

    def test_flags_low_topic_variety(self, monkeypatch):
        sessions = _sample_sessions(n=7, topics=5)
        fake = _make_fake_db(sessions)
        monkeypatch.setitem(sys.modules, "db_supabase", fake)
        today = {"interactions": 20, "duration_minutes": 15, "topic_count": 1, "sadness_pct": 10}
        result = check_anomalies("test", today)
        metrics = [a["metric"] for a in result]
        assert "topic_variety" in metrics

    def test_flags_mood_shift(self, monkeypatch):
        sessions = _sample_sessions(n=7, sadness_pct=5)
        fake = _make_fake_db(sessions)
        monkeypatch.setitem(sys.modules, "db_supabase", fake)
        today = {"interactions": 20, "duration_minutes": 15, "topic_count": 3, "sadness_pct": 60}
        result = check_anomalies("test", today)
        metrics = [a["metric"] for a in result]
        assert "mood_shift" in metrics

    def test_returns_empty_with_no_baseline(self, monkeypatch):
        fake = _make_fake_db([])  # no sessions
        monkeypatch.setitem(sys.modules, "db_supabase", fake)
        today = {"interactions": 5, "duration_minutes": 2, "topic_count": 0, "sadness_pct": 80}
        result = check_anomalies("test", today)
        assert result == []

    def test_returns_empty_with_no_today_stats(self, monkeypatch):
        sessions = _sample_sessions(n=7)
        fake = _make_fake_db(sessions)
        monkeypatch.setitem(sys.modules, "db_supabase", fake)
        assert check_anomalies("test", None) == []
        assert check_anomalies("test", {}) == []

    def test_anomaly_has_required_fields(self, monkeypatch):
        sessions = _sample_sessions(n=7, interactions=20)
        fake = _make_fake_db(sessions)
        monkeypatch.setitem(sys.modules, "db_supabase", fake)
        today = {"interactions": 3, "duration_minutes": 15, "topic_count": 3, "sadness_pct": 10}
        result = check_anomalies("test", today)
        for a in result:
            assert "metric" in a
            assert "message" in a
            assert "severity" in a
