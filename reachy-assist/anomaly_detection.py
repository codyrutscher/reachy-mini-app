"""Behavioral baseline & anomaly detection."""


def build_baseline(patient_id="default", days=14):
    """Build a baseline from the last N session summaries."""
    try:
        import db_supabase as _db
    except Exception:
        return {}
    sessions = _db.get_session_summaries(patient_id, limit=days)
    if len(sessions) < 3:
        return {}
    interactions = []
    durations = []
    topic_counts = []
    mood_totals = {}
    total_mood_entries = 0
    for s in sessions:
        interactions.append(s.get("interactions", 0))
        durations.append(s.get("duration_minutes", 0))
        topics = s.get("topics_discussed", [])
        topic_counts.append(len(set(topics)))
        mood_dist = s.get("mood_distribution", {})
        for mood, count in mood_dist.items():
            mood_totals[mood] = mood_totals.get(mood, 0) + count
            total_mood_entries += count
    n = len(sessions)
    mood_pct = {}
    if total_mood_entries > 0:
        mood_pct = {m: round(c / total_mood_entries * 100, 1) for m, c in mood_totals.items()}
    return {
        "sessions": n,
        "avg_interactions": round(sum(interactions) / n, 1),
        "avg_duration": round(sum(durations) / n, 1),
        "avg_topics": round(sum(topic_counts) / n, 1),
        "mood_pct": mood_pct,
    }


def check_anomalies(patient_id="default", today_stats=None):
    """Compare today against baseline. Returns list of anomaly dicts."""
    if not today_stats:
        return []
    baseline = build_baseline(patient_id)
    if not baseline:
        return []
    anomalies = []
    avg_int = baseline["avg_interactions"]
    today_int = today_stats.get("interactions", 0)
    if avg_int > 0 and today_int < avg_int * 0.5:
        anomalies.append({
            "metric": "interactions",
            "message": f"Very few interactions today ({today_int} vs avg {avg_int})",
            "severity": "warning",
        })
    avg_dur = baseline["avg_duration"]
    today_dur = today_stats.get("duration_minutes", 0)
    if avg_dur > 0 and today_dur < avg_dur * 0.5:
        anomalies.append({
            "metric": "duration",
            "message": f"Session much shorter than usual ({today_dur:.0f}min vs avg {avg_dur:.0f}min)",
            "severity": "warning",
        })
    avg_top = baseline["avg_topics"]
    today_top = today_stats.get("topic_count", 0)
    if avg_top > 0 and today_top < avg_top * 0.4:
        anomalies.append({
            "metric": "topic_variety",
            "message": f"Very low topic variety ({today_top} vs avg {avg_top})",
            "severity": "info",
        })
    baseline_sad = baseline.get("mood_pct", {}).get("sadness", 0)
    today_sad = today_stats.get("sadness_pct", 0)
    if today_sad > baseline_sad + 30:
        anomalies.append({
            "metric": "mood_shift",
            "message": f"Sadness much higher than usual ({today_sad:.0f}% vs baseline {baseline_sad:.0f}%)",
            "severity": "warning",
        })
    return anomalies
