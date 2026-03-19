"""SQLite database layer — persistent storage for alerts, messages,
conversation log, and patient status. Shared between both apps."""

import json
import os
import sqlite3
import threading
from datetime import datetime

# Both apps use the same database file
DB_PATH = os.environ.get("REACHY_DB", os.path.join(os.path.dirname(__file__), "reachy.db"))

_local = threading.local()


def _get_conn():
    """Get a thread-local database connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")  # better concurrent access
    return _local.conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            message TEXT NOT NULL,
            details TEXT DEFAULT '',
            user_said TEXT DEFAULT '',
            time TEXT NOT NULL,
            acknowledged INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            priority TEXT DEFAULT 'normal',
            time TEXT NOT NULL,
            delivered INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS conversation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            speaker TEXT NOT NULL,
            text TEXT NOT NULL,
            time TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS patient_status (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS checkin_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            results TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mood_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mood TEXT NOT NULL,
            time TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            time TEXT NOT NULL,
            repeat TEXT DEFAULT 'once',
            active INTEGER DEFAULT 1,
            last_sent TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dosage TEXT DEFAULT '',
            times TEXT NOT NULL,
            notes TEXT DEFAULT '',
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS med_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            med_id INTEGER,
            status TEXT NOT NULL,
            time TEXT NOT NULL,
            scheduled_time TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            details TEXT DEFAULT '',
            time TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'caregiver',
            name TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS daily_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            report TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS caregiver_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER DEFAULT 0,
            note TEXT NOT NULL,
            author TEXT DEFAULT '',
            time TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS shift_handoffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_member TEXT NOT NULL,
            patient_id INTEGER DEFAULT 0,
            message TEXT NOT NULL,
            message_type TEXT DEFAULT 'text',
            read INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS vitals_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER DEFAULT 0,
            heart_rate INTEGER,
            spo2 INTEGER,
            bp_systolic INTEGER,
            bp_diastolic INTEGER,
            temperature REAL,
            source TEXT DEFAULT 'simulated',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS incident_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL DEFAULT 'default',
            incident_type TEXT NOT NULL,
            severity TEXT DEFAULT 'medium',
            description TEXT NOT NULL,
            actions_taken TEXT DEFAULT '',
            reported_by TEXT NOT NULL,
            resolved INTEGER DEFAULT 0,
            resolved_at TEXT,
            created_at TEXT NOT NULL
        );
    """)
    # Initialize patient status defaults
    defaults = {"mood": "unknown", "last_active": "", "last_said": "",
                "session_start": "", "name": ""}
    for k, v in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO patient_status (key, value) VALUES (?, ?)",
            (k, v),
        )
    conn.commit()
    print(f"[DB] Database ready: {DB_PATH}")


# ── Alerts ──────────────────────────────────────────────────────────

def add_alert(alert_type, message, details="", user_said="", time_str=None):
    conn = _get_conn()
    t = time_str or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        "INSERT INTO alerts (type, message, details, user_said, time) VALUES (?,?,?,?,?)",
        (alert_type, message, details, user_said, t),
    )
    conn.commit()
    return {
        "id": cur.lastrowid, "type": alert_type, "message": message,
        "details": details, "user_said": user_said, "time": t, "acknowledged": False,
    }


def get_alerts(limit=100):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) | {"acknowledged": bool(r["acknowledged"])} for r in rows]


def ack_alert(alert_id):
    conn = _get_conn()
    conn.execute("UPDATE alerts SET acknowledged=1 WHERE id=?", (alert_id,))
    conn.commit()


def clear_acked_alerts():
    conn = _get_conn()
    conn.execute("DELETE FROM alerts WHERE acknowledged=1")
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    return count


# ── Messages (caregiver → robot) ───────────────────────────────────

def add_message(text, priority="normal"):
    conn = _get_conn()
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        "INSERT INTO messages (text, priority, time) VALUES (?,?,?)",
        (text, priority, t),
    )
    conn.commit()
    return {
        "id": cur.lastrowid, "text": text, "priority": priority,
        "time": t, "delivered": False,
    }


def get_pending_messages():
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM messages WHERE delivered=0 ORDER BY id"
    ).fetchall()
    ids = [r["id"] for r in rows]
    if ids:
        conn.execute(
            f"UPDATE messages SET delivered=1 WHERE id IN ({','.join('?' * len(ids))})",
            ids,
        )
        conn.commit()
    return [dict(r) | {"delivered": True} for r in rows]


