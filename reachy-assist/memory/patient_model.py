"""Patient model — tracks cognitive decline, exercise compliance,
medication adherence, and behavioral patterns over time.
Surfaces trends and alerts to caregivers.

Backend selection:
  Set SUPABASE_DB_URL or DATABASE_URL to a postgresql:// connection
  string to use Postgres.  Otherwise falls back to local SQLite.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from core.log_config import get_logger

logger = get_logger("patient_model")

# ── Backend detection ───────────────────────────────────────────────

_PG_URL = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL", "")
_use_postgres = bool(_PG_URL)

MODEL_DB = os.environ.get(
    "REACHY_MODEL_DB",
    os.path.join(os.path.dirname(__file__), "patient_model.db"),
)

_local = threading.local()


# ── Connection helpers ──────────────────────────────────────────────

def _get_conn():
    if _use_postgres:
        return _get_pg_conn()
    return _get_sqlite_conn()


def _get_sqlite_conn():
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(MODEL_DB, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
    return _local.conn


def _get_pg_conn():
    if not hasattr(_local, "conn") or _local.conn is None or _local.conn.closed:
        import psycopg2
        _local.conn = psycopg2.connect(_PG_URL)
        _local.conn.autocommit = True
    return _local.conn


def _ph():
    """Return the placeholder style for the active backend."""
    return "%s" if _use_postgres else "?"


def _execute(sql, params=None, fetch=False, fetchone=False):
    """Unified query runner."""
    conn = _get_conn()
    if _use_postgres:
        import psycopg2.extras
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            if fetchone:
                row = cur.fetchone()
                return dict(row) if row else None
            if fetch:
                return [dict(r) for r in cur.fetchall()]
        return None
    else:
        cur = conn.execute(sql, params or ())
        if fetchone:
            row = cur.fetchone()
            return dict(row) if row else None
        if fetch:
            return [dict(r) for r in cur.fetchall()]
        conn.commit()
        return cur


# ── Database initialisation ─────────────────────────────────────────

def init_model_db():
    conn = _get_conn()
    if _use_postgres:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cognitive_scores (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT DEFAULT 'default',
                    game_type TEXT NOT NULL,
                    score REAL NOT NULL,
                    max_score REAL DEFAULT 0,
                    duration_seconds REAL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS exercise_compliance (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT DEFAULT 'default',
                    exercise_type TEXT NOT NULL,
                    completed INTEGER DEFAULT 1,
                    duration_seconds REAL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS med_adherence (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT DEFAULT 'default',
                    medication TEXT NOT NULL,
                    status TEXT NOT NULL,
                    scheduled_time TEXT DEFAULT '',
                    actual_time TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS behavior_events (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT DEFAULT 'default',
                    event_type TEXT NOT NULL,
                    details TEXT DEFAULT '',
                    severity REAL DEFAULT 0.5,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS daily_trends (
                    id SERIAL PRIMARY KEY,
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
        logger.info("PostgreSQL database ready: %s...", _PG_URL[:40])
    else:
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
        logger.info("Database ready: %s", MODEL_DB)


# ── Cognitive tracking ──────────────────────────────────────────────

def log_cognitive_score(game_type, score, max_score=0, duration=0, patient_id="default"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    p = _ph()
    _execute(
        f"INSERT INTO cognitive_scores (patient_id, game_type, score, max_score, duration_seconds, created_at)"
        f" VALUES ({p},{p},{p},{p},{p},{p})",
        (patient_id, game_type, score, max_score, duration, now),
    )


def get_cognitive_trend(patient_id="default", days=30):
    """Get cognitive score trend over time."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    p = _ph()
    return _execute(
        f"SELECT date(created_at) as day, game_type, AVG(score) as avg_score,"
        f" COUNT(*) as games_played"
        f" FROM cognitive_scores WHERE patient_id={p} AND created_at>={p}"
        f" GROUP BY day, game_type ORDER BY day",
        (patient_id, cutoff),
        fetch=True,
    ) or []


def detect_cognitive_decline(patient_id="default"):
    """Compare recent 7-day avg vs previous 7-day avg. Returns decline percentage."""
    now = datetime.now()
    recent_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_start = (now - timedelta(days=14)).strftime("%Y-%m-%d")
    p = _ph()

    recent = _execute(
        f"SELECT AVG(score) as avg FROM cognitive_scores WHERE patient_id={p} AND created_at>={p}",
        (patient_id, recent_start),
        fetchone=True,
    )
    prev = _execute(
        f"SELECT AVG(score) as avg FROM cognitive_scores WHERE patient_id={p} AND created_at>={p} AND created_at<{p}",
        (patient_id, prev_start, recent_start),
        fetchone=True,
    )

    if not recent or not prev or not recent["avg"] or not prev["avg"]:
        return None
    decline = ((prev["avg"] - recent["avg"]) / prev["avg"]) * 100
    return round(decline, 1)


# ── Exercise compliance ─────────────────────────────────────────────

