"""Temporal Pattern Detection — spots trends over time in patient data.

Detects things like:
- "Patient mentioned back pain 4 times this week but 0 times last week"
- "Sadness is increasing — 2 sad days last week, 5 this week"
- "Patient hasn't mentioned family in 10 days (usually talks about them daily)"
- "Sleep quality declining — bedtime getting later each night"

Patterns are saved to Supabase and can trigger caregiver alerts.
"""

import json
from datetime import datetime, timedelta


def analyze(patient_id: str = "default") -> list:
    """Run all pattern detectors and return findings."""
    findings = []
    findings.extend(_detect_mood_trends(patient_id))
    findings.extend(_detect_topic_changes(patient_id))
    findings.extend(_detect_health_mentions(patient_id))
    findings.extend(_detect_engagement_drop(patient_id))
    findings.extend(_detect_sleep_changes(patient_id))

    # Save findings to DB
    try:
        import db_supabase as _db
        if _db.is_available():
            for f in findings:
                _db.save_pattern(
                    f["type"], f["description"], f["severity"],
                    f.get("data", {}), patient_id)
    except Exception as e:
        print(f"[TEMPORAL] Save error: {e}")

    if findings:
        print(f"[TEMPORAL] Detected {len(findings)} patterns")
    return findings


def _detect_mood_trends(patient_id) -> list:
    """Compare this week's moods to last week's."""
    findings = []
    try:
        import db_supabase as _db
        this_week = _db.get_mood_counts(patient_id, days=7)
        last_week_raw = _db._execute(
            "SELECT mood, COUNT(*) as cnt FROM bot_mood_journal "
            "WHERE patient_id=%s AND created_at BETWEEN NOW() - INTERVAL '14 days' AND NOW() - INTERVAL '7 days' "
            "GROUP BY mood", (patient_id,), fetch=True) or []
        last_week = {r["mood"]: r["cnt"] for r in last_week_raw}

        if not this_week:
            return findings

        # Check if sadness is increasing
        sad_now = this_week.get("sadness", 0)
        sad_before = last_week.get("sadness", 0)
        if sad_now >= 3 and sad_now > sad_before * 1.5:
            findings.append({
                "type": "mood_trend",
                "description": f"Sadness increasing: {sad_before} last week → {sad_now} this week",
                "severity": "warning",
                "data": {"this_week": this_week, "last_week": last_week},
            })

        # Check if joy is decreasing
        joy_now = this_week.get("joy", 0)
        joy_before = last_week.get("joy", 0)
        if joy_before >= 3 and joy_now < joy_before * 0.5:
            findings.append({
                "type": "mood_trend",
                "description": f"Joy declining: {joy_before} last week → {joy_now} this week",
                "severity": "warning",
                "data": {"this_week": this_week, "last_week": last_week},
            })

        # Positive: mood improving
        if sad_before >= 3 and sad_now <= 1:
            findings.append({
                "type": "mood_trend",
                "description": f"Mood improving: sadness dropped from {sad_before} to {sad_now}",
                "severity": "info",
                "data": {"this_week": this_week, "last_week": last_week},
            })
    except Exception as e:
        print(f"[TEMPORAL] Mood trend error: {e}")
    return findings


def _detect_topic_changes(patient_id) -> list:
    """Detect if a usually-discussed topic has gone silent."""
    findings = []
    try:
        import db_supabase as _db
        this_week = _db.get_topic_counts(patient_id, days=7)
        last_week_raw = _db._execute(
            "SELECT topic, COUNT(*) as cnt FROM bot_conversation_log "
            "WHERE patient_id=%s AND topic != 'general' "
            "AND created_at BETWEEN NOW() - INTERVAL '14 days' AND NOW() - INTERVAL '7 days' "
            "GROUP BY topic", (patient_id,), fetch=True) or []
        last_week = {r["topic"]: r["cnt"] for r in last_week_raw}

        # Topics that were active last week but silent this week
        for topic, count in last_week.items():
            if count >= 3 and topic not in this_week:
                findings.append({
                    "type": "topic_change",
                    "description": f"Patient stopped talking about {topic} (was {count}x last week)",
                    "severity": "info",
                    "data": {"topic": topic, "last_week": count, "this_week": 0},
                })

        # New topic emerging
        for topic, count in this_week.items():
            if count >= 3 and topic not in last_week:
                findings.append({
                    "type": "topic_change",
                    "description": f"New frequent topic: {topic} ({count}x this week)",
                    "severity": "info",
                    "data": {"topic": topic, "this_week": count},
                })
    except Exception as e:
        print(f"[TEMPORAL] Topic change error: {e}")
    return findings


