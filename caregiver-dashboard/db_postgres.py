"""PostgreSQL/Supabase database backend — drop-in replacement for SQLite db.py.

Activated by setting environment variables:
  DATABASE_URL=postgresql://user:pass@host:port/dbname
  or
  SUPABASE_DB_URL=postgresql://user:pass@db.xxx.supabase.co:5432/postgres

Falls back to SQLite if no Postgres URL is configured.

Usage:
  import db_postgres as db   # instead of: import db
  db.init_db()               # same API as db.py
"""

import json
import os
import threading
from datetime import datetime

_pool = None
_local = threading.local()

DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL", "")


def _is_postgres():
    return bool(DATABASE_URL)


def _get_conn():
    """Get a thread-local Postgres connection."""
    if not hasattr(_local, "conn") or _local.conn is None or _local.conn.closed:
        import psycopg2
        import psycopg2.extras
        _local.conn = psycopg2.connect(DATABASE_URL)
        _local.conn.autocommit = True
    return _local.conn


def _execute(query, params=None, fetch=False, fetchone=False):
    """Execute a query and optionally fetch results as dicts."""
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


def init_db():
    """Create tables if they don't exist (Postgres syntax)."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id SERIAL PRIMARY KEY,
                type TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT DEFAULT '',
                user_said TEXT DEFAULT '',
                time TEXT NOT NULL,
                acknowledged INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                text TEXT NOT NULL,
                priority TEXT DEFAULT 'normal',
                time TEXT NOT NULL,
                delivered INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS conversation (
                id SERIAL PRIMARY KEY,
                speaker TEXT NOT NULL,
                text TEXT NOT NULL,
                time TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS patient_status (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS checkin_history (
                id SERIAL PRIMARY KEY,
                time TEXT NOT NULL,
                results TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS mood_history (
                id SERIAL PRIMARY KEY,
                mood TEXT NOT NULL,
                time TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS patients (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                room TEXT DEFAULT '',
                age INTEGER,
                patient_type TEXT DEFAULT 'elderly',
                conditions TEXT DEFAULT '',
                emergency_contact TEXT DEFAULT '',
                mood TEXT DEFAULT 'unknown',
                last_active TEXT DEFAULT '',
                alerts_today INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active'
            );
            CREATE TABLE IF NOT EXISTS facilities (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT DEFAULT '',
                type TEXT DEFAULT 'nursing_home',
                robots INTEGER DEFAULT 0,
                patients INTEGER DEFAULT 0,
                contact TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS scheduled_messages (
                id SERIAL PRIMARY KEY,
                text TEXT NOT NULL,
                time TEXT NOT NULL,
                repeat TEXT DEFAULT 'once',
                active INTEGER DEFAULT 1,
                last_sent TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS medications (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                dosage TEXT DEFAULT '',
                times TEXT NOT NULL,
                notes TEXT DEFAULT '',
                active INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS med_log (
                id SERIAL PRIMARY KEY,
                med_id INTEGER,
                status TEXT NOT NULL,
                time TEXT NOT NULL,
                scheduled_time TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS activity_log (
                id SERIAL PRIMARY KEY,
                action TEXT NOT NULL,
                details TEXT DEFAULT '',
                time TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'caregiver',
                name TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS daily_reports (
                id SERIAL PRIMARY KEY,
                date TEXT NOT NULL,
                report TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS caregiver_notes (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER DEFAULT 0,
                note TEXT NOT NULL,
                author TEXT DEFAULT '',
                time TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS shift_handoffs (
                id SERIAL PRIMARY KEY,
                from_caregiver TEXT NOT NULL,
                to_caregiver TEXT DEFAULT '',
                summary TEXT NOT NULL,
                alerts_summary TEXT DEFAULT '',
                mood_summary TEXT DEFAULT '',
                med_summary TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS family_messages (
                id SERIAL PRIMARY KEY,
                family_member TEXT NOT NULL,
                patient_id INTEGER DEFAULT 0,
                message TEXT NOT NULL,
                message_type TEXT DEFAULT 'text',
                read INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS vitals_log (
                id SERIAL PRIMARY KEY,
                patient_id INTEGER DEFAULT 0,
                heart_rate INTEGER,
                spo2 INTEGER,
                bp_systolic INTEGER,
                bp_diastolic INTEGER,
                temperature REAL,
                source TEXT DEFAULT 'simulated',
                created_at TEXT NOT NULL
            );
        """)
    # Initialize patient status defaults
    defaults = {"mood": "unknown", "last_active": "", "last_said": "",
                "session_start": "", "name": ""}
    with conn.cursor() as cur:
        for k, v in defaults.items():
            cur.execute(
                "INSERT INTO patient_status (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
                (k, v),
            )
    print(f"[DB] PostgreSQL database ready: {DATABASE_URL[:40]}...")


