"""Patient model — tracks cognitive decline, exercise compliance,
medication adherence, and behavioral patterns over time.
Surfaces trends and alerts to caregivers."""

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta

MODEL_DB = os.environ.get(
    "REACHY_MODEL_DB",
    os.path.join(os.path.dirname(__file__), "patient_model.db"),
)

_local = threading.local()


def _get_conn():
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(MODEL_DB, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
    return _local.conn


def init_model_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cognitive_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT DEFAULT 'default',
            game_type TEXT NOT NULL,
            score REAL NOT NULL,
            max_score REAL DEFAULT 0,
            duration_seconds REAL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS exercise_compliance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT DEFAULT 'default',
            exercise_type TEXT NOT NULL,
            completed INTEGER DEFAULT 1,
            duration_seconds REAL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS med_adherence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT DEFAULT 'default',
            medication TEXT NOT NULL,
            status TEXT NOT NULL,
            scheduled_time TEXT DEFAULT '',
            actual_time TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS behavior_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT DEFAULT 'default',
            event_type TEXT NOT NULL,
            details TEXT DEFAULT '',
            severity REAL DEFAULT 0.5,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS daily_trends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT DEFAULT 'default',
            date TEXT NOT NULL,
            avg_mood_score REAL DEFAULT 0,
            interaction_count INTEGER DEFAULT 0,
            exercise_minutes REAL DEFAULT 0,
            meds_taken INTEGER DEFAULT 0,
            meds_missed INTEGER DEFAULT 0,
            cognitive_avg REAL DEFAULT 0,
            alerts_count INTEGER DEFAULT 0,
            sleep_hours REAL DEFAULT 0,
            UNIQUE(patient_id, date)
        );
    """)
    conn.commit()
    print(f"[PATIENT_MODEL] Database ready: {MODEL_DB}")


# ── Cognitive tracking ──────────────────────────────────────────────

def log_cognitive_score(game_type, score, max_score=0, duration=0, patient_id="default"):
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO cognitive_scores (patient_id, game_type, score, max_score, duration_seconds, created_at) VALUES (?,?,?,?,?,?)",
        (patient_id, game_type, score, max_score, duration, now),
    )
    conn.commit()


def get_cognitive_trend(patient_id="default", days=30):
    """Get cognitive score trend over time."""
    conn = _get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT date(created_at) as day, game_type, AVG(score) as avg_score,
           COUNT(*) as games_played
           FROM cognitive_scores WHERE patient_id=? AND created_at>=?
           GROUP BY day, game_type ORDER BY day""",
        (patient_id, cutoff),
    ).fetchall()
    return [dict(r) for r in rows]


def detect_cognitive_decline(patient_id="default"):
    """Compare recent 7-day avg vs previous 7-day avg. Returns decline percentage."""
    conn = _get_conn()
    now = datetime.now()
    recent_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_start = (now - timedelta(days=14)).strftime("%Y-%m-%d")

    recent = conn.execute(
        "SELECT AVG(score) as avg FROM cognitive_scores WHERE patient_id=? AND created_at>=?",
        (patient_id, recent_start),
    ).fetchone()
    prev = conn.execute(
        "SELECT AVG(score) as avg FROM cognitive_scores WHERE patient_id=? AND created_at>=? AND created_at<?",
        (patient_id, prev_start, recent_start),
    ).fetchone()

    if not recent["avg"] or not prev["avg"]:
        return None
    decline = ((prev["avg"] - recent["avg"]) / prev["avg"]) * 100
    return round(decline, 1)


# ── Exercise compliance ─────────────────────────────────────────────

def log_exercise(exercise_type, completed=True, duration=0, patient_id="default"):
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO exercise_compliance (patient_id, exercise_type, completed, duration_seconds, created_at) VALUES (?,?,?,?,?)",
        (patient_id, exercise_type, int(completed), duration, now),
    )
    conn.commit()