# ── Conversation ────────────────────────────────────────────────────

def add_conversation(speaker, text):
    conn = _get_conn()
    t = datetime.now().strftime("%H:%M:%S")
    conn.execute(
        "INSERT INTO conversation (speaker, text, time) VALUES (?,?,?)",
        (speaker, text, t),
    )
    conn.commit()
    return {"speaker": speaker, "text": text, "time": t}


def get_conversation(limit=50):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT speaker, text, time FROM conversation ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


# ── Patient status ──────────────────────────────────────────────────

def get_status():
    conn = _get_conn()
    rows = conn.execute("SELECT key, value FROM patient_status").fetchall()
    return {r["key"]: r["value"] for r in rows}


def update_status(**kwargs):
    conn = _get_conn()
    for k, v in kwargs.items():
        conn.execute(
            "INSERT OR REPLACE INTO patient_status (key, value) VALUES (?,?)",
            (k, str(v) if v is not None else ""),
        )
    conn.commit()


# ── Mood history ────────────────────────────────────────────────────

def add_mood(mood):
    conn = _get_conn()
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO mood_history (mood, time) VALUES (?,?)", (mood, t))
    conn.commit()


def get_mood_history(limit=50):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT mood, time FROM mood_history ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


# ── Check-in history ───────────────────────────────────────────────

def add_checkin(results):
    conn = _get_conn()
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO checkin_history (time, results) VALUES (?,?)",
        (t, json.dumps(results)),
    )
    conn.commit()


def get_checkin_history(limit=30):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT time, results FROM checkin_history ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [{"time": r["time"], "results": json.loads(r["results"])} for r in rows]


# ── Patients ────────────────────────────────────────────────────────

def add_patient(name, room="", age=None, conditions="", emergency_contact="", patient_type="elderly"):
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO patients (name, room, age, patient_type, conditions, emergency_contact) VALUES (?,?,?,?,?,?)",
        (name, room, age, patient_type, conditions, emergency_contact),
    )
    conn.commit()
    return get_patient(cur.lastrowid)


def get_patients():
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM patients ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_patient(patient_id):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
    return dict(row) if row else None


def delete_patient(patient_id):
    conn = _get_conn()
    conn.execute("DELETE FROM patients WHERE id=?", (patient_id,))
    conn.commit()


# ── Facilities ──────────────────────────────────────────────────────

def add_facility(name, address="", ftype="nursing_home", robots=0, contact=""):
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO facilities (name, address, type, robots, contact) VALUES (?,?,?,?,?)",
        (name, address, ftype, robots, contact),
    )
    conn.commit()
    return get_facility(cur.lastrowid)


def get_facilities():
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM facilities ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_facility(facility_id):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM facilities WHERE id=?", (facility_id,)).fetchone()
    return dict(row) if row else None


def delete_facility(facility_id):
    conn = _get_conn()
    conn.execute("DELETE FROM facilities WHERE id=?", (facility_id,))
    conn.commit()


# ── Settings ────────────────────────────────────────────────────────

def get_settings():
    conn = _get_conn()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def save_settings(**kwargs):
    conn = _get_conn()
    for k, v in kwargs.items():
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
            (k, str(v) if v is not None else ""),
        )
    conn.commit()


# ── Clear all ───────────────────────────────────────────────────────

def clear_all():
    conn = _get_conn()
    for table in ["alerts", "messages", "conversation", "mood_history",
                   "checkin_history", "activity_log", "med_log", "daily_reports"]:
        conn.execute(f"DELETE FROM {table}")
    conn.commit()


# ── Scheduled messages ──────────────────────────────────────────────

def add_scheduled_message(text, time_str, repeat="once"):
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO scheduled_messages (text, time, repeat) VALUES (?,?,?)",
        (text, time_str, repeat),
    )
    conn.commit()
    return get_scheduled_message(cur.lastrowid)


def get_scheduled_messages():
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM scheduled_messages ORDER BY time").fetchall()
    return [dict(r) | {"active": bool(r["active"])} for r in rows]


def get_scheduled_message(mid):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM scheduled_messages WHERE id=?", (mid,)).fetchone()
    return dict(row) | {"active": bool(row["active"])} if row else None


