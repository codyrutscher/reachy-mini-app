"""Speech Pattern Analysis — track linguistic markers of cognitive decline.

Analyzes transcripts for vocabulary diversity, sentence complexity,
word-finding pauses, and repetition patterns.
"""

import logging
import re
import time

logger = logging.getLogger(__name__)


class SpeechAnalyzer:
    """Tracks speech patterns over time for cognitive health monitoring."""

    def __init__(self, dashboard_url: str = "http://localhost:5555"):
        self._dashboard_url = dashboard_url
        self._daily_samples = []  # today's transcript samples
        self._weekly_stats = []  # daily summaries
        self._last_reset = time.strftime("%Y-%m-%d")

    def _reset_if_new_day(self):
        today = time.strftime("%Y-%m-%d")
        if today != self._last_reset:
            if self._daily_samples:
                summary = self._compute_daily_summary()
                self._weekly_stats.append(summary)
                if len(self._weekly_stats) > 30:
                    self._weekly_stats.pop(0)
            self._daily_samples = []
            self._last_reset = today

    def analyze_utterance(self, text: str) -> dict:
        """Analyze a single utterance for linguistic markers."""
        self._reset_if_new_day()
        if not text or len(text.strip()) < 3:
            return {}

        words = text.split()
        unique_words = set(w.lower().strip(".,!?") for w in words)

        metrics = {
            "word_count": len(words),
            "unique_words": len(unique_words),
            "vocabulary_diversity": round(len(unique_words) / max(len(words), 1), 2),
            "avg_word_length": round(sum(len(w) for w in words) / max(len(words), 1), 1),
            "sentence_count": max(1, text.count(".") + text.count("!") + text.count("?")),
            "filler_words": sum(1 for w in words if w.lower().strip(".,!?") in (
                "um", "uh", "er", "like", "you know", "well", "so", "hmm",
            )),
            "repetitions": self._count_repetitions(words),
            "word_finding_pauses": self._detect_word_finding(text),
            "timestamp": time.strftime("%H:%M:%S"),
        }

        self._daily_samples.append(metrics)
        return metrics

    def _count_repetitions(self, words: list) -> int:
        """Count repeated words/phrases (potential perseveration)."""
        count = 0
        for i in range(1, len(words)):
            if words[i].lower() == words[i - 1].lower() and len(words[i]) > 2:
                count += 1
        return count

    def _detect_word_finding(self, text: str) -> int:
        """Detect word-finding difficulty markers."""
        markers = [
            r"\b(that thing|the thing|what's it called|you know what i mean)\b",
            r"\b(the uh|the um|a uh|a um)\b",
            r"\.{3,}",  # trailing dots indicating pauses
            r"\b(whatchamacallit|thingamajig|whatnot)\b",
        ]
        count = 0
        lower = text.lower()
        for pattern in markers:
            count += len(re.findall(pattern, lower))
        return count

    def _compute_daily_summary(self) -> dict:
        if not self._daily_samples:
            return {}
        n = len(self._daily_samples)
        return {
            "date": self._last_reset,
            "utterances": n,
            "avg_word_count": round(sum(s["word_count"] for s in self._daily_samples) / n, 1),
            "avg_vocabulary_diversity": round(
                sum(s["vocabulary_diversity"] for s in self._daily_samples) / n, 2
            ),
            "total_filler_words": sum(s["filler_words"] for s in self._daily_samples),
            "total_repetitions": sum(s["repetitions"] for s in self._daily_samples),
            "total_word_finding": sum(s["word_finding_pauses"] for s in self._daily_samples),
        }

    def get_trends(self) -> dict:
        """Compare recent stats to baseline for cognitive decline indicators."""
        self._reset_if_new_day()
        if len(self._weekly_stats) < 3:
            return {"status": "collecting_data", "message": "Need more data to establish trends."}

        recent = self._weekly_stats[-3:]
        older = self._weekly_stats[:-3] if len(self._weekly_stats) > 3 else self._weekly_stats[:1]

        recent_diversity = sum(s.get("avg_vocabulary_diversity", 0) for s in recent) / len(recent)
        older_diversity = sum(s.get("avg_vocabulary_diversity", 0) for s in older) / len(older)

        recent_fillers = sum(s.get("total_filler_words", 0) for s in recent) / len(recent)
        older_fillers = sum(s.get("total_filler_words", 0) for s in older) / len(older)

        flags = []
        if older_diversity > 0 and recent_diversity < older_diversity * 0.8:
            flags.append("Vocabulary diversity has decreased by more than 20%")
        if older_fillers > 0 and recent_fillers > older_fillers * 1.5:
            flags.append("Filler word usage has increased significantly")

        return {
            "status": "warning" if flags else "stable",
            "flags": flags,
            "recent_diversity": round(recent_diversity, 2),
            "baseline_diversity": round(older_diversity, 2),
            "days_tracked": len(self._weekly_stats),
        }

    def get_status(self) -> dict:
        self._reset_if_new_day()
        return {
            "samples_today": len(self._daily_samples),
            "days_tracked": len(self._weekly_stats),
            "trends": self.get_trends(),
        }
