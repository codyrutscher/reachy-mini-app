"""Supabase/Postgres connection for the Reachy bot.

Comprehensive persistence layer — stores moods, conversations, patient
facts, cognitive scores, exercises, sleep, sessions, and weekly reports.

Set SUPABASE_DB_URL in your environment to enable.
Falls back gracefully if not configured or psycopg2 is missing.
"""

import json
import os
import threading
from datetime import datetime, timedelta

DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL", "")

_local = threading.local()
_available = False


def is_available() -> bool:
    return _available


def _get_conn():
    if not hasattr(_local, "conn") or _local.conn is None or _local.conn.closed:
        import psycopg2
        _local.conn = psycopg2.connect(DATABASE_URL)
        _local.conn.autocommit = True
    return _local.conn


def _execute(query, params=None, fetch=False, fetchone=False):
    import psycopg2.extras
    conn = _get_conn()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params or ())
        if fetchone:
            row = cur.fetchone()
            return dict(row) if row else None
        if fetch:
            return [dict(r) for r in cur.fetchall()]
    return None


def init_bot_tables():
    """Create all bot tables if they don't exist."""
    global _available
    if not DATABASE_URL:
        print("[DB] No SUPABASE_DB_URL set — bot data won't persist")
        return False
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bot_mood_journal (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT DEFAULT 'default',
                    mood TEXT NOT NULL,
                    hour INTEGER,
                    day_of_week TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS bot_conversation_log (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT DEFAULT 'default',
                    topic TEXT,
                    text TEXT NOT NULL,
                    speaker TEXT DEFAULT 'patient',
                    emotion TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS bot_mentions (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT DEFAULT 'default',
                    category TEXT NOT NULL,
                    mention TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(patient_id, category, mention)
                );
                CREATE TABLE IF NOT EXISTS bot_streaks (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT DEFAULT 'default',
                    conversation_date DATE NOT NULL,
                    UNIQUE(patient_id, conversation_date)
                );
                CREATE TABLE IF NOT EXISTS bot_patient_facts (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT DEFAULT 'default',
                    category TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(patient_id, fact)
                );
                CREATE TABLE IF NOT EXISTS bot_patient_profile (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT UNIQUE DEFAULT 'default',
                    name TEXT DEFAULT '',
                    preferred_name TEXT DEFAULT '',
                    age INTEGER,
                    favorite_topic TEXT DEFAULT '',
                    personality_notes TEXT DEFAULT '',
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bot_cognitive_scores (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT DEFAULT 'default',
                    game_type TEXT NOT NULL,
                    score REAL NOT NULL,
                    max_score REAL NOT NULL,
                    duration_seconds INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS bot_exercise_log (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT DEFAULT 'default',
                    exercise_name TEXT NOT NULL,
                    completed BOOLEAN DEFAULT TRUE,
                    duration_seconds INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS bot_pain_reports (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT DEFAULT 'default',
                    location TEXT DEFAULT '',
                    severity INTEGER DEFAULT 0,
                    notes TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS bot_sleep_log (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT DEFAULT 'default',
                    event_type TEXT NOT NULL,
                    quality TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS bot_session_summaries (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT DEFAULT 'default',
                    interactions INTEGER DEFAULT 0,
                    dominant_mood TEXT DEFAULT '',
                    mood_distribution TEXT DEFAULT '{}',
                    topics_discussed TEXT DEFAULT '[]',
                    facts_learned TEXT DEFAULT '[]',
                    duration_minutes REAL DEFAULT 0,
                    summary_text TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS bot_weekly_reports (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT DEFAULT 'default',
                    week_start DATE NOT NULL,
                    total_sessions INTEGER DEFAULT 0,
                    total_interactions INTEGER DEFAULT 0,
                    mood_summary TEXT DEFAULT '{}',
                    top_topics TEXT DEFAULT '[]',
                    cognitive_avg REAL DEFAULT 0,
                    streak_days INTEGER DEFAULT 0,
                    report_text TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(patient_id, week_start)
                );
                CREATE TABLE IF NOT EXISTS bot_reminders (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT DEFAULT 'default',
                    reminder_type TEXT DEFAULT 'general',
                    text TEXT NOT NULL,
                    time TEXT DEFAULT '',
                    repeat_pattern TEXT DEFAULT 'once',
                    active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS bot_caregiver_alerts (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT DEFAULT 'default',
                    alert_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    severity TEXT DEFAULT 'normal',
                    acknowledged BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS bot_chat_history (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT UNIQUE DEFAULT 'default',
                    history JSONB DEFAULT '[]',
                    user_name TEXT DEFAULT '',
                    user_facts JSONB DEFAULT '[]',
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)
        _available = True
        print("[DB] Bot Supabase tables ready (13 tables)")

        # Migrations — add columns that may not exist on older databases
        try:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE bot_session_summaries ADD COLUMN IF NOT EXISTS summary_text TEXT DEFAULT ''")
                cur.execute("ALTER TABLE bot_session_summaries ADD COLUMN IF NOT EXISTS engagement_avg REAL DEFAULT 0")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bot_conversation_intel (
                        id SERIAL PRIMARY KEY,
                        patient_id TEXT UNIQUE DEFAULT 'default',
                        humor_hits JSONB DEFAULT '[]',
                        topic_mood_map JSONB DEFAULT '{}',
                        mentioned_names JSONB DEFAULT '{}',
                        engagement_avg REAL DEFAULT 0,
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """)
        except Exception:
            pass  # column/table already exists

        return True
    except Exception as e:
        print(f"[DB] Supabase init failed: {e}")
        return False


# ── Mood Journal ────────────────────────────────────────────────────

def save_mood(mood, hour, day, patient_id="default"):
    if not _available: return
    try:
        _execute("INSERT INTO bot_mood_journal (patient_id,mood,hour,day_of_week) VALUES (%s,%s,%s,%s)",
                 (patient_id, mood, hour, day))
    except Exception as e: print(f"[DB] save_mood: {e}")

def get_moods(patient_id="default", limit=50):
    if not _available: return []
    try:
        return _execute("SELECT mood,hour,day_of_week,created_at FROM bot_mood_journal WHERE patient_id=%s ORDER BY id DESC LIMIT %s",
                        (patient_id, limit), fetch=True) or []
    except Exception as e: print(f"[DB] get_moods: {e}"); return []

def get_mood_counts(patient_id="default", days=7):
    """Get mood counts for the last N days."""
    if not _available: return {}
    try:
        rows = _execute("SELECT mood, COUNT(*) as cnt FROM bot_mood_journal WHERE patient_id=%s AND created_at > NOW() - INTERVAL '%s days' GROUP BY mood ORDER BY cnt DESC",
                        (patient_id, days), fetch=True) or []
        return {r["mood"]: r["cnt"] for r in rows}
    except Exception as e: print(f"[DB] get_mood_counts: {e}"); return {}


# ── Conversation Log ────────────────────────────────────────────────

def save_conversation(topic, text, patient_id="default", speaker="patient", emotion=""):
    if not _available: return
    try:
        _execute("INSERT INTO bot_conversation_log (patient_id,topic,text,speaker,emotion) VALUES (%s,%s,%s,%s,%s)",
                 (patient_id, topic, text, speaker, emotion))
    except Exception as e: print(f"[DB] save_conversation: {e}")

def get_conversations(patient_id="default", limit=50):
    if not _available: return []
    try:
        return _execute("SELECT topic,text,speaker,emotion,created_at FROM bot_conversation_log WHERE patient_id=%s ORDER BY id DESC LIMIT %s",
                        (patient_id, limit), fetch=True) or []
    except Exception as e: print(f"[DB] get_conversations: {e}"); return []

def get_topic_counts(patient_id="default", days=7):
    """Get topic frequency for the last N days."""
    if not _available: return {}
    try:
        rows = _execute("SELECT topic, COUNT(*) as cnt FROM bot_conversation_log WHERE patient_id=%s AND topic != 'general' AND created_at > NOW() - INTERVAL '%s days' GROUP BY topic ORDER BY cnt DESC",
                        (patient_id, days), fetch=True) or []
        return {r["topic"]: r["cnt"] for r in rows}
    except Exception as e: print(f"[DB] get_topic_counts: {e}"); return {}


# ── Mentions ────────────────────────────────────────────────────────

def save_mention(category, mention, patient_id="default"):
    if not _available: return
    try:
        _execute("INSERT INTO bot_mentions (patient_id,category,mention) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                 (patient_id, category, mention))
    except Exception as e: print(f"[DB] save_mention: {e}")

def get_mentions(patient_id="default"):
    if not _available: return {}
    try:
        rows = _execute("SELECT category,mention FROM bot_mentions WHERE patient_id=%s", (patient_id,), fetch=True) or []
        result = {}
        for r in rows:
            result.setdefault(r["category"], []).append(r["mention"])
        return result
    except Exception as e: print(f"[DB] get_mentions: {e}"); return {}


# ── Streaks ─────────────────────────────────────────────────────────

def save_streak_date(patient_id="default"):
    """Log that a conversation happened today."""
    if not _available: return
    try:
        _execute("INSERT INTO bot_streaks (patient_id,conversation_date) VALUES (%s,CURRENT_DATE) ON CONFLICT DO NOTHING",
                 (patient_id,))
    except Exception as e: print(f"[DB] save_streak_date: {e}")

def get_streak(patient_id="default") -> int:
    """Calculate consecutive conversation days ending today."""
    if not _available: return 0
    try:
        rows = _execute("SELECT conversation_date FROM bot_streaks WHERE patient_id=%s ORDER BY conversation_date DESC LIMIT 60",
                        (patient_id,), fetch=True) or []
        if not rows:
            return 0
        dates = [r["conversation_date"] for r in rows]
        streak = 1
        for i in range(len(dates) - 1):
            diff = dates[i] - dates[i + 1]
            if diff.days == 1:
                streak += 1
            else:
                break
        return streak
    except Exception as e: print(f"[DB] get_streak: {e}"); return 0


# ── Patient Facts ───────────────────────────────────────────────────

def save_fact(category, fact, patient_id="default"):
    if not _available: return
    try:
        _execute("INSERT INTO bot_patient_facts (patient_id,category,fact) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                 (patient_id, category, fact))
    except Exception as e: print(f"[DB] save_fact: {e}")

def get_facts(patient_id="default", category=None):
    if not _available: return []
    try:
        if category:
            return _execute("SELECT category,fact,created_at FROM bot_patient_facts WHERE patient_id=%s AND category=%s ORDER BY id DESC",
                            (patient_id, category), fetch=True) or []
        return _execute("SELECT category,fact,created_at FROM bot_patient_facts WHERE patient_id=%s ORDER BY id DESC",
                        (patient_id,), fetch=True) or []
    except Exception as e: print(f"[DB] get_facts: {e}"); return []


# ── Patient Profile ─────────────────────────────────────────────────

def save_profile(patient_id="default", **kwargs):
    """Create or update a patient profile. Pass any column as a kwarg."""
    if not _available: return
    try:
        _execute("INSERT INTO bot_patient_profile (patient_id) VALUES (%s) ON CONFLICT (patient_id) DO NOTHING",
                 (patient_id,))
        allowed = {"name", "preferred_name", "age", "favorite_topic", "personality_notes"}
        for key, val in kwargs.items():
            if key in allowed:
                _execute(f"UPDATE bot_patient_profile SET {key}=%s, updated_at=NOW() WHERE patient_id=%s",
                         (val, patient_id))
    except Exception as e: print(f"[DB] save_profile: {e}")

def get_profile(patient_id="default"):
    if not _available: return {}
    try:
        row = _execute("SELECT * FROM bot_patient_profile WHERE patient_id=%s", (patient_id,), fetchone=True)
        return row or {}
    except Exception as e: print(f"[DB] get_profile: {e}"); return {}


# ── Cognitive Scores ────────────────────────────────────────────────

def save_cognitive_score(game_type, score, max_score, duration_seconds=0, patient_id="default"):
    if not _available: return
    try:
        _execute("INSERT INTO bot_cognitive_scores (patient_id,game_type,score,max_score,duration_seconds) VALUES (%s,%s,%s,%s,%s)",
                 (patient_id, game_type, score, max_score, duration_seconds))
    except Exception as e: print(f"[DB] save_cognitive_score: {e}")

def get_cognitive_scores(patient_id="default", limit=20):
    if not _available: return []
    try:
        return _execute("SELECT game_type,score,max_score,duration_seconds,created_at FROM bot_cognitive_scores WHERE patient_id=%s ORDER BY id DESC LIMIT %s",
                        (patient_id, limit), fetch=True) or []
    except Exception as e: print(f"[DB] get_cognitive_scores: {e}"); return []

def get_cognitive_avg(patient_id="default", days=7):
    """Average cognitive score percentage over the last N days."""
    if not _available: return 0.0
    try:
        row = _execute("SELECT AVG(score/NULLIF(max_score,0))*100 as avg_pct FROM bot_cognitive_scores WHERE patient_id=%s AND created_at > NOW() - INTERVAL '%s days'",
                       (patient_id, days), fetchone=True)
        return round(row["avg_pct"] or 0, 1) if row else 0.0
    except Exception as e: print(f"[DB] get_cognitive_avg: {e}"); return 0.0


# ── Exercise Log ────────────────────────────────────────────────────

def save_exercise(exercise_name, completed=True, duration_seconds=0, patient_id="default"):
    if not _available: return
    try:
        _execute("INSERT INTO bot_exercise_log (patient_id,exercise_name,completed,duration_seconds) VALUES (%s,%s,%s,%s)",
                 (patient_id, exercise_name, completed, duration_seconds))
    except Exception as e: print(f"[DB] save_exercise: {e}")

def get_exercises(patient_id="default", limit=20):
    if not _available: return []
    try:
        return _execute("SELECT exercise_name,completed,duration_seconds,created_at FROM bot_exercise_log WHERE patient_id=%s ORDER BY id DESC LIMIT %s",
                        (patient_id, limit), fetch=True) or []
    except Exception as e: print(f"[DB] get_exercises: {e}"); return []


# ── Pain Reports ────────────────────────────────────────────────────

def save_pain_report(location, severity, notes="", patient_id="default"):
    if not _available: return
    try:
        _execute("INSERT INTO bot_pain_reports (patient_id,location,severity,notes) VALUES (%s,%s,%s,%s)",
                 (patient_id, location, severity, notes))
    except Exception as e: print(f"[DB] save_pain_report: {e}")

def get_pain_reports(patient_id="default", limit=20):
    if not _available: return []
    try:
        return _execute("SELECT location,severity,notes,created_at FROM bot_pain_reports WHERE patient_id=%s ORDER BY id DESC LIMIT %s",
                        (patient_id, limit), fetch=True) or []
    except Exception as e: print(f"[DB] get_pain_reports: {e}"); return []


# ── Sleep Log ───────────────────────────────────────────────────────

def save_sleep_event(event_type, quality="", notes="", patient_id="default"):
    """event_type: 'bedtime' or 'wake'."""
    if not _available: return
    try:
        _execute("INSERT INTO bot_sleep_log (patient_id,event_type,quality,notes) VALUES (%s,%s,%s,%s)",
                 (patient_id, event_type, quality, notes))
    except Exception as e: print(f"[DB] save_sleep_event: {e}")

def get_sleep_log(patient_id="default", limit=14):
    if not _available: return []
    try:
        return _execute("SELECT event_type,quality,notes,created_at FROM bot_sleep_log WHERE patient_id=%s ORDER BY id DESC LIMIT %s",
                        (patient_id, limit), fetch=True) or []
    except Exception as e: print(f"[DB] get_sleep_log: {e}"); return []


# ── Session Summaries ───────────────────────────────────────────────

def save_session_summary(interactions, dominant_mood, mood_distribution,
                         topics_discussed, facts_learned, duration_minutes,
                         patient_id="default", summary_text="", engagement_avg=0.0):
    if not _available: return
    try:
        _execute(
            "INSERT INTO bot_session_summaries "
            "(patient_id,interactions,dominant_mood,mood_distribution,topics_discussed,facts_learned,duration_minutes,summary_text,engagement_avg) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (patient_id, interactions, dominant_mood,
             json.dumps(mood_distribution), json.dumps(topics_discussed),
             json.dumps(facts_learned), duration_minutes, summary_text, engagement_avg))
    except Exception as e: print(f"[DB] save_session_summary: {e}")

def get_session_summaries(patient_id="default", limit=10):
    if not _available: return []
    try:
        rows = _execute(
            "SELECT interactions,dominant_mood,mood_distribution,topics_discussed,"
            "facts_learned,duration_minutes,summary_text,created_at "
            "FROM bot_session_summaries WHERE patient_id=%s ORDER BY id DESC LIMIT %s",
            (patient_id, limit), fetch=True) or []
        for r in rows:
            r["mood_distribution"] = json.loads(r.get("mood_distribution", "{}"))
            r["topics_discussed"] = json.loads(r.get("topics_discussed", "[]"))
            r["facts_learned"] = json.loads(r.get("facts_learned", "[]"))
        return rows
    except Exception as e: print(f"[DB] get_session_summaries: {e}"); return []


# ── Weekly Reports ──────────────────────────────────────────────────

def generate_weekly_report(patient_id="default"):
    """Auto-generate a weekly report from the last 7 days of data."""
    if not _available: return {}
    try:
        from datetime import date
        today = date.today()
        week_start = today - timedelta(days=today.weekday())  # Monday

        # Gather stats
        mood_summary = get_mood_counts(patient_id, days=7)
        top_topics = get_topic_counts(patient_id, days=7)
        cognitive_avg = get_cognitive_avg(patient_id, days=7)
        streak = get_streak(patient_id)

        sessions = get_session_summaries(patient_id, limit=7)
        total_sessions = len(sessions)
        total_interactions = sum(s.get("interactions", 0) for s in sessions)

        # Build a human-readable report
        parts = [f"Weekly Report ({week_start} to {today})"]
        parts.append(f"Sessions: {total_sessions}, Interactions: {total_interactions}")
        if mood_summary:
            top_mood = max(mood_summary, key=mood_summary.get)
            parts.append(f"Dominant mood: {top_mood}")
        if top_topics:
            fav = list(top_topics.keys())[:3]
            parts.append(f"Favorite topics: {', '.join(fav)}")
        if cognitive_avg:
            parts.append(f"Cognitive avg: {cognitive_avg}%")
        parts.append(f"Streak: {streak} days")
        report_text = ". ".join(parts)

        # Save to DB
        _execute(
            "INSERT INTO bot_weekly_reports "
            "(patient_id,week_start,total_sessions,total_interactions,mood_summary,"
            "top_topics,cognitive_avg,streak_days,report_text) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (patient_id,week_start) DO UPDATE SET "
            "total_sessions=EXCLUDED.total_sessions,total_interactions=EXCLUDED.total_interactions,"
            "mood_summary=EXCLUDED.mood_summary,top_topics=EXCLUDED.top_topics,"
            "cognitive_avg=EXCLUDED.cognitive_avg,streak_days=EXCLUDED.streak_days,"
            "report_text=EXCLUDED.report_text,created_at=NOW()",
            (patient_id, week_start, total_sessions, total_interactions,
             json.dumps(mood_summary), json.dumps(list(top_topics.keys())[:5]),
             cognitive_avg, streak, report_text))

        return {"week_start": str(week_start), "report": report_text,
                "mood_summary": mood_summary, "top_topics": top_topics,
                "cognitive_avg": cognitive_avg, "streak": streak}
    except Exception as e: print(f"[DB] generate_weekly_report: {e}"); return {}

def get_weekly_reports(patient_id="default", limit=4):
    if not _available: return []
    try:
        rows = _execute(
            "SELECT week_start,total_sessions,total_interactions,mood_summary,"
            "top_topics,cognitive_avg,streak_days,report_text,created_at "
            "FROM bot_weekly_reports WHERE patient_id=%s ORDER BY week_start DESC LIMIT %s",
            (patient_id, limit), fetch=True) or []
        for r in rows:
            r["mood_summary"] = json.loads(r.get("mood_summary", "{}"))
            r["top_topics"] = json.loads(r.get("top_topics", "[]"))
        return rows
    except Exception as e: print(f"[DB] get_weekly_reports: {e}"); return []


# ── Reminders ───────────────────────────────────────────────────────

def save_reminder(text, reminder_type="general", time_str="", repeat_pattern="once", patient_id="default"):
    if not _available: return None
    try:
        row = _execute(
            "INSERT INTO bot_reminders (patient_id,reminder_type,text,time,repeat_pattern) "
            "VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (patient_id, reminder_type, text, time_str, repeat_pattern), fetchone=True)
        return row["id"] if row else None
    except Exception as e: print(f"[DB] save_reminder: {e}"); return None

def get_reminders(patient_id="default", active_only=True):
    if not _available: return []
    try:
        if active_only:
            return _execute("SELECT id,reminder_type,text,time,repeat_pattern,active,created_at FROM bot_reminders WHERE patient_id=%s AND active=TRUE ORDER BY id DESC",
                            (patient_id,), fetch=True) or []
        return _execute("SELECT id,reminder_type,text,time,repeat_pattern,active,created_at FROM bot_reminders WHERE patient_id=%s ORDER BY id DESC",
                        (patient_id,), fetch=True) or []
    except Exception as e: print(f"[DB] get_reminders: {e}"); return []

def toggle_reminder(reminder_id, active=False):
    if not _available: return
    try:
        _execute("UPDATE bot_reminders SET active=%s WHERE id=%s", (active, reminder_id))
    except Exception as e: print(f"[DB] toggle_reminder: {e}")


# ── Caregiver Alerts ────────────────────────────────────────────────

def save_alert(alert_type, message, severity="normal", patient_id="default"):
    if not _available: return None
    try:
        row = _execute(
            "INSERT INTO bot_caregiver_alerts (patient_id,alert_type,message,severity) "
            "VALUES (%s,%s,%s,%s) RETURNING id",
            (patient_id, alert_type, message, severity), fetchone=True)
        return row["id"] if row else None
    except Exception as e: print(f"[DB] save_alert: {e}"); return None

def get_alerts(patient_id="default", unacknowledged_only=True, limit=20):
    if not _available: return []
    try:
        if unacknowledged_only:
            return _execute(
                "SELECT id,alert_type,message,severity,acknowledged,created_at "
                "FROM bot_caregiver_alerts WHERE patient_id=%s AND acknowledged=FALSE "
                "ORDER BY id DESC LIMIT %s",
                (patient_id, limit), fetch=True) or []
        return _execute(
            "SELECT id,alert_type,message,severity,acknowledged,created_at "
            "FROM bot_caregiver_alerts WHERE patient_id=%s ORDER BY id DESC LIMIT %s",
            (patient_id, limit), fetch=True) or []
    except Exception as e: print(f"[DB] get_alerts: {e}"); return []

def ack_alert(alert_id):
    """Mark an alert as acknowledged."""
    if not _available: return
    try:
        _execute("UPDATE bot_caregiver_alerts SET acknowledged=TRUE WHERE id=%s", (alert_id,))
    except Exception as e: print(f"[DB] ack_alert: {e}")


# ── Vector Memory (pgvector) ────────────────────────────────────────

def save_memory_vector(text, embedding, speaker="patient", emotion="", topic="general", patient_id="default", emotion_weight=1.0):
    """Store a conversation turn with its vector embedding and emotion weight."""
    if not _available: return
    try:
        _execute(
            "INSERT INTO bot_memory_vectors (patient_id,text,speaker,emotion,topic,embedding,emotion_weight) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (patient_id, text, speaker, emotion, topic, str(embedding), emotion_weight))
    except Exception as e: print(f"[DB] save_memory_vector: {e}")

def search_memory_vectors(query_embedding, patient_id="default", limit=5):
    """Find the most similar past conversations using cosine similarity."""
    if not _available: return []
    try:
        rows = _execute(
            "SELECT text, speaker, emotion, topic, emotion_weight, created_at, "
            "1 - (embedding <=> %s::vector) as similarity "
            "FROM bot_memory_vectors "
            "WHERE patient_id = %s "
            "ORDER BY embedding <=> %s::vector "
            "LIMIT %s",
            (str(query_embedding), patient_id, str(query_embedding), limit),
            fetch=True) or []
        return rows
    except Exception as e: print(f"[DB] search_memory_vectors: {e}"); return []

def get_memory_vector_count(patient_id="default") -> int:
    if not _available: return 0
    try:
        row = _execute("SELECT COUNT(*) as cnt FROM bot_memory_vectors WHERE patient_id=%s",
                       (patient_id,), fetchone=True)
        return row["cnt"] if row else 0
    except Exception as e: print(f"[DB] get_memory_vector_count: {e}"); return 0


# ── Knowledge Graph ─────────────────────────────────────────────────

def save_entity(name, entity_type, attributes=None, patient_id="default"):
    """Save or update a knowledge entity (person, place, pet, etc.)."""
    if not _available: return
    try:
        attrs = json.dumps(attributes or {})
        _execute(
            "INSERT INTO bot_knowledge_entities (patient_id,name,entity_type,attributes) "
            "VALUES (%s,%s,%s,%s) "
            "ON CONFLICT (patient_id,name,entity_type) DO UPDATE SET "
            "attributes = bot_knowledge_entities.attributes || %s::jsonb, updated_at=NOW()",
            (patient_id, name.lower(), entity_type, attrs, attrs))
    except Exception as e: print(f"[DB] save_entity: {e}")

def save_relation(subject, relation, obj, source_text="", confidence=1.0, patient_id="default"):
    """Save a relationship between two entities."""
    if not _available: return
    try:
        _execute(
            "INSERT INTO bot_knowledge_relations (patient_id,subject,relation,object,confidence,source_text) "
            "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (patient_id,subject,relation,object) DO UPDATE SET "
            "confidence=GREATEST(bot_knowledge_relations.confidence, EXCLUDED.confidence), "
            "source_text=EXCLUDED.source_text",
            (patient_id, subject.lower(), relation, obj.lower(), confidence, source_text[:200]))
    except Exception as e: print(f"[DB] save_relation: {e}")

def get_entity(name, patient_id="default"):
    """Get an entity and all its attributes."""
    if not _available: return None
    try:
        return _execute(
            "SELECT name,entity_type,attributes,updated_at FROM bot_knowledge_entities "
            "WHERE patient_id=%s AND name=%s",
            (patient_id, name.lower()), fetchone=True)
    except Exception as e: print(f"[DB] get_entity: {e}"); return None

def get_entities_by_type(entity_type, patient_id="default"):
    if not _available: return []
    try:
        return _execute(
            "SELECT name,entity_type,attributes FROM bot_knowledge_entities "
            "WHERE patient_id=%s AND entity_type=%s ORDER BY updated_at DESC",
            (patient_id, entity_type), fetch=True) or []
    except Exception as e: print(f"[DB] get_entities_by_type: {e}"); return []

def get_relations_for(name, patient_id="default"):
    """Get all relationships involving an entity (as subject or object)."""
    if not _available: return []
    try:
        return _execute(
            "SELECT subject,relation,object,confidence FROM bot_knowledge_relations "
            "WHERE patient_id=%s AND (subject=%s OR object=%s) ORDER BY confidence DESC",
            (patient_id, name.lower(), name.lower()), fetch=True) or []
    except Exception as e: print(f"[DB] get_relations_for: {e}"); return []

def get_all_entities(patient_id="default"):
    if not _available: return []
    try:
        return _execute(
            "SELECT name,entity_type,attributes FROM bot_knowledge_entities "
            "WHERE patient_id=%s ORDER BY entity_type,name",
            (patient_id,), fetch=True) or []
    except Exception as e: print(f"[DB] get_all_entities: {e}"); return []

def get_all_relations(patient_id="default"):
    if not _available: return []
    try:
        return _execute(
            "SELECT subject,relation,object,confidence FROM bot_knowledge_relations "
            "WHERE patient_id=%s ORDER BY confidence DESC",
            (patient_id,), fetch=True) or []
    except Exception as e: print(f"[DB] get_all_relations: {e}"); return []


# ── Temporal Patterns ───────────────────────────────────────────────

def save_pattern(pattern_type, description, severity="info", data=None, patient_id="default"):
    if not _available: return
    try:
        _execute(
            "INSERT INTO bot_temporal_patterns (patient_id,pattern_type,description,severity,data) "
            "VALUES (%s,%s,%s,%s,%s) "
            "ON CONFLICT (patient_id,pattern_type,description) DO UPDATE SET "
            "severity=EXCLUDED.severity, data=EXCLUDED.data, detected_at=NOW()",
            (patient_id, pattern_type, description, severity, json.dumps(data or {})))
    except Exception as e: print(f"[DB] save_pattern: {e}")

def get_patterns(patient_id="default", severity=None):
    if not _available: return []
    try:
        if severity:
            return _execute(
                "SELECT pattern_type,description,severity,data,detected_at FROM bot_temporal_patterns "
                "WHERE patient_id=%s AND severity=%s ORDER BY detected_at DESC",
                (patient_id, severity), fetch=True) or []
        return _execute(
            "SELECT pattern_type,description,severity,data,detected_at FROM bot_temporal_patterns "
            "WHERE patient_id=%s ORDER BY detected_at DESC",
            (patient_id,), fetch=True) or []
    except Exception as e: print(f"[DB] get_patterns: {e}"); return []

# ── Chat History (brain.history persistence) ────────────────────────

def save_chat_history(history, user_name="", user_facts=None, patient_id="default"):
    """Persist the brain's conversation history so it survives restarts.
    Uses UPSERT — one row per patient, overwritten each save."""
    if not _available: return
    try:
        _execute(
            "INSERT INTO bot_chat_history (patient_id, history, user_name, user_facts, updated_at) "
            "VALUES (%s, %s, %s, %s, NOW()) "
            "ON CONFLICT (patient_id) DO UPDATE SET "
            "history = EXCLUDED.history, user_name = EXCLUDED.user_name, "
            "user_facts = EXCLUDED.user_facts, updated_at = NOW()",
            (patient_id, json.dumps(history), user_name, json.dumps(user_facts or [])))
    except Exception as e: print(f"[DB] save_chat_history: {e}")


def get_chat_history(patient_id="default"):
    """Restore the brain's conversation history from the last session.
    Returns dict with 'history', 'user_name', 'user_facts' or None."""
    if not _available: return None
    try:
        row = _execute(
            "SELECT history, user_name, user_facts, updated_at FROM bot_chat_history "
            "WHERE patient_id=%s", (patient_id,), fetchone=True)
        if not row:
            return None
        # Parse JSON fields
        hist = row.get("history", [])
        if isinstance(hist, str):
            hist = json.loads(hist)
        facts = row.get("user_facts", [])
        if isinstance(facts, str):
            facts = json.loads(facts)
        return {
            "history": hist,
            "user_name": row.get("user_name", ""),
            "user_facts": facts,
            "updated_at": row.get("updated_at"),
        }
    except Exception as e: print(f"[DB] get_chat_history: {e}"); return None


# ── Conversational intelligence persistence ───────────────────

def save_conversation_intel(patient_id="default", humor_hits=None, topic_mood_map=None,
                            mentioned_names=None, engagement_avg=0.0):
    """Save conversational intelligence data for cross-session learning."""
    if not _available:
        return
    try:
        _execute(
            "INSERT INTO bot_conversation_intel "
            "(patient_id, humor_hits, topic_mood_map, mentioned_names, engagement_avg) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (patient_id) DO UPDATE SET "
            "humor_hits = EXCLUDED.humor_hits, "
            "topic_mood_map = EXCLUDED.topic_mood_map, "
            "mentioned_names = EXCLUDED.mentioned_names, "
            "engagement_avg = EXCLUDED.engagement_avg, "
            "updated_at = NOW()",
            (patient_id, json.dumps(humor_hits or []),
             json.dumps(topic_mood_map or {}),
             json.dumps(mentioned_names or {}),
             engagement_avg))
    except Exception as e:
        print(f"[DB] save_conversation_intel: {e}")


def get_conversation_intel(patient_id="default"):
    """Load conversational intelligence data from previous sessions."""
    if not _available:
        return None
    try:
        row = _execute(
            "SELECT humor_hits, topic_mood_map, mentioned_names, engagement_avg "
            "FROM bot_conversation_intel WHERE patient_id=%s",
            (patient_id,), fetchone=True)
        if not row:
            return None
        humor = row.get("humor_hits", [])
        if isinstance(humor, str):
            humor = json.loads(humor)
        topic_mood = row.get("topic_mood_map", {})
        if isinstance(topic_mood, str):
            topic_mood = json.loads(topic_mood)
        names = row.get("mentioned_names", {})
        if isinstance(names, str):
            names = json.loads(names)
        return {
            "humor_hits": humor,
            "topic_mood_map": topic_mood,
            "mentioned_names": names,
            "engagement_avg": row.get("engagement_avg", 0.0),
        }
    except Exception as e:
        print(f"[DB] get_conversation_intel: {e}")
        return None