# ── Alerts ──────────────────────────────────────────────────────────

def add_alert(alert_type, message, details="", user_said="", time_str=None):
    t = time_str or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = _execute(
        "INSERT INTO alerts (type, message, details, user_said, time) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (alert_type, message, details, user_said, t), fetchone=True,
    )
    return {"id": row["id"], "type": alert_type, "message": message,
            "details": details, "user_said": user_said, "time": t, "acknowledged": False}


def get_alerts(limit=100):
    rows = _execute("SELECT * FROM alerts ORDER BY id DESC LIMIT %s", (limit,), fetch=True)
    for r in rows:
        r["acknowledged"] = bool(r["acknowledged"])
    return rows


def ack_alert(alert_id):
    _execute("UPDATE alerts SET acknowledged=1 WHERE id=%s", (alert_id,))


def clear_acked_alerts():
    _execute("DELETE FROM alerts WHERE acknowledged=1")
    row = _execute("SELECT COUNT(*) as cnt FROM alerts", fetchone=True)
    return row["cnt"]


# ── Messages ────────────────────────────────────────────────────────

def add_message(text, priority="normal"):
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = _execute(
        "INSERT INTO messages (text, priority, time) VALUES (%s,%s,%s) RETURNING id",
        (text, priority, t), fetchone=True,
    )
    return {"id": row["id"], "text": text, "priority": priority, "time": t, "delivered": False}


def get_pending_messages():
    rows = _execute("SELECT * FROM messages WHERE delivered=0 ORDER BY id", fetch=True)
    if rows:
        ids = [r["id"] for r in rows]
        _execute("UPDATE messages SET delivered=1 WHERE id = ANY(%s)", (ids,))
    return [dict(r) | {"delivered": True} for r in rows]


# ── Conversation ────────────────────────────────────────────────────

def add_conversation(speaker, text):
    t = datetime.now().strftime("%H:%M:%S")
    _execute("INSERT INTO conversation (speaker, text, time) VALUES (%s,%s,%s)", (speaker, text, t))
    return {"speaker": speaker, "text": text, "time": t}


def get_conversation(limit=50):
    rows = _execute(
        "SELECT speaker, text, time FROM conversation ORDER BY id DESC LIMIT %s", (limit,), fetch=True
    )
    return list(reversed(rows))


# ── Status ──────────────────────────────────────────────────────────

def get_status():
    rows = _execute("SELECT key, value FROM patient_status", fetch=True)
    return {r["key"]: r["value"] for r in rows}


def update_status(**kwargs):
    for k, v in kwargs.items():
        _execute(
            "INSERT INTO patient_status (key, value) VALUES (%s,%s) ON CONFLICT (key) DO UPDATE SET value=%s",
            (k, str(v) if v is not None else "", str(v) if v is not None else ""),
        )


# ── Mood ────────────────────────────────────────────────────────────

def add_mood(mood):
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _execute("INSERT INTO mood_history (mood, time) VALUES (%s,%s)", (mood, t))


def get_mood_history(limit=50):
    rows = _execute("SELECT mood, time FROM mood_history ORDER BY id DESC LIMIT %s", (limit,), fetch=True)
    return list(reversed(rows))


# ── Check-in ────────────────────────────────────────────────────────

def add_checkin(results):
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _execute("INSERT INTO checkin_history (time, results) VALUES (%s,%s)", (t, json.dumps(results)))