def _detect_health_mentions(patient_id) -> list:
    """Detect if health-related mentions are spiking."""
    findings = []
    try:
        import db_supabase as _db
        rows = _db._execute(
            "SELECT text, created_at FROM bot_conversation_log "
            "WHERE patient_id=%s AND created_at > NOW() - INTERVAL '7 days' "
            "ORDER BY created_at DESC", (patient_id,), fetch=True) or []

        health_words = ["pain", "hurt", "ache", "tired", "dizzy", "sick",
                        "medication", "medicine", "doctor", "hospital",
                        "can't sleep", "nauseous", "weak", "fell"]
        health_count = 0
        health_texts = []
        for r in rows:
            text = (r.get("text") or "").lower()
            if any(w in text for w in health_words):
                health_count += 1
                health_texts.append(text[:80])

        if health_count >= 3:
            findings.append({
                "type": "health_spike",
                "description": f"Patient mentioned health concerns {health_count} times this week",
                "severity": "warning" if health_count >= 5 else "info",
                "data": {"count": health_count, "samples": health_texts[:3]},
            })
    except Exception as e:
        print(f"[TEMPORAL] Health mention error: {e}")
    return findings


def _detect_engagement_drop(patient_id) -> list:
    """Detect if the patient is talking less."""
    findings = []
    try:
        import db_supabase as _db
        this_week = _db._execute(
            "SELECT COUNT(*) as cnt FROM bot_conversation_log "
            "WHERE patient_id=%s AND created_at > NOW() - INTERVAL '7 days'",
            (patient_id,), fetchone=True)
        last_week = _db._execute(
            "SELECT COUNT(*) as cnt FROM bot_conversation_log "
            "WHERE patient_id=%s AND created_at BETWEEN NOW() - INTERVAL '14 days' AND NOW() - INTERVAL '7 days'",
            (patient_id,), fetchone=True)

        now_cnt = (this_week or {}).get("cnt", 0)
        prev_cnt = (last_week or {}).get("cnt", 0)

        if prev_cnt >= 10 and now_cnt < prev_cnt * 0.4:
            findings.append({
                "type": "engagement_drop",
                "description": f"Patient talking much less: {prev_cnt} messages last week → {now_cnt} this week",
                "severity": "warning",
                "data": {"this_week": now_cnt, "last_week": prev_cnt},
            })
    except Exception as e:
        print(f"[TEMPORAL] Engagement error: {e}")
    return findings


def _detect_sleep_changes(patient_id) -> list:
    """Detect sleep pattern changes."""
    findings = []
    try:
        import db_supabase as _db
        events = _db.get_sleep_log(patient_id, limit=14)
        if len(events) < 4:
            return findings

        bedtimes = []
        for e in events:
            if e.get("event_type") == "bedtime":
                hour = e["created_at"].hour if hasattr(e["created_at"], "hour") else 0
                bedtimes.append(hour)

        if len(bedtimes) >= 3:
            avg = sum(bedtimes) / len(bedtimes)
            recent_avg = sum(bedtimes[:3]) / 3
            if recent_avg > avg + 1.5:
                findings.append({
                    "type": "sleep_change",
                    "description": f"Bedtime getting later: recent avg {recent_avg:.0f}:00 vs usual {avg:.0f}:00",
                    "severity": "info",
                    "data": {"recent_avg_hour": recent_avg, "overall_avg_hour": avg},
                })
    except Exception as e:
        print(f"[TEMPORAL] Sleep change error: {e}")
    return findings


def build_context(patient_id: str = "default") -> str:
    """Build a context string from detected patterns for the LLM."""
    try:
        import db_supabase as _db
        if not _db.is_available():
            return ""
        patterns = _db.get_patterns(patient_id)
        if not patterns:
            return ""
        parts = []
        for p in patterns[:4]:
            sev = p["severity"]
            desc = p["description"]
            prefix = "⚠️" if sev == "warning" else "📊"
            parts.append(f"{prefix} {desc}")
        if parts:
            return "Detected patterns: " + "; ".join(parts)
        return ""
    except Exception:
        return ""