def get_due_scheduled_messages(current_time):
    """Get messages that should be sent now (HH:MM format)."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM scheduled_messages WHERE active=1 AND time=? AND last_sent!=?",
        (current_time, datetime.now().strftime("%Y-%m-%d")),
    ).fetchall()
    results = [dict(r) for r in rows]
    for r in results:
        conn.execute(
            "UPDATE scheduled_messages SET last_sent=? WHERE id=?",
            (datetime.now().strftime("%Y-%m-%d"), r["id"]),
        )
    conn.commit()
    return results


def delete_scheduled_message(mid):
    conn = _get_conn()
    conn.execute("DELETE FROM scheduled_messages WHERE id=?", (mid,))
    conn.commit()


def toggle_scheduled_message(mid):
    conn = _get_conn()
    conn.execute("UPDATE scheduled_messages SET active = NOT active WHERE id=?", (mid,))
    conn.commit()


# ── Medications ─────────────────────────────────────────────────────

def add_medication(name, dosage="", times="", notes=""):
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO medications (name, dosage, times, notes) VALUES (?,?,?,?)",
        (name, dosage, times, notes),
    )
    conn.commit()
    return get_medication(cur.lastrowid)


def get_medications():
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM medications ORDER BY name").fetchall()
    return [dict(r) | {"active": bool(r["active"])} for r in rows]


def get_medication(mid):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM medications WHERE id=?", (mid,)).fetchone()
    return dict(row) | {"active": bool(row["active"])} if row else None


def delete_medication(mid):
    conn = _get_conn()
    conn.execute("DELETE FROM medications WHERE id=?", (mid,))
    conn.commit()


def log_med_event(med_id, status, scheduled_time=""):
    conn = _get_conn()
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO med_log (med_id, status, time, scheduled_time) VALUES (?,?,?,?)",
        (med_id, status, t, scheduled_time),
    )
    conn.commit()


def get_med_log(limit=50):
    conn = _get_conn()
    rows = conn.execute("""
        SELECT ml.*, m.name as med_name FROM med_log ml
        LEFT JOIN medications m ON ml.med_id = m.id
        ORDER BY ml.id DESC LIMIT ?
    """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_med_log_today():
    conn = _get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT ml.*, m.name as med_name FROM med_log ml
        LEFT JOIN medications m ON ml.med_id = m.id
        WHERE ml.time LIKE ?
        ORDER BY ml.time
    """, (f"{today}%",)).fetchall()
    return [dict(r) for r in rows]


# ── Activity log ────────────────────────────────────────────────────

def add_activity(action, details=""):
    conn = _get_conn()
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO activity_log (action, details, time) VALUES (?,?,?)",
        (action, details, t),
    )
    conn.commit()


def get_activity_log(limit=100):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM activity_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


# ── Users / Auth ────────────────────────────────────────────────────

def add_user(username, password_hash, role="caregiver", name=""):
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, name) VALUES (?,?,?,?)",
            (username, password_hash, role, name),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def get_user(username):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None


def get_users():
    conn = _get_conn()
    rows = conn.execute("SELECT id, username, role, name FROM users ORDER BY username").fetchall()
    return [dict(r) for r in rows]


def delete_user(uid):
    conn = _get_conn()
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()


# ── Daily reports ───────────────────────────────────────────────────

def add_daily_report(report_text, date_str=None):
    conn = _get_conn()
    d = date_str or datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        "INSERT OR REPLACE INTO daily_reports (date, report) VALUES (?,?)",
        (d, report_text),
    )
    conn.commit()