def get_checkin_history(limit=30):
    rows = _execute("SELECT time, results FROM checkin_history ORDER BY id DESC LIMIT %s", (limit,), fetch=True)
    return [{"time": r["time"], "results": json.loads(r["results"])} for r in rows]


# ── Patients ────────────────────────────────────────────────────────

def add_patient(name, room="", age=None, conditions="", emergency_contact="", patient_type="elderly"):
    row = _execute(
        "INSERT INTO patients (name, room, age, patient_type, conditions, emergency_contact) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (name, room, age, patient_type, conditions, emergency_contact), fetchone=True,
    )
    return get_patient(row["id"])


def get_patients():
    return _execute("SELECT * FROM patients ORDER BY name", fetch=True)


def get_patient(patient_id):
    return _execute("SELECT * FROM patients WHERE id=%s", (patient_id,), fetchone=True)


def delete_patient(patient_id):
    _execute("DELETE FROM patients WHERE id=%s", (patient_id,))


# ── Facilities ──────────────────────────────────────────────────────

def add_facility(name, address="", ftype="nursing_home", robots=0, contact=""):
    row = _execute(
        "INSERT INTO facilities (name, address, type, robots, contact) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (name, address, ftype, robots, contact), fetchone=True,
    )
    return get_facility(row["id"])


def get_facilities():
    return _execute("SELECT * FROM facilities ORDER BY name", fetch=True)


def get_facility(facility_id):
    return _execute("SELECT * FROM facilities WHERE id=%s", (facility_id,), fetchone=True)


def delete_facility(facility_id):
    _execute("DELETE FROM facilities WHERE id=%s", (facility_id,))


# ── Settings ────────────────────────────────────────────────────────

def get_settings():
    rows = _execute("SELECT key, value FROM settings", fetch=True)
    return {r["key"]: r["value"] for r in rows}


def save_settings(**kwargs):
    for k, v in kwargs.items():
        _execute(
            "INSERT INTO settings (key, value) VALUES (%s,%s) ON CONFLICT (key) DO UPDATE SET value=%s",
            (k, str(v) if v is not None else "", str(v) if v is not None else ""),
        )


def clear_all():
    for table in ["alerts", "messages", "conversation", "mood_history",
                   "checkin_history", "activity_log", "med_log", "daily_reports"]:
        _execute(f"DELETE FROM {table}")


# ── Scheduled messages ──────────────────────────────────────────────

def add_scheduled_message(text, time_str, repeat="once"):
    row = _execute(
        "INSERT INTO scheduled_messages (text, time, repeat) VALUES (%s,%s,%s) RETURNING id",
        (text, time_str, repeat), fetchone=True,
    )
    return get_scheduled_message(row["id"])


def get_scheduled_messages():
    rows = _execute("SELECT * FROM scheduled_messages ORDER BY time", fetch=True)
    for r in rows:
        r["active"] = bool(r["active"])
    return rows


def get_scheduled_message(mid):
    r = _execute("SELECT * FROM scheduled_messages WHERE id=%s", (mid,), fetchone=True)
    if r:
        r["active"] = bool(r["active"])
    return r


def get_due_scheduled_messages(current_time):
    today = datetime.now().strftime("%Y-%m-%d")
    rows = _execute(
        "SELECT * FROM scheduled_messages WHERE active=1 AND time=%s AND last_sent!=%s",
        (current_time, today), fetch=True,
    )
    for r in rows:
        _execute("UPDATE scheduled_messages SET last_sent=%s WHERE id=%s", (today, r["id"]))
    return rows


def delete_scheduled_message(mid):
    _execute("DELETE FROM scheduled_messages WHERE id=%s", (mid,))


def toggle_scheduled_message(mid):
    _execute("UPDATE scheduled_messages SET active = CASE WHEN active=1 THEN 0 ELSE 1 END WHERE id=%s", (mid,))


# ── Medications ─────────────────────────────────────────────────────

def add_medication(name, dosage="", times="", notes=""):
    row = _execute(
        "INSERT INTO medications (name, dosage, times, notes) VALUES (%s,%s,%s,%s) RETURNING id",
        (name, dosage, times, notes), fetchone=True,
    )
    return get_medication(row["id"])