def get_exercise_compliance(patient_id="default", days=30):
    conn = _get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT date(created_at) as day, COUNT(*) as total,
           SUM(completed) as completed, SUM(duration_seconds) as total_duration
           FROM exercise_compliance WHERE patient_id=? AND created_at>=?
           GROUP BY day ORDER BY day""",
        (patient_id, cutoff),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Medication adherence ────────────────────────────────────────────

def log_med_adherence(medication, status, scheduled_time="", patient_id="default"):
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO med_adherence (patient_id, medication, status, scheduled_time, actual_time, created_at) VALUES (?,?,?,?,?,?)",
        (patient_id, medication, status, scheduled_time, now, now),
    )
    conn.commit()


def get_med_adherence_rate(patient_id="default", days=30):
    conn = _get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    total = conn.execute(
        "SELECT COUNT(*) FROM med_adherence WHERE patient_id=? AND created_at>=?",
        (patient_id, cutoff),
    ).fetchone()[0]
    taken = conn.execute(
        "SELECT COUNT(*) FROM med_adherence WHERE patient_id=? AND created_at>=? AND status='taken'",
        (patient_id, cutoff),
    ).fetchone()[0]
    if total == 0:
        return 100.0
    return round((taken / total) * 100, 1)


# ── Behavior events ─────────────────────────────────────────────────

def log_behavior_event(event_type, details="", severity=0.5, patient_id="default"):
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO behavior_events (patient_id, event_type, details, severity, created_at) VALUES (?,?,?,?,?)",
        (patient_id, event_type, details, severity, now),
    )
    conn.commit()


def get_behavior_events(patient_id="default", days=7, event_type=None):
    conn = _get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    if event_type:
        rows = conn.execute(
            "SELECT * FROM behavior_events WHERE patient_id=? AND created_at>=? AND event_type=? ORDER BY created_at DESC",
            (patient_id, cutoff, event_type),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM behavior_events WHERE patient_id=? AND created_at>=? ORDER BY created_at DESC",
            (patient_id, cutoff),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Daily trend aggregation ─────────────────────────────────────────

def update_daily_trend(patient_id="default"):
    """Aggregate today's data into the daily_trends table."""
    conn = _get_conn()
    today = datetime.now().strftime("%Y-%m-%d")

    interactions = conn.execute(
        "SELECT COUNT(*) FROM behavior_events WHERE patient_id=? AND date(created_at)=?",
        (patient_id, today),
    ).fetchone()[0]

    exercise_secs = conn.execute(
        "SELECT COALESCE(SUM(duration_seconds), 0) FROM exercise_compliance WHERE patient_id=? AND date(created_at)=?",
        (patient_id, today),
    ).fetchone()[0]

    meds_taken = conn.execute(
        "SELECT COUNT(*) FROM med_adherence WHERE patient_id=? AND date(created_at)=? AND status='taken'",
        (patient_id, today),
    ).fetchone()[0]
    meds_missed = conn.execute(
        "SELECT COUNT(*) FROM med_adherence WHERE patient_id=? AND date(created_at)=? AND status='missed'",
        (patient_id, today),
    ).fetchone()[0]

    cog_avg = conn.execute(
        "SELECT COALESCE(AVG(score), 0) FROM cognitive_scores WHERE patient_id=? AND date(created_at)=?",
        (patient_id, today),
    ).fetchone()[0]

    alerts = conn.execute(
        "SELECT COUNT(*) FROM behavior_events WHERE patient_id=? AND date(created_at)=? AND severity>=0.7",
        (patient_id, today),
    ).fetchone()[0]

    conn.execute(
        """INSERT OR REPLACE INTO daily_trends
           (patient_id, date, interaction_count, exercise_minutes, meds_taken, meds_missed, cognitive_avg, alerts_count)
           VALUES (?,?,?,?,?,?,?,?)""",
        (patient_id, today, interactions, exercise_secs / 60, meds_taken, meds_missed, cog_avg, alerts),
    )
    conn.commit()


def get_daily_trends(patient_id="default", days=30):
    conn = _get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM daily_trends WHERE patient_id=? AND date>=? ORDER BY date",
        (patient_id, cutoff),
    ).fetchall()
    return [dict(r) for r in rows]


def get_patient_summary(patient_id="default"):
    """Get a comprehensive patient summary for caregiver handoff."""
    med_rate = get_med_adherence_rate(patient_id, days=7)
    cog_decline = detect_cognitive_decline(patient_id)
    exercise = get_exercise_compliance(patient_id, days=7)
    recent_events = get_behavior_events(patient_id, days=1)
    trends = get_daily_trends(patient_id, days=7)

    total_exercise_min = sum(d.get("total_duration", 0) / 60 for d in exercise)
    high_severity = [e for e in recent_events if e["severity"] >= 0.7]

    return {
        "medication_adherence_7d": med_rate,
        "cognitive_decline_pct": cog_decline,
        "exercise_minutes_7d": round(total_exercise_min, 1),
        "exercise_sessions_7d": len(exercise),
        "high_severity_events_today": len(high_severity),
        "recent_events": recent_events[:10],
        "daily_trends": trends,
    }