def log_exercise(exercise_type, completed=True, duration=0, patient_id="default"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    p = _ph()
    _execute(
        f"INSERT INTO exercise_compliance (patient_id, exercise_type, completed, duration_seconds, created_at)"
        f" VALUES ({p},{p},{p},{p},{p})",
        (patient_id, exercise_type, int(completed), duration, now),
    )


def get_exercise_compliance(patient_id="default", days=30):
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    p = _ph()
    return _execute(
        f"SELECT date(created_at) as day, COUNT(*) as total,"
        f" SUM(completed) as completed, SUM(duration_seconds) as total_duration"
        f" FROM exercise_compliance WHERE patient_id={p} AND created_at>={p}"
        f" GROUP BY day ORDER BY day",
        (patient_id, cutoff),
        fetch=True,
    ) or []


# ── Medication adherence ────────────────────────────────────────────

def log_med_adherence(medication, status, scheduled_time="", patient_id="default"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    p = _ph()
    _execute(
        f"INSERT INTO med_adherence (patient_id, medication, status, scheduled_time, actual_time, created_at)"
        f" VALUES ({p},{p},{p},{p},{p},{p})",
        (patient_id, medication, status, scheduled_time, now, now),
    )


def get_med_adherence_rate(patient_id="default", days=30):
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    p = _ph()
    total_row = _execute(
        f"SELECT COUNT(*) as cnt FROM med_adherence WHERE patient_id={p} AND created_at>={p}",
        (patient_id, cutoff),
        fetchone=True,
    )
    taken_row = _execute(
        f"SELECT COUNT(*) as cnt FROM med_adherence WHERE patient_id={p} AND created_at>={p} AND status='taken'",
        (patient_id, cutoff),
        fetchone=True,
    )
    total = total_row["cnt"] if total_row else 0
    taken = taken_row["cnt"] if taken_row else 0
    if total == 0:
        return 100.0
    return round((taken / total) * 100, 1)


# ── Behavior events ─────────────────────────────────────────────────

def log_behavior_event(event_type, details="", severity=0.5, patient_id="default"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    p = _ph()
    _execute(
        f"INSERT INTO behavior_events (patient_id, event_type, details, severity, created_at)"
        f" VALUES ({p},{p},{p},{p},{p})",
        (patient_id, event_type, details, severity, now),
    )


def get_behavior_events(patient_id="default", days=7, event_type=None):
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    p = _ph()
    if event_type:
        return _execute(
            f"SELECT * FROM behavior_events WHERE patient_id={p} AND created_at>={p} AND event_type={p}"
            f" ORDER BY created_at DESC",
            (patient_id, cutoff, event_type),
            fetch=True,
        ) or []
    return _execute(
        f"SELECT * FROM behavior_events WHERE patient_id={p} AND created_at>={p}"
        f" ORDER BY created_at DESC",
        (patient_id, cutoff),
        fetch=True,
    ) or []


# ── Daily trend aggregation ─────────────────────────────────────────

def update_daily_trend(patient_id="default"):
    """Aggregate today's data into the daily_trends table."""
    today = datetime.now().strftime("%Y-%m-%d")
    p = _ph()

    interactions = (_execute(
        f"SELECT COUNT(*) as cnt FROM behavior_events WHERE patient_id={p} AND date(created_at)={p}",
        (patient_id, today), fetchone=True,
    ) or {}).get("cnt", 0)

    exercise_secs = (_execute(
        f"SELECT COALESCE(SUM(duration_seconds), 0) as total FROM exercise_compliance"
        f" WHERE patient_id={p} AND date(created_at)={p}",
        (patient_id, today), fetchone=True,
    ) or {}).get("total", 0)

    meds_taken = (_execute(
        f"SELECT COUNT(*) as cnt FROM med_adherence"
        f" WHERE patient_id={p} AND date(created_at)={p} AND status='taken'",
        (patient_id, today), fetchone=True,
    ) or {}).get("cnt", 0)

    meds_missed = (_execute(
        f"SELECT COUNT(*) as cnt FROM med_adherence"
        f" WHERE patient_id={p} AND date(created_at)={p} AND status='missed'",
        (patient_id, today), fetchone=True,
    ) or {}).get("cnt", 0)

    cog_avg = (_execute(
        f"SELECT COALESCE(AVG(score), 0) as avg FROM cognitive_scores"
        f" WHERE patient_id={p} AND date(created_at)={p}",
        (patient_id, today), fetchone=True,
    ) or {}).get("avg", 0)

    alerts = (_execute(
        f"SELECT COUNT(*) as cnt FROM behavior_events"
        f" WHERE patient_id={p} AND date(created_at)={p} AND severity>=0.7",
        (patient_id, today), fetchone=True,
    ) or {}).get("cnt", 0)

    if _use_postgres:
        _execute(
            "INSERT INTO daily_trends"
            " (patient_id, date, interaction_count, exercise_minutes, meds_taken, meds_missed, cognitive_avg, alerts_count)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
            " ON CONFLICT (patient_id, date) DO UPDATE SET"
            "  interaction_count=EXCLUDED.interaction_count,"
            "  exercise_minutes=EXCLUDED.exercise_minutes,"
            "  meds_taken=EXCLUDED.meds_taken,"
            "  meds_missed=EXCLUDED.meds_missed,"
            "  cognitive_avg=EXCLUDED.cognitive_avg,"
            "  alerts_count=EXCLUDED.alerts_count",
            (patient_id, today, interactions, exercise_secs / 60,
             meds_taken, meds_missed, cog_avg, alerts),
        )
    else:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO daily_trends"
            " (patient_id, date, interaction_count, exercise_minutes, meds_taken, meds_missed, cognitive_avg, alerts_count)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (patient_id, today, interactions, exercise_secs / 60,
             meds_taken, meds_missed, cog_avg, alerts),
        )
        conn.commit()


def get_daily_trends(patient_id="default", days=30):
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    p = _ph()
    return _execute(
        f"SELECT * FROM daily_trends WHERE patient_id={p} AND date>={p} ORDER BY date",
        (patient_id, cutoff),
        fetch=True,
    ) or []


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