def get_medications():
    rows = _execute("SELECT * FROM medications ORDER BY name", fetch=True)
    for r in rows:
        r["active"] = bool(r["active"])
    return rows


def get_medication(mid):
    r = _execute("SELECT * FROM medications WHERE id=%s", (mid,), fetchone=True)
    if r:
        r["active"] = bool(r["active"])
    return r


def delete_medication(mid):
    _execute("DELETE FROM medications WHERE id=%s", (mid,))


def log_med_event(med_id, status, scheduled_time=""):
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _execute(
        "INSERT INTO med_log (med_id, status, time, scheduled_time) VALUES (%s,%s,%s,%s)",
        (med_id, status, t, scheduled_time),
    )


def get_med_log(limit=50):
    return _execute("""
        SELECT ml.*, m.name as med_name FROM med_log ml
        LEFT JOIN medications m ON ml.med_id = m.id
        ORDER BY ml.id DESC LIMIT %s
    """, (limit,), fetch=True)


def get_med_log_today():
    today = datetime.now().strftime("%Y-%m-%d")
    return _execute("""
        SELECT ml.*, m.name as med_name FROM med_log ml
        LEFT JOIN medications m ON ml.med_id = m.id
        WHERE ml.time LIKE %s ORDER BY ml.time
    """, (f"{today}%",), fetch=True)


# ── Activity log ────────────────────────────────────────────────────

def add_activity(action, details=""):
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _execute("INSERT INTO activity_log (action, details, time) VALUES (%s,%s,%s)", (action, details, t))


def get_activity_log(limit=100):
    return _execute("SELECT * FROM activity_log ORDER BY id DESC LIMIT %s", (limit,), fetch=True)


# ── Users ───────────────────────────────────────────────────────────

def add_user(username, password_hash, role="caregiver", name=""):
    try:
        _execute(
            "INSERT INTO users (username, password_hash, role, name) VALUES (%s,%s,%s,%s)",
            (username, password_hash, role, name),
        )
        return True
    except Exception:
        return False


def get_user(username):
    return _execute("SELECT * FROM users WHERE username=%s", (username,), fetchone=True)


def get_users():
    return _execute("SELECT id, username, role, name FROM users ORDER BY username", fetch=True)


def delete_user(uid):
    _execute("DELETE FROM users WHERE id=%s", (uid,))


def update_user_password(username, new_hash):
    _execute("UPDATE users SET password_hash=%s WHERE username=%s", (new_hash, username))


def update_user_role(username, role):
    _execute("UPDATE users SET role=%s WHERE username=%s", (role, username))


# ── Daily reports ───────────────────────────────────────────────────

def add_daily_report(report_text, date_str=None):
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    _execute(
        "INSERT INTO daily_reports (date, report) VALUES (%s,%s) ON CONFLICT DO NOTHING",
        (d, report_text),
    )


def get_daily_reports(limit=30):
    return _execute("SELECT * FROM daily_reports ORDER BY date DESC LIMIT %s", (limit,), fetch=True)


def generate_daily_report():
    today = datetime.now().strftime("%Y-%m-%d")
    alert_count = _execute(
        "SELECT COUNT(*) as cnt FROM alerts WHERE time LIKE %s", (f"{today}%",), fetchone=True
    )["cnt"]
    convo_count = _execute(
        "SELECT COUNT(*) as cnt FROM conversation", fetchone=True
    )["cnt"]
    moods = _execute(
        "SELECT mood, COUNT(*) as cnt FROM mood_history WHERE time LIKE %s GROUP BY mood ORDER BY cnt DESC",
        (f"{today}%",), fetch=True,
    )
    mood_summary = ", ".join(f"{r['mood']}({r['cnt']})" for r in moods) if moods else "No data"
    med_taken = _execute(
        "SELECT COUNT(*) as cnt FROM med_log WHERE time LIKE %s AND status='taken'", (f"{today}%",), fetchone=True
    )["cnt"]
    med_missed = _execute(
        "SELECT COUNT(*) as cnt FROM med_log WHERE time LIKE %s AND status='missed'", (f"{today}%",), fetchone=True
    )["cnt"]
    activities = _execute(
        "SELECT COUNT(*) as cnt FROM activity_log WHERE time LIKE %s", (f"{today}%",), fetchone=True
    )["cnt"]
    report = (
        f"Daily Report — {today}\nAlerts: {alert_count}\nConversations: {convo_count} messages\n"
        f"Moods: {mood_summary}\nMedications: {med_taken} taken, {med_missed} missed\n"
        f"Activities logged: {activities}"
    )
    add_daily_report(report, today)
    return report