def get_daily_reports(limit=30):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM daily_reports ORDER BY date DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def generate_daily_report():
    """Generate a summary report for today."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = _get_conn()

    alert_count = conn.execute(
        "SELECT COUNT(*) FROM alerts WHERE time LIKE ?", (f"{today}%",)
    ).fetchone()[0]

    convo_count = conn.execute(
        "SELECT COUNT(*) FROM conversation WHERE time LIKE ? OR time NOT LIKE '%-%'",
        (f"{today}%",)
    ).fetchone()[0]

    moods = conn.execute(
        "SELECT mood, COUNT(*) as cnt FROM mood_history WHERE time LIKE ? GROUP BY mood ORDER BY cnt DESC",
        (f"{today}%",)
    ).fetchall()
    mood_summary = ", ".join(f"{r['mood']}({r['cnt']})" for r in moods) if moods else "No data"

    med_taken = conn.execute(
        "SELECT COUNT(*) FROM med_log WHERE time LIKE ? AND status='taken'", (f"{today}%",)
    ).fetchone()[0]
    med_missed = conn.execute(
        "SELECT COUNT(*) FROM med_log WHERE time LIKE ? AND status='missed'", (f"{today}%",)
    ).fetchone()[0]

    activities = conn.execute(
        "SELECT COUNT(*) FROM activity_log WHERE time LIKE ?", (f"{today}%",)
    ).fetchone()[0]

    report = (
        f"Daily Report — {today}\n"
        f"Alerts: {alert_count}\n"
        f"Conversations: {convo_count} messages\n"
        f"Moods: {mood_summary}\n"
        f"Medications: {med_taken} taken, {med_missed} missed\n"
        f"Activities logged: {activities}"
    )
    add_daily_report(report, today)
    return report


# ── Caregiver Notes ─────────────────────────────────────────────

def add_note(note, author="", patient_id=0):
    conn = _get_conn()
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        "INSERT INTO caregiver_notes (patient_id, note, author, time) VALUES (?,?,?,?)",
        (patient_id, note, author, t),
    )
    conn.commit()
    return {"id": cur.lastrowid, "patient_id": patient_id, "note": note, "author": author, "time": t}


def get_notes(patient_id=None, limit=50):
    conn = _get_conn()
    if patient_id is not None:
        rows = conn.execute(
            "SELECT * FROM caregiver_notes WHERE patient_id=? ORDER BY id DESC LIMIT ?",
            (patient_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM caregiver_notes ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def delete_note(note_id):
    conn = _get_conn()
    conn.execute("DELETE FROM caregiver_notes WHERE id=?", (note_id,))
    conn.commit()


# ── Shift Handoffs ──────────────────────────────────────────────────

def create_shift_handoff(from_caregiver, to_caregiver=""):
    """Auto-generate a shift handoff report from today's data."""
    conn = _get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Alerts summary
    alert_rows = conn.execute(
        "SELECT type, message FROM alerts WHERE time LIKE ? ORDER BY id DESC LIMIT 10",
        (f"{today}%",),
    ).fetchall()
    alerts_summary = "; ".join(f"{r['type']}: {r['message']}" for r in alert_rows) if alert_rows else "No alerts"

    # Mood summary
    mood_rows = conn.execute(
        "SELECT mood, COUNT(*) as cnt FROM mood_history WHERE time LIKE ? GROUP BY mood ORDER BY cnt DESC",
        (f"{today}%",),
    ).fetchall()
    mood_summary = ", ".join(f"{r['mood']}({r['cnt']})" for r in mood_rows) if mood_rows else "No mood data"

    # Medication summary
    med_taken = conn.execute(
        "SELECT COUNT(*) FROM med_log WHERE time LIKE ? AND status='taken'", (f"{today}%",)
    ).fetchone()[0]
    med_missed = conn.execute(
        "SELECT COUNT(*) FROM med_log WHERE time LIKE ? AND status='missed'", (f"{today}%",)
    ).fetchone()[0]
    med_summary = f"{med_taken} taken, {med_missed} missed"

    # Recent notes
    note_rows = conn.execute(
        "SELECT note, author FROM caregiver_notes WHERE time LIKE ? ORDER BY id DESC LIMIT 5",
        (f"{today}%",),
    ).fetchall()
    notes = "; ".join(f"{r['author']}: {r['note']}" for r in note_rows) if note_rows else ""

    # Activity count
    activity_count = conn.execute(
        "SELECT COUNT(*) FROM activity_log WHERE time LIKE ?", (f"{today}%",)
    ).fetchone()[0]

    summary = (
        f"Shift handoff — {today}\n"
        f"From: {from_caregiver}\n"
        f"Activities: {activity_count} logged\n"
        f"Alerts: {alerts_summary}\n"
        f"Moods: {mood_summary}\n"
        f"Medications: {med_summary}\n"
    )
    if notes:
        summary += f"Notes: {notes}\n"

    cur = conn.execute(
        """INSERT INTO shift_handoffs
           (from_caregiver, to_caregiver, summary, alerts_summary, mood_summary, med_summary, notes, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (from_caregiver, to_caregiver, summary, alerts_summary, mood_summary, med_summary, notes, now),
    )
    conn.commit()
    return {
        "id": cur.lastrowid, "from_caregiver": from_caregiver,
        "to_caregiver": to_caregiver, "summary": summary,
        "created_at": now,
    }


def get_shift_handoffs(limit=20):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM shift_handoffs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


# ── Family Messages ─────────────────────────────────────────────────

def add_family_message(family_member, message, patient_id=0, message_type="text"):
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        "INSERT INTO family_messages (family_member, patient_id, message, message_type, created_at) VALUES (?,?,?,?,?)",
        (family_member, patient_id, message, message_type, now),
    )
    conn.commit()
    return {"id": cur.lastrowid, "family_member": family_member, "message": message, "created_at": now}


def get_family_messages(patient_id=None, limit=50):
    conn = _get_conn()
    if patient_id is not None:
        rows = conn.execute(
            "SELECT * FROM family_messages WHERE patient_id=? ORDER BY id DESC LIMIT ?",
            (patient_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM family_messages ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def mark_family_message_read(msg_id):
    conn = _get_conn()
    conn.execute("UPDATE family_messages SET read=1 WHERE id=?", (msg_id,))
    conn.commit()


# ── Vitals Log ──────────────────────────────────────────────────────

def add_vitals(heart_rate=None, spo2=None, bp_sys=None, bp_dia=None,
               temperature=None, source="simulated", patient_id=0):
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """INSERT INTO vitals_log
           (patient_id, heart_rate, spo2, bp_systolic, bp_diastolic, temperature, source, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (patient_id, heart_rate, spo2, bp_sys, bp_dia, temperature, source, now),
    )
    conn.commit()


def get_vitals_history(patient_id=0, limit=50):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM vitals_log WHERE patient_id=? ORDER BY id DESC LIMIT ?",
        (patient_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_latest_vitals(patient_id=0):
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM vitals_log WHERE patient_id=? ORDER BY id DESC LIMIT 1",
        (patient_id,),
    ).fetchone()
    return dict(row) if row else None


def update_user_password(username, new_hash):
    conn = _get_conn()
    conn.execute("UPDATE users SET password_hash=? WHERE username=?", (new_hash, username))
    conn.commit()


def update_user_role(username, role):
    conn = _get_conn()
    conn.execute("UPDATE users SET role=? WHERE username=?", (role, username))
    conn.commit()


# ── Bot data stubs (SQLite fallback) ────────────────────────────────
# These mirror the db_postgres.py bot functions so the dashboard
# doesn't crash when running without Supabase.

# ── Incident Reports ────────────────────────────────────────────────

def add_incident(patient_id, incident_type, severity, description, actions_taken, reported_by):
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        """INSERT INTO incident_reports
           (patient_id, incident_type, severity, description, actions_taken, reported_by, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (patient_id, incident_type, severity, description, actions_taken, reported_by, now),
    )
    conn.commit()
    return get_incident(cur.lastrowid)


def get_incidents(patient_id=None, limit=100):
    conn = _get_conn()
    if patient_id:
        rows = conn.execute(
            "SELECT * FROM incident_reports WHERE patient_id=? ORDER BY id DESC LIMIT ?",
            (patient_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM incident_reports ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_incident(incident_id):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM incident_reports WHERE id=?", (incident_id,)).fetchone()
    return dict(row) if row else None


def resolve_incident(incident_id):
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE incident_reports SET resolved=1, resolved_at=? WHERE id=?",
        (now, incident_id),
    )
    conn.commit()


def delete_incident(incident_id):
    conn = _get_conn()
    conn.execute("DELETE FROM incident_reports WHERE id=?", (incident_id,))
    conn.commit()


def get_bot_conversations(patient_id="default", limit=500):
    return []

def get_bot_moods(patient_id="default", limit=50):
    return []

def get_bot_session_summaries(patient_id="default", limit=20):
    return []

def get_bot_facts(patient_id="default"):
    return []

def get_bot_alerts(patient_id="default", limit=50):
    return []

def get_bot_profile(patient_id="default"):
    return None

def get_bot_weekly_reports(patient_id="default", limit=4):
    return []

def get_bot_cognitive_scores(patient_id="default", limit=20):
    return []

def get_bot_exercises(patient_id="default", limit=20):
    return []

def get_bot_sleep_log(patient_id="default", limit=14):
    return []

def get_bot_reminders(patient_id="default"):
    return []

def get_bot_streaks(patient_id="default"):
    return 0