# ── Caregiver Notes ─────────────────────────────────────────────────

def add_note(note, author="", patient_id=0):
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = _execute(
        "INSERT INTO caregiver_notes (patient_id, note, author, time) VALUES (%s,%s,%s,%s) RETURNING id",
        (patient_id, note, author, t), fetchone=True,
    )
    return {"id": row["id"], "patient_id": patient_id, "note": note, "author": author, "time": t}


def get_notes(patient_id=None, limit=50):
    if patient_id is not None:
        return _execute(
            "SELECT * FROM caregiver_notes WHERE patient_id=%s ORDER BY id DESC LIMIT %s",
            (patient_id, limit), fetch=True,
        )
    return _execute("SELECT * FROM caregiver_notes ORDER BY id DESC LIMIT %s", (limit,), fetch=True)


def delete_note(note_id):
    _execute("DELETE FROM caregiver_notes WHERE id=%s", (note_id,))


# ── Shift Handoffs ──────────────────────────────────────────────────

def create_shift_handoff(from_caregiver, to_caregiver=""):
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    alerts = _execute(
        "SELECT type, message FROM alerts WHERE time LIKE %s ORDER BY id DESC LIMIT 10",
        (f"{today}%",), fetch=True,
    )
    alerts_summary = "; ".join(f"{r['type']}: {r['message']}" for r in alerts) if alerts else "No alerts"
    moods = _execute(
        "SELECT mood, COUNT(*) as cnt FROM mood_history WHERE time LIKE %s GROUP BY mood ORDER BY cnt DESC",
        (f"{today}%",), fetch=True,
    )
    mood_summary = ", ".join(f"{r['mood']}({r['cnt']})" for r in moods) if moods else "No mood data"
    med_taken = _execute("SELECT COUNT(*) as cnt FROM med_log WHERE time LIKE %s AND status='taken'", (f"{today}%",), fetchone=True)["cnt"]
    med_missed = _execute("SELECT COUNT(*) as cnt FROM med_log WHERE time LIKE %s AND status='missed'", (f"{today}%",), fetchone=True)["cnt"]
    med_summary = f"{med_taken} taken, {med_missed} missed"
    note_rows = _execute("SELECT note, author FROM caregiver_notes WHERE time LIKE %s ORDER BY id DESC LIMIT 5", (f"{today}%",), fetch=True)
    notes = "; ".join(f"{r['author']}: {r['note']}" for r in note_rows) if note_rows else ""
    activity_count = _execute("SELECT COUNT(*) as cnt FROM activity_log WHERE time LIKE %s", (f"{today}%",), fetchone=True)["cnt"]
    summary = f"Shift handoff — {today}\nFrom: {from_caregiver}\nActivities: {activity_count} logged\nAlerts: {alerts_summary}\nMoods: {mood_summary}\nMedications: {med_summary}\n"
    if notes:
        summary += f"Notes: {notes}\n"
    row = _execute(
        "INSERT INTO shift_handoffs (from_caregiver, to_caregiver, summary, alerts_summary, mood_summary, med_summary, notes, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (from_caregiver, to_caregiver, summary, alerts_summary, mood_summary, med_summary, notes, now), fetchone=True,
    )
    return {"id": row["id"], "from_caregiver": from_caregiver, "to_caregiver": to_caregiver, "summary": summary, "created_at": now}


def get_shift_handoffs(limit=20):
    return _execute("SELECT * FROM shift_handoffs ORDER BY id DESC LIMIT %s", (limit,), fetch=True)


# ── Family Messages ─────────────────────────────────────────────────

def add_family_message(family_member, message, patient_id=0, message_type="text"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = _execute(
        "INSERT INTO family_messages (family_member, patient_id, message, message_type, created_at) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (family_member, patient_id, message, message_type, now), fetchone=True,
    )
    return {"id": row["id"], "family_member": family_member, "message": message, "created_at": now}


def get_family_messages(patient_id=None, limit=50):
    if patient_id is not None:
        return _execute("SELECT * FROM family_messages WHERE patient_id=%s ORDER BY id DESC LIMIT %s", (patient_id, limit), fetch=True)
    return _execute("SELECT * FROM family_messages ORDER BY id DESC LIMIT %s", (limit,), fetch=True)


def mark_family_message_read(msg_id):
    _execute("UPDATE family_messages SET read=1 WHERE id=%s", (msg_id,))


# ── Vitals ──────────────────────────────────────────────────────────

def add_vitals(heart_rate=None, spo2=None, bp_sys=None, bp_dia=None,
               temperature=None, source="simulated", patient_id=0):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _execute(
        "INSERT INTO vitals_log (patient_id, heart_rate, spo2, bp_systolic, bp_diastolic, temperature, source, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (patient_id, heart_rate, spo2, bp_sys, bp_dia, temperature, source, now),
    )


def get_vitals_history(patient_id=0, limit=50):
    return _execute("SELECT * FROM vitals_log WHERE patient_id=%s ORDER BY id DESC LIMIT %s", (patient_id, limit), fetch=True)


def get_latest_vitals(patient_id=0):
    return _execute("SELECT * FROM vitals_log WHERE patient_id=%s ORDER BY id DESC LIMIT 1", (patient_id,), fetchone=True)


# ── Incident Reports ────────────────────────────────────────────────

def add_incident(patient_id, incident_type, severity, description, actions_taken, reported_by):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = _execute(
        """INSERT INTO incident_reports
           (patient_id, incident_type, severity, description, actions_taken, reported_by, created_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (patient_id, incident_type, severity, description, actions_taken, reported_by, now),
        fetchone=True,
    )
    return get_incident(row["id"])


def get_incidents(patient_id=None, limit=100):
    if patient_id:
        return _execute(
            "SELECT * FROM incident_reports WHERE patient_id=%s ORDER BY id DESC LIMIT %s",
            (patient_id, limit), fetch=True,
        ) or []
    return _execute(
        "SELECT * FROM incident_reports ORDER BY id DESC LIMIT %s",
        (limit,), fetch=True,
    ) or []


def get_incident(incident_id):
    return _execute(
        "SELECT * FROM incident_reports WHERE id=%s", (incident_id,), fetchone=True
    )


def resolve_incident(incident_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _execute(
        "UPDATE incident_reports SET resolved=TRUE, resolved_at=%s WHERE id=%s",
        (now, incident_id),
    )


def delete_incident(incident_id):
    _execute("DELETE FROM incident_reports WHERE id=%s", (incident_id,))


# ══════════════════════════════════════════════════════════════════════
# Bot Tables — read from Reachy's bot_* tables (same Supabase DB)
# These are written by the robot and read by the dashboard.
# ══════════════════════════════════════════════════════════════════════

def get_bot_conversations(patient_id="default", limit=500):
    """Read from bot_conversation_log — Reachy's actual conversation data.
    Has richer data than the dashboard's conversation table: topic, emotion, speaker."""
    return _execute(
        "SELECT id, patient_id, topic, text, speaker, emotion, created_at "
        "FROM bot_conversation_log WHERE patient_id=%s ORDER BY id DESC LIMIT %s",
        (patient_id, limit), fetch=True,
    ) or []


def get_bot_moods(patient_id="default", limit=50):
    """Read from bot_mood_journal — mood with hour and day_of_week."""
    return _execute(
        "SELECT id, mood, hour, day_of_week, created_at "
        "FROM bot_mood_journal WHERE patient_id=%s ORDER BY id DESC LIMIT %s",
        (patient_id, limit), fetch=True,
    ) or []


def get_bot_session_summaries(patient_id="default", limit=20):
    """Read from bot_session_summaries — end-of-session reports."""
    rows = _execute(
        "SELECT id, interactions, dominant_mood, mood_distribution, topics_discussed, "
        "facts_learned, duration_minutes, created_at "
        "FROM bot_session_summaries WHERE patient_id=%s ORDER BY id DESC LIMIT %s",
        (patient_id, limit), fetch=True,
    ) or []
    for r in rows:
        # Parse JSON strings into real objects
        for field in ("mood_distribution", "topics_discussed", "facts_learned"):
            val = r.get(field, "")
            if isinstance(val, str):
                try:
                    r[field] = json.loads(val)
                except Exception:
                    pass
    return rows


def get_bot_facts(patient_id="default"):
    """Read from bot_patient_facts — things Reachy learned about the patient."""
    return _execute(
        "SELECT id, category, fact, created_at "
        "FROM bot_patient_facts WHERE patient_id=%s ORDER BY category, id DESC",
        (patient_id,), fetch=True,
    ) or []


def get_bot_alerts(patient_id="default", limit=50):
    """Read from bot_caregiver_alerts — alerts generated by the robot."""
    return _execute(
        "SELECT id, alert_type, message, severity, acknowledged, created_at "
        "FROM bot_caregiver_alerts WHERE patient_id=%s ORDER BY id DESC LIMIT %s",
        (patient_id, limit), fetch=True,
    ) or []


def get_bot_profile(patient_id="default"):
    """Read from bot_patient_profile — name, preferred name, personality notes."""
    return _execute(
        "SELECT patient_id, name, preferred_name, age, favorite_topic, personality_notes, updated_at "
        "FROM bot_patient_profile WHERE patient_id=%s",
        (patient_id,), fetchone=True,
    )


def get_bot_weekly_reports(patient_id="default", limit=4):
    """Read from bot_weekly_reports — auto-generated weekly summaries."""
    rows = _execute(
        "SELECT id, week_start, total_sessions, total_interactions, mood_summary, "
        "top_topics, cognitive_avg, streak_days, report_text, created_at "
        "FROM bot_weekly_reports WHERE patient_id=%s ORDER BY week_start DESC LIMIT %s",
        (patient_id, limit), fetch=True,
    ) or []
    for r in rows:
        for field in ("mood_summary", "top_topics"):
            val = r.get(field, "")
            if isinstance(val, str):
                try:
                    r[field] = json.loads(val)
                except Exception:
                    pass
    return rows


def get_bot_cognitive_scores(patient_id="default", limit=20):
    """Read from bot_cognitive_scores — game results."""
    return _execute(
        "SELECT id, game_type, score, max_score, duration_seconds, created_at "
        "FROM bot_cognitive_scores WHERE patient_id=%s ORDER BY id DESC LIMIT %s",
        (patient_id, limit), fetch=True,
    ) or []


def get_bot_exercises(patient_id="default", limit=20):
    """Read from bot_exercise_log."""
    return _execute(
        "SELECT id, exercise_name, completed, duration_seconds, created_at "
        "FROM bot_exercise_log WHERE patient_id=%s ORDER BY id DESC LIMIT %s",
        (patient_id, limit), fetch=True,
    ) or []


def get_bot_sleep_log(patient_id="default", limit=14):
    """Read from bot_sleep_log."""
    return _execute(
        "SELECT id, event_type, quality, notes, created_at "
        "FROM bot_sleep_log WHERE patient_id=%s ORDER BY id DESC LIMIT %s",
        (patient_id, limit), fetch=True,
    ) or []


def get_bot_reminders(patient_id="default"):
    """Read from bot_reminders."""
    return _execute(
        "SELECT id, reminder_type, text, time, repeat_pattern, active, created_at "
        "FROM bot_reminders WHERE patient_id=%s ORDER BY id DESC",
        (patient_id,), fetch=True,
    ) or []


def get_bot_streaks(patient_id="default"):
    """Read from bot_streaks — conversation dates for streak calculation."""
    rows = _execute(
        "SELECT conversation_date FROM bot_streaks WHERE patient_id=%s "
        "ORDER BY conversation_date DESC LIMIT 60",
        (patient_id,), fetch=True,
    ) or []
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
