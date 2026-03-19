"""Caregiver Dashboard — receives alerts from Reachy, displays them in
real-time, and lets caregivers send messages back through the robot.
All data persisted in SQLite. Includes auth, scheduling, med tracking,
shift handoffs, family portal, vitals monitoring, and i18n."""

import hashlib
import json
import os
import queue
import threading
from datetime import datetime
from functools import wraps
from pathlib import Path

# Load .env file from the dashboard directory
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from flask import Flask, request, jsonify, render_template, Response, session, redirect, url_for
from flask_cors import CORS
from validators import (
    sanitize, sanitize_short, require_json, require_fields,
    validate_time_format, validate_role, validate_username, validate_repeat,
    validate_med_status, validate_priority, validate_patient_type,
    validate_int_range, validate_float_range, check_login_rate_limit,
    MAX_TEXT, MAX_NOTE, MAX_SHORT, MAX_PASSWORD, MIN_PASSWORD,
)
import db

# Auto-detect PostgreSQL/Supabase — use Postgres backend if configured
_pg_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL", "")
if _pg_url:
    try:
        import db_postgres
        db = db_postgres
        print("[APP] Using PostgreSQL/Supabase database backend")
    except ImportError:
        print("[APP] psycopg2 not installed — falling back to SQLite")
        print("[APP] Install with: pip install psycopg2-binary")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "reachy-care-secret-key-change-me")
CORS(app)

# ── Global error handlers ───────────────────────────────────────────

@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": str(e.description) if hasattr(e, 'description') else "Bad request"}), 400

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    return redirect(url_for("login_page"))

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500

# i18n — inject translation function into all templates
from i18n import t as _t, set_language, get_language, available_languages

@app.context_processor
def inject_i18n():
    lang = session.get("lang") or request.args.get("lang") or "en"
    set_language(lang)
    user = session.get("user", {})
    user_role = user.get("role", "")
    return {"t": _t, "current_lang": lang, "available_languages": available_languages(),
            "user_role": user_role, "user_name": user.get("name", "")}

# Try bcrypt, fall back to sha256
try:
    import bcrypt
    _USE_BCRYPT = True
    print("[AUTH] Using bcrypt for password hashing")
except ImportError:
    _USE_BCRYPT = False
    print("[AUTH] bcrypt not installed, using sha256 (install bcrypt for production)")


def _hash_password(password):
    if _USE_BCRYPT:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    return hashlib.sha256(password.encode()).hexdigest()


def _check_password(password, stored_hash):
    if _USE_BCRYPT:
        try:
            return bcrypt.checkpw(password.encode(), stored_hash.encode())
        except Exception:
            # Fall back to sha256 check for legacy hashes
            return hashlib.sha256(password.encode()).hexdigest() == stored_hash
    return hashlib.sha256(password.encode()).hexdigest() == stored_hash

# Serve PWA static files
@app.route("/manifest.json")
def manifest():
    return app.send_static_file("manifest.json")

@app.route("/sw.js")
def service_worker():
    resp = app.send_static_file("sw.js")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Content-Type"] = "application/javascript"
    return resp

@app.route("/icons/<path:filename>")
def icons(filename):
    return app.send_static_file(f"icons/{filename}")

db.init_db()

# Seed default users — one per role for testing
_seed_users = [
    ("admin", "admin", "admin", "Administrator"),
    ("nurse", "nurse", "caregiver", "Nurse Maria"),
    ("family", "family", "family", "Sarah (Daughter)"),
]
for _u, _p, _r, _n in _seed_users:
    if not db.get_user(_u):
        db.add_user(_u, _hash_password(_p), role=_r, name=_n)
        print(f"[AUTH] Created user: {_u} / {_p} (role: {_r})")

sse_listeners = []


def notify_listeners(event_type, data):
    dead = []
    for q in sse_listeners:
        try:
            q.put_nowait({"event": event_type, "data": data})
        except Exception:
            dead.append(q)
    for q in dead:
        if q in sse_listeners:
            sse_listeners.remove(q)


def sse_stream():
    q = queue.Queue()
    sse_listeners.append(q)
    try:
        while True:
            item = q.get()
            event = item["event"]
            data = json.dumps(item["data"])
            yield f"event: {event}\ndata: {data}\n\n"
    except GeneratorExit:
        if q in sse_listeners:
            sse_listeners.remove(q)


# ── Auth helpers ────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            # Allow API calls from the robot without auth
            if request.path.startswith("/api/") and request.method == "POST":
                api_key = request.headers.get("X-Robot-Key", "")
                if api_key == "reachy-robot":
                    return f(*args, **kwargs)
            if request.path.startswith("/api/"):
                return f(*args, **kwargs)  # API endpoints open for now
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


@app.route("/set-lang/<lang>")
def switch_lang(lang):
    if lang in available_languages():
        session["lang"] = lang
    return redirect(request.referrer or "/")


@app.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html", active_page="login")


@app.route("/login", methods=["POST"])
def login_action():
    if check_login_rate_limit(request.remote_addr):
        return jsonify({"error": "Too many login attempts. Try again in 5 minutes."}), 429
    data, err = require_json()
    if err:
        return err
    username = sanitize_short(data.get("username", ""))
    password = data.get("password", "")  # don't sanitize passwords
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    user = db.get_user(username)
    if user and _check_password(password, user["password_hash"]):
        session["user"] = {"username": username, "role": user["role"], "name": user["name"]}
        db.add_activity("login", f"{username} logged in")
        return jsonify({"status": "ok"})
    return jsonify({"error": "Invalid credentials"}), 401


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login_page"))


# ── Page routes ─────────────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html", active_page="dashboard")

@app.route("/patients")
@login_required
def patients_page():
    return render_template("patients.html", active_page="patients")

@app.route("/history")
@login_required
def history_page():
    return render_template("history.html", active_page="history")

@app.route("/facilities")
@login_required
def facilities_page():
    return render_template("facilities.html", active_page="facilities")

@app.route("/medications")
@login_required
def medications_page():
    return render_template("medications.html", active_page="medications")

@app.route("/schedule")
@login_required
def schedule_page():
    return render_template("schedule.html", active_page="schedule")

@app.route("/reports")
@login_required
def reports_page():
    return render_template("reports.html", active_page="reports")

@app.route("/camera")
@login_required
def camera_page():
    return render_template("camera.html", active_page="camera")

@app.route("/activity")
@login_required
def activity_page():
    return render_template("activity.html", active_page="activity")

@app.route("/settings")
@login_required
def settings_page():
    return render_template("settings.html", active_page="settings")

# ── Alert API ───────────────────────────────────────────────────────

@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    return jsonify(db.get_alerts())

@app.route("/api/alerts", methods=["POST"])
def post_alert():
    data, err = require_json()
    if err:
        return err
    message = sanitize(data.get("message", ""))
    if not message:
        return jsonify({"error": "Message is required"}), 400
    alert = db.add_alert(
        alert_type=sanitize_short(data.get("type", "INFO")),
        message=message,
        details=sanitize(data.get("details", "")),
        user_said=sanitize(data.get("user_said", "")),
        time_str=data.get("time"),
    )
    db.add_activity("alert", f"{alert['type']}: {alert['message']}")
    notify_listeners("alert", alert)
    return jsonify({"status": "ok", "id": alert["id"]}), 201

@app.route("/api/alerts/<int:alert_id>/ack", methods=["POST"])
def ack_alert(alert_id):
    db.ack_alert(alert_id)
    return jsonify({"status": "ok"})

@app.route("/api/alerts/clear", methods=["POST"])
def clear_alerts():
    remaining = db.clear_acked_alerts()
    return jsonify({"status": "ok", "remaining": remaining})

@app.route("/api/activity/stats", methods=["GET"])
def activity_stats():
    activities = db.get_activity_log()
    counts = {}
    for a in activities:
        action = a["action"]
        counts[action] = counts.get(action, 0) + 1
    return jsonify(counts)


# ── Messages API ────────────────────────────────────────────────────

@app.route("/api/messages", methods=["POST"])
def send_message():
    data, err = require_json()
    if err:
        return err
    text = sanitize(data.get("text", ""))
    if not text:
        return jsonify({"error": "Message text is required"}), 400
    priority = data.get("priority", "normal")
    if not validate_priority(priority):
        priority = "normal"
    msg = db.add_message(text=text, priority=priority)
    entry = db.add_conversation("caregiver", msg["text"])
    db.add_activity("message_sent", f"Caregiver: {msg['text'][:50]}")
    notify_listeners("message_sent", msg)
    notify_listeners("conversation", entry)
    return jsonify({"status": "ok", "id": msg["id"]}), 201

@app.route("/api/messages/pending", methods=["GET"])
def get_pending_messages():
    pending = db.get_pending_messages()
    # Also check scheduled messages
    now = datetime.now().strftime("%H:%M")
    scheduled = db.get_due_scheduled_messages(now)
    for s in scheduled:
        pending.append({"id": s["id"], "text": s["text"], "priority": "scheduled", "delivered": True})
        db.add_activity("scheduled_message", f"Sent: {s['text'][:50]}")
    return jsonify(pending)

# ── Conversation API ────────────────────────────────────────────────

@app.route("/api/conversation", methods=["GET"])
def get_conversation():
    limit = request.args.get("limit", 200, type=int)
    return jsonify(db.get_conversation(limit=limit))

@app.route("/api/conversation", methods=["POST"])
def post_conversation():
    data, err = require_json()
    if err:
        return err
    speaker = sanitize_short(data.get("speaker", "patient"))
    text = sanitize(data.get("text", ""))
    if not text:
        return jsonify({"error": "Text is required"}), 400
    if speaker not in ("patient", "reachy", "caregiver"):
        speaker = "patient"
    entry = db.add_conversation(speaker, text)
    if speaker == "patient":
        db.update_status(last_said=text, last_active=datetime.now().strftime("%H:%M:%S"))
        db.add_activity("patient_spoke", text[:80])
    notify_listeners("conversation", entry)
    return jsonify({"status": "ok"})

# ── Memory Book API ─────────────────────────────────────────────────

@app.route("/memory-book")
@login_required
def memory_book_page():
    return render_template("memory_book.html", active_page="memory_book")


# ── Status API ──────────────────────────────────────────────────────

@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify(db.get_status())

@app.route("/api/status", methods=["POST"])
def update_status():
    data, err = require_json()
    if err:
        return err
    # Sanitize all string values
    clean = {sanitize_short(k): sanitize(str(v)) for k, v in data.items()}
    db.update_status(**clean)
    if "mood" in data:
        db.add_mood(sanitize_short(str(data["mood"])))
    status = db.get_status()
    notify_listeners("status", status)
    return jsonify({"status": "ok"})


# ── History API ─────────────────────────────────────────────────────

@app.route("/api/mood-history", methods=["GET"])
def mood_history():
    return jsonify(db.get_mood_history())

@app.route("/api/checkin-history", methods=["GET"])
def checkin_history():
    return jsonify(db.get_checkin_history())

@app.route("/api/checkin-history", methods=["POST"])
def post_checkin():
    data, err = require_json()
    if err:
        return err
    results = data.get("results", {})
    if not isinstance(results, dict):
        return jsonify({"error": "Results must be a JSON object"}), 400
    db.add_checkin(results)
    db.add_activity("checkin", f"Results: {results}")
    return jsonify({"status": "ok"})

# ── Patients API ────────────────────────────────────────────────────

@app.route("/api/patients", methods=["GET"])
def get_patients():
    return jsonify(db.get_patients())

@app.route("/api/patients", methods=["POST"])
def add_patient():
    data, err = require_json()
    if err:
        return err
    name = sanitize_short(data.get("name", ""))
    if not name:
        return jsonify({"error": "Patient name is required"}), 400
    patient_type = data.get("patient_type", "elderly")
    if not validate_patient_type(patient_type):
        patient_type = "elderly"
    age = data.get("age")
    if age is not None and not validate_int_range(age, 0, 150):
        return jsonify({"error": "Age must be between 0 and 150"}), 400
    patient = db.add_patient(
        name=name, room=sanitize_short(data.get("room", "")),
        age=age, conditions=sanitize(data.get("conditions", "")),
        emergency_contact=sanitize_short(data.get("emergency_contact", "")),
        patient_type=patient_type,
    )
    db.add_activity("patient_added", f"Added: {patient['name']}")
    return jsonify(patient), 201

@app.route("/api/patients/<int:pid>", methods=["DELETE"])
def delete_patient(pid):
    db.delete_patient(pid)
    return jsonify({"status": "ok"})

# ── Facilities API ──────────────────────────────────────────────────

@app.route("/api/facilities", methods=["GET"])
def get_facilities():
    return jsonify(db.get_facilities())

@app.route("/api/facilities", methods=["POST"])
def add_facility():
    data, err = require_json()
    if err:
        return err
    name = sanitize_short(data.get("name", ""))
    if not name:
        return jsonify({"error": "Facility name is required"}), 400
    robots = data.get("robots", 0)
    if not validate_int_range(robots, 0, 10000):
        return jsonify({"error": "Robots count must be 0-10000"}), 400
    facility = db.add_facility(
        name=name, address=sanitize(data.get("address", "")),
        ftype=sanitize_short(data.get("type", "nursing_home")),
        robots=robots,
        contact=sanitize_short(data.get("contact", "")),
    )
    return jsonify(facility), 201

@app.route("/api/facilities/<int:fid>", methods=["DELETE"])
def delete_facility(fid):
    db.delete_facility(fid)
    return jsonify({"status": "ok"})


# ── Scheduled Messages API ──────────────────────────────────────────

@app.route("/api/scheduled", methods=["GET"])
def get_scheduled():
    return jsonify(db.get_scheduled_messages())

@app.route("/api/scheduled", methods=["POST"])
def add_scheduled():
    data, err = require_json()
    if err:
        return err
    text = sanitize(data.get("text", ""))
    time_str = data.get("time", "").strip()
    if not text:
        return jsonify({"error": "Message text is required"}), 400
    if not time_str or not validate_time_format(time_str):
        return jsonify({"error": "Time must be in HH:MM format"}), 400
    repeat = data.get("repeat", "once")
    if not validate_repeat(repeat):
        repeat = "once"
    msg = db.add_scheduled_message(text=text, time_str=time_str, repeat=repeat)
    db.add_activity("schedule_added", f"'{msg['text'][:30]}' at {msg['time']}")
    return jsonify(msg), 201

@app.route("/api/scheduled/<int:sid>", methods=["DELETE"])
def delete_scheduled(sid):
    db.delete_scheduled_message(sid)
    return jsonify({"status": "ok"})

@app.route("/api/scheduled/<int:sid>/toggle", methods=["POST"])
def toggle_scheduled(sid):
    db.toggle_scheduled_message(sid)
    return jsonify({"status": "ok"})

# ── Medications API ─────────────────────────────────────────────────

@app.route("/api/medications", methods=["GET"])
def get_medications():
    return jsonify(db.get_medications())

@app.route("/api/medications", methods=["POST"])
def add_medication():
    data, err = require_json()
    if err:
        return err
    name = sanitize_short(data.get("name", ""))
    if not name:
        return jsonify({"error": "Medication name is required"}), 400
    med = db.add_medication(
        name=name, dosage=sanitize_short(data.get("dosage", "")),
        times=sanitize_short(data.get("times", "")), notes=sanitize(data.get("notes", "")),
    )
    db.add_activity("med_added", f"Added: {med['name']} {med['dosage']}")
    return jsonify(med), 201

@app.route("/api/medications/<int:mid>", methods=["DELETE"])
def delete_medication(mid):
    db.delete_medication(mid)
    return jsonify({"status": "ok"})

@app.route("/api/medications/<int:mid>/log", methods=["POST"])
def log_medication(mid):
    data, err = require_json()
    if err:
        return err
    status = data.get("status", "taken")
    if not validate_med_status(status):
        return jsonify({"error": f"Invalid status. Must be: taken, missed, skipped, late"}), 400
    db.log_med_event(mid, status, sanitize_short(data.get("scheduled_time", "")))
    med = db.get_medication(mid)
    name = med["name"] if med else "Unknown"
    db.add_activity("med_log", f"{name}: {status}")
    return jsonify({"status": "ok"})

@app.route("/api/med-log", methods=["GET"])
def get_med_log():
    return jsonify(db.get_med_log())

@app.route("/api/med-log/today", methods=["GET"])
def get_med_log_today():
    return jsonify(db.get_med_log_today())


# ── Activity Log API ────────────────────────────────────────────────

@app.route("/api/activity", methods=["GET"])
def get_activity():
    return jsonify(db.get_activity_log())

@app.route("/api/activity", methods=["POST"])
def post_activity():
    data, err = require_json()
    if err:
        return err
    db.add_activity(sanitize_short(data.get("action", "")), sanitize(data.get("details", "")))
    return jsonify({"status": "ok"})

# ── Reports API ─────────────────────────────────────────────────────

@app.route("/api/reports", methods=["GET"])
def get_reports():
    return jsonify(db.get_daily_reports())

@app.route("/api/reports/generate", methods=["POST"])
def generate_report():
    report = db.generate_daily_report()
    return jsonify({"status": "ok", "report": report})

# ── Settings API ────────────────────────────────────────────────────

@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify(db.get_settings())

@app.route("/api/settings", methods=["POST"])
def save_settings():
    data, err = require_json()
    if err:
        return err
    # Sanitize all keys and values
    clean = {sanitize_short(k): sanitize_short(str(v)) for k, v in data.items()}
    db.save_settings(**clean)
    return jsonify({"status": "ok"})

@app.route("/api/clear-all", methods=["POST"])
def clear_all():
    db.clear_all()
    return jsonify({"status": "ok"})

# ── Caregiver Notes API ─────────────────────────────────────────────

@app.route("/api/notes", methods=["GET"])
def get_notes():
    pid = request.args.get("patient_id", type=int)
    return jsonify(db.get_notes(patient_id=pid))

@app.route("/api/notes", methods=["POST"])
def add_note():
    data, err = require_json()
    if err:
        return err
    note_text = sanitize(data.get("note", ""), MAX_NOTE)
    if not note_text:
        return jsonify({"error": "Note text is required"}), 400
    user = session.get("user", {})
    note = db.add_note(
        note=note_text,
        author=user.get("name", user.get("username", "Unknown")),
        patient_id=data.get("patient_id", 0),
    )
    db.add_activity("note_added", f"{note['author']}: {note['note'][:50]}")
    return jsonify(note), 201

@app.route("/api/notes/<int:nid>", methods=["DELETE"])
def delete_note(nid):
    db.delete_note(nid)
    return jsonify({"status": "ok"})

@app.route("/family")
def family_page():
    return render_template("family.html", active_page="family")

# ── Shift Handoff API ──────────────────────────────────────────────

@app.route("/api/handoff", methods=["POST"])
@login_required
def create_handoff():
    user = session.get("user", {})
    data, err = require_json()
    if err:
        return err
    handoff = db.create_shift_handoff(
        from_caregiver=user.get("name", user.get("username", "Unknown")),
        to_caregiver=sanitize_short(data.get("to_caregiver", "")),
    )
    db.add_activity("shift_handoff", f"Handoff by {handoff['from_caregiver']}")
    return jsonify(handoff), 201

@app.route("/api/handoff", methods=["GET"])
def get_handoffs():
    return jsonify(db.get_shift_handoffs())

# ── Family Portal API ──────────────────────────────────────────────

@app.route("/api/family/messages", methods=["GET"])
def get_family_messages():
    pid = request.args.get("patient_id", type=int)
    return jsonify(db.get_family_messages(patient_id=pid))

@app.route("/api/family/messages", methods=["POST"])
def post_family_message():
    data, err = require_json()
    if err:
        return err
    message = sanitize(data.get("message", ""))
    if not message:
        return jsonify({"error": "Message is required"}), 400
    family_member = sanitize_short(data.get("family_member", "Family"))
    msg = db.add_family_message(
        family_member=family_member,
        message=message,
        patient_id=data.get("patient_id", 0),
        message_type=sanitize_short(data.get("type", "text")),
    )
    db.add_message(text=f"Message from your family: {msg['message']}", priority="normal")
    db.add_activity("family_message", f"{msg['family_member']}: {msg['message'][:50]}")
    notify_listeners("family_message", msg)
    return jsonify(msg), 201

@app.route("/api/family/messages/<int:mid>/read", methods=["POST"])
def mark_family_read(mid):
    db.mark_family_message_read(mid)
    return jsonify({"status": "ok"})

# ── Vitals API ─────────────────────────────────────────────────────

@app.route("/api/vitals", methods=["GET"])
def get_vitals():
    pid = request.args.get("patient_id", 0, type=int)
    return jsonify(db.get_vitals_history(patient_id=pid))

@app.route("/api/vitals", methods=["POST"])
def post_vitals():
    data, err = require_json()
    if err:
        return err
    hr = data.get("heart_rate")
    spo2 = data.get("spo2")
    bp_sys = data.get("bp_systolic")
    bp_dia = data.get("bp_diastolic")
    temp = data.get("temperature")
    if hr is not None and not validate_int_range(hr, 20, 300):
        return jsonify({"error": "Heart rate must be 20-300 bpm"}), 400
    if spo2 is not None and not validate_int_range(spo2, 0, 100):
        return jsonify({"error": "SpO2 must be 0-100%"}), 400
    if bp_sys is not None and not validate_int_range(bp_sys, 40, 300):
        return jsonify({"error": "Systolic BP must be 40-300"}), 400
    if bp_dia is not None and not validate_int_range(bp_dia, 20, 200):
        return jsonify({"error": "Diastolic BP must be 20-200"}), 400
    if temp is not None and not validate_float_range(temp, 85.0, 115.0):
        return jsonify({"error": "Temperature must be 85-115°F"}), 400
    db.add_vitals(
        heart_rate=hr, spo2=spo2, bp_sys=bp_sys, bp_dia=bp_dia,
        temperature=temp,
        source=sanitize_short(data.get("source", "device")),
        patient_id=data.get("patient_id", 0),
    )
    alerts = []
    if hr and (hr < 50 or hr > 120):
        alerts.append(f"Abnormal heart rate: {hr} bpm")
    if spo2 and spo2 < 90:
        alerts.append(f"Low oxygen: {spo2}%")
    for alert_msg in alerts:
        alert = db.add_alert("VITALS_ALERT", alert_msg, details=json.dumps(data))
        notify_listeners("alert", alert)
    return jsonify({"status": "ok", "alerts": alerts})

@app.route("/api/vitals/latest", methods=["GET"])
def get_latest_vitals():
    pid = request.args.get("patient_id", 0, type=int)
    v = db.get_latest_vitals(patient_id=pid)
    return jsonify(v or {})

# ── Incident Reports API ───────────────────────────────────────────

VALID_INCIDENT_TYPES = ('fall', 'wandering', 'agitation', 'medication_error', 'injury', 'other')
VALID_SEVERITIES = ('low', 'medium', 'high', 'critical')

@app.route("/incidents")
@login_required
def incidents_page():
    return render_template("incidents.html", active_page="incidents")

@app.route("/api/incidents", methods=["GET"])
@login_required
def get_incidents():
    pid = request.args.get("patient_id")
    return jsonify(db.get_incidents(patient_id=pid))

@app.route("/api/incidents", methods=["POST"])
@login_required
def create_incident():
    data, err = require_json()
    if err:
        return err
    incident_type = data.get("incident_type", "")
    if incident_type not in VALID_INCIDENT_TYPES:
        return jsonify({"error": f"incident_type must be one of: {', '.join(VALID_INCIDENT_TYPES)}"}), 400
    severity = data.get("severity", "medium")
    if severity not in VALID_SEVERITIES:
        return jsonify({"error": f"severity must be one of: {', '.join(VALID_SEVERITIES)}"}), 400
    description = sanitize(data.get("description", ""))
    if not description:
        return jsonify({"error": "Description is required"}), 400
    reported_by = session.get("username", "unknown")
    incident = db.add_incident(
        patient_id=sanitize_short(data.get("patient_id", "default")),
        incident_type=incident_type,
        severity=severity,
        description=description,
        actions_taken=sanitize(data.get("actions_taken", "")),
        reported_by=reported_by,
    )
    db.add_activity("incident_reported", f"{severity} {incident_type} by {reported_by}")
    if severity in ("high", "critical"):
        alert = db.add_alert("INCIDENT", f"{severity.upper()} incident: {incident_type}", details=description)
        notify_listeners("alert", alert)
    return jsonify(incident), 201

@app.route("/api/incidents/<int:iid>/resolve", methods=["POST"])
@login_required
def resolve_incident(iid):
    db.resolve_incident(iid)
    db.add_activity("incident_resolved", f"Incident #{iid} resolved")
    return jsonify({"status": "ok"})

@app.route("/api/incidents/<int:iid>", methods=["DELETE"])
@login_required
def delete_incident(iid):
    db.delete_incident(iid)
    return jsonify({"status": "ok"})

# ── User Management API ────────────────────────────────────────────

@app.route("/api/users", methods=["GET"])
@login_required
def get_users():
    return jsonify(db.get_users())

@app.route("/api/users", methods=["POST"])
@login_required
def create_user():
    data, err = require_json()
    if err:
        return err
    username = data.get("username", "").strip()
    password = data.get("password", "")
    role = data.get("role", "caregiver")
    name = sanitize_short(data.get("name", ""))
    if not username:
        return jsonify({"error": "Username is required"}), 400
    if not validate_username(username):
        return jsonify({"error": "Username must be 2-50 alphanumeric characters or underscores"}), 400
    if len(password) < MIN_PASSWORD:
        return jsonify({"error": f"Password must be at least {MIN_PASSWORD} characters"}), 400
    if len(password) > MAX_PASSWORD:
        return jsonify({"error": f"Password must be at most {MAX_PASSWORD} characters"}), 400
    if not validate_role(role):
        return jsonify({"error": "Role must be: admin, caregiver, or family"}), 400
    pw = _hash_password(password)
    ok = db.add_user(username=username, password_hash=pw, role=role, name=name)
    if ok:
        return jsonify({"status": "ok"}), 201
    return jsonify({"error": "Username already exists"}), 409

@app.route("/api/users/<int:uid>", methods=["DELETE"])
@login_required
def remove_user(uid):
    db.delete_user(uid)
    return jsonify({"status": "ok"})

@app.route("/api/change-password", methods=["POST"])
@login_required
def change_password():
    data, err = require_json()
    if err:
        return err
    user = session.get("user", {})
    username = user.get("username", "")
    old_pw = data.get("old_password", "")
    new_pw = data.get("new_password", "")
    if not old_pw or not new_pw:
        return jsonify({"error": "Both old and new passwords are required"}), 400
    if len(new_pw) < MIN_PASSWORD:
        return jsonify({"error": f"New password must be at least {MIN_PASSWORD} characters"}), 400
    if len(new_pw) > MAX_PASSWORD:
        return jsonify({"error": f"New password must be at most {MAX_PASSWORD} characters"}), 400
    db_user = db.get_user(username)
    if not db_user or not _check_password(old_pw, db_user["password_hash"]):
        return jsonify({"error": "Current password is incorrect"}), 401
    db.update_user_password(username, _hash_password(new_pw))
    return jsonify({"status": "ok"})

# ── Patient Trends API ─────────────────────────────────────────────

@app.route("/api/trends/mood", methods=["GET"])
def mood_trends():
    """Get mood data grouped by day for charting."""
    conn = db._get_conn()
    rows = conn.execute("""
        SELECT date(time) as day, mood, COUNT(*) as cnt
        FROM mood_history
        GROUP BY day, mood
        ORDER BY day
    """).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/trends/activity", methods=["GET"])
def activity_trends():
    """Get activity counts by day."""
    conn = db._get_conn()
    rows = conn.execute("""
        SELECT date(time) as day, action, COUNT(*) as cnt
        FROM activity_log
        GROUP BY day, action
        ORDER BY day
    """).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/trends/medications", methods=["GET"])
def med_trends():
    """Get medication adherence by day."""
    conn = db._get_conn()
    rows = conn.execute("""
        SELECT date(time) as day, status, COUNT(*) as cnt
        FROM med_log
        GROUP BY day, status
        ORDER BY day
    """).fetchall()
    return jsonify([dict(r) for r in rows])

# ── Export API ──────────────────────────────────────────────────────

@app.route("/api/export/csv", methods=["GET"])
def export_csv():
    import csv
    import io
    activities = db.get_activity_log(limit=1000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Time", "Action", "Details"])
    for a in activities:
        writer.writerow([a["time"], a["action"], a["details"]])
    resp = Response(output.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = "attachment; filename=reachy_activity_log.csv"
    return resp

@app.route("/api/export/alerts-csv", methods=["GET"])
def export_alerts_csv():
    import csv
    import io
    alerts = db.get_alerts(limit=1000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Time", "Type", "Message", "Details", "User Said", "Acknowledged"])
    for a in alerts:
        writer.writerow([a["time"], a["type"], a["message"], a["details"], a["user_said"], a["acknowledged"]])
    resp = Response(output.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = "attachment; filename=reachy_alerts.csv"
    return resp

@app.route("/api/export/report-text", methods=["GET"])
def export_report():
    reports = db.get_daily_reports(limit=1)
    if not reports:
        return Response("No reports available.", mimetype="text/plain")
    resp = Response(reports[0]["report"], mimetype="text/plain")
    resp.headers["Content-Disposition"] = f"attachment; filename=report_{reports[0]['date']}.txt"
    return resp

# ── SSE ─────────────────────────────────────────────────────────────

@app.route("/api/i18n", methods=["GET"])
def get_translations():
    from i18n import get_all_translations, available_languages
    lang = request.args.get("lang", "en")
    return jsonify({"translations": get_all_translations(lang), "languages": available_languages()})

@app.route("/api/i18n/set", methods=["POST"])
def set_lang():
    from i18n import set_language
    data, err = require_json()
    if err:
        return err
    lang = sanitize_short(data.get("lang", "en"))
    set_language(lang)
    return jsonify({"status": "ok"})

@app.route("/stream")
def stream():
    return Response(sse_stream(), mimetype="text/event-stream")

# ── Camera stream proxy ─────────────────────────────────────────────

@app.route("/api/camera/stream")
def camera_stream_proxy():
    """Proxy the MJPEG camera stream from the robot so the dashboard can embed it."""
    camera_url = os.environ.get("CAMERA_STREAM_URL", "http://localhost:5556/stream")
    try:
        import urllib.request
        req = urllib.request.Request(camera_url)
        resp = urllib.request.urlopen(req, timeout=5)
        def generate():
            try:
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    yield chunk
            except Exception:
                pass
        return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")
    except Exception:
        # Return a 1x1 transparent pixel if camera unavailable
        return Response(status=503)

@app.route("/teleop")
@login_required
def teleop_page():
    return render_template("teleop.html", active_page="teleop")


@app.route("/mirror")
@login_required
def mirror_page():
    return render_template("mirror.html", active_page="mirror")


# ── Robot Teleoperation Proxy ────────────────────────────────────────

def _robot_proxy(path, method="POST", json_data=None):
    """Forward a request to the robot's webapp API."""
    robot_url = os.environ.get("ROBOT_API_URL", "http://localhost:5557")
    import urllib.request
    url = f"{robot_url}{path}"
    try:
        if method == "GET":
            req = urllib.request.Request(url)
        else:
            body = json.dumps(json_data or {}).encode()
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=5)
        return jsonify(json.loads(resp.read())), resp.status
    except Exception as e:
        return jsonify({"error": f"Robot unreachable: {e}"}), 503


@app.route("/api/robot/health", methods=["GET"])
@login_required
def robot_health():
    return _robot_proxy("/api/health", method="GET")


@app.route("/api/robot/state", methods=["GET"])
@login_required
def robot_state():
    return _robot_proxy("/api/state", method="GET")


@app.route("/api/robot/pose", methods=["POST"])
@login_required
def robot_pose():
    data, err = require_json()
    if err:
        return err
    return _robot_proxy("/api/pose", json_data=data)


@app.route("/api/robot/expression", methods=["POST"])
@login_required
def robot_expression():
    data, err = require_json()
    if err:
        return err
    return _robot_proxy("/api/expression", json_data=data)


@app.route("/api/robot/action", methods=["POST"])
@login_required
def robot_action():
    data, err = require_json()
    if err:
        return err
    return _robot_proxy("/api/action", json_data=data)


@app.route("/api/robot/reset", methods=["POST"])
@login_required
def robot_reset():
    return _robot_proxy("/api/reset")


@app.route("/api/camera/snapshot")
def camera_snapshot():
    """Get a single frame from the robot camera."""
    camera_url = os.environ.get("CAMERA_STREAM_URL", "http://localhost:5556/snapshot")
    try:
        import urllib.request
        resp = urllib.request.urlopen(camera_url, timeout=3)
        data = resp.read()
        return Response(data, mimetype="image/jpeg")
    except Exception:
        return Response(status=503)


# ══════════════════════════════════════════════════════════════════════
# Bot Data API — reads from Reachy's bot_* tables (same Supabase DB)
# ══════════════════════════════════════════════════════════════════════

@app.route("/api/bot/conversations", methods=["GET"])
@login_required
def bot_conversations():
    """Get conversation log from the robot (bot_conversation_log)."""
    limit = request.args.get("limit", 500, type=int)
    patient_id = request.args.get("patient_id", "default")
    try:
        rows = db.get_bot_conversations(patient_id=patient_id, limit=limit)
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bot/moods", methods=["GET"])
@login_required
def bot_moods():
    """Get mood journal from the robot (bot_mood_journal)."""
    limit = request.args.get("limit", 50, type=int)
    patient_id = request.args.get("patient_id", "default")
    try:
        rows = db.get_bot_moods(patient_id=patient_id, limit=limit)
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bot/sessions", methods=["GET"])
@login_required
def bot_sessions():
    """Get session summaries from the robot (bot_session_summaries)."""
    limit = request.args.get("limit", 20, type=int)
    patient_id = request.args.get("patient_id", "default")
    try:
        rows = db.get_bot_session_summaries(patient_id=patient_id, limit=limit)
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bot/facts", methods=["GET"])
@login_required
def bot_facts():
    """Get patient facts learned by the robot (bot_patient_facts)."""
    patient_id = request.args.get("patient_id", "default")
    try:
        rows = db.get_bot_facts(patient_id=patient_id)
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bot/alerts", methods=["GET"])
@login_required
def bot_alerts():
    """Get alerts generated by the robot (bot_caregiver_alerts)."""
    limit = request.args.get("limit", 50, type=int)
    patient_id = request.args.get("patient_id", "default")
    try:
        rows = db.get_bot_alerts(patient_id=patient_id, limit=limit)
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bot/profile", methods=["GET"])
@login_required
def bot_profile():
    """Get patient profile from the robot (bot_patient_profile)."""
    patient_id = request.args.get("patient_id", "default")
    try:
        row = db.get_bot_profile(patient_id=patient_id)
        return jsonify(row or {})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bot/weekly-reports", methods=["GET"])
@login_required
def bot_weekly_reports():
    """Get weekly reports from the robot (bot_weekly_reports)."""
    limit = request.args.get("limit", 4, type=int)
    patient_id = request.args.get("patient_id", "default")
    try:
        rows = db.get_bot_weekly_reports(patient_id=patient_id, limit=limit)
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bot/cognitive", methods=["GET"])
@login_required
def bot_cognitive():
    """Get cognitive game scores from the robot (bot_cognitive_scores)."""
    limit = request.args.get("limit", 20, type=int)
    patient_id = request.args.get("patient_id", "default")
    try:
        rows = db.get_bot_cognitive_scores(patient_id=patient_id, limit=limit)
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bot/exercises", methods=["GET"])
@login_required
def bot_exercises():
    """Get exercise log from the robot (bot_exercise_log)."""
    limit = request.args.get("limit", 20, type=int)
    patient_id = request.args.get("patient_id", "default")
    try:
        rows = db.get_bot_exercises(patient_id=patient_id, limit=limit)
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bot/sleep", methods=["GET"])
@login_required
def bot_sleep():
    """Get sleep log from the robot (bot_sleep_log)."""
    limit = request.args.get("limit", 14, type=int)
    patient_id = request.args.get("patient_id", "default")
    try:
        rows = db.get_bot_sleep_log(patient_id=patient_id, limit=limit)
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bot/reminders", methods=["GET"])
@login_required
def bot_reminders():
    """Get reminders from the robot (bot_reminders)."""
    patient_id = request.args.get("patient_id", "default")
    try:
        rows = db.get_bot_reminders(patient_id=patient_id)
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bot/streak", methods=["GET"])
@login_required
def bot_streak():
    """Get conversation streak from the robot (bot_streaks)."""
    patient_id = request.args.get("patient_id", "default")
    try:
        streak = db.get_bot_streaks(patient_id=patient_id)
        return jsonify({"streak": streak})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bot/summary", methods=["GET"])
@login_required
def bot_summary():
    """All-in-one endpoint: profile, recent moods, streak, latest session, facts count."""
    patient_id = request.args.get("patient_id", "default")
    try:
        profile = db.get_bot_profile(patient_id=patient_id) or {}
        moods = db.get_bot_moods(patient_id=patient_id, limit=10)
        streak = db.get_bot_streaks(patient_id=patient_id)
        sessions = db.get_bot_session_summaries(patient_id=patient_id, limit=1)
        facts = db.get_bot_facts(patient_id=patient_id)
        return jsonify({
            "profile": profile,
            "recent_moods": moods,
            "streak": streak,
            "latest_session": sessions[0] if sessions else None,
            "facts_count": len(facts),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════
# Doctor Report Generator
# ══════════════════════════════════════════════════════════════════════

@app.route("/api/doctor-report", methods=["GET"])
@login_required
def doctor_report():
    """Generate a structured clinical report from all available data."""
    patient_id = request.args.get("patient_id", "default")
    days = request.args.get("days", 7, type=int)

    report = {"generated": datetime.now().strftime("%Y-%m-%d %H:%M"), "period_days": days}

    try:
        # Patient profile
        report["profile"] = db.get_bot_profile(patient_id=patient_id) or {}
    except Exception:
        report["profile"] = {}

    try:
        # Session summaries
        sessions = db.get_bot_session_summaries(patient_id=patient_id, limit=days)
        report["sessions"] = sessions
        if sessions:
            total_interactions = sum(s.get("interactions", 0) for s in sessions)
            total_duration = sum(s.get("duration_minutes", 0) for s in sessions)
            report["session_stats"] = {
                "total_sessions": len(sessions),
                "total_interactions": total_interactions,
                "total_duration_minutes": round(total_duration, 1),
                "avg_duration_minutes": round(total_duration / len(sessions), 1) if sessions else 0,
            }
    except Exception:
        report["sessions"] = []
        report["session_stats"] = {}

    try:
        # Mood analysis
        moods = db.get_bot_moods(patient_id=patient_id, limit=200)
        report["moods_raw"] = moods
        if moods:
            mood_counts = {}
            for m in moods:
                mood = m.get("mood", "neutral")
                mood_counts[mood] = mood_counts.get(mood, 0) + 1
            total = sum(mood_counts.values()) or 1
            report["mood_distribution"] = {k: {"count": v, "pct": round(v / total * 100, 1)} for k, v in sorted(mood_counts.items(), key=lambda x: x[1], reverse=True)}
        else:
            report["mood_distribution"] = {}
    except Exception:
        report["moods_raw"] = []
        report["mood_distribution"] = {}

    try:
        # Alerts
        alerts = db.get_bot_alerts(patient_id=patient_id, limit=100)
        report["alerts"] = alerts
        if alerts:
            alert_counts = {}
            for a in alerts:
                t = a.get("alert_type") or a.get("type", "OTHER")
                alert_counts[t] = alert_counts.get(t, 0) + 1
            report["alert_summary"] = alert_counts
        else:
            report["alert_summary"] = {}
    except Exception:
        report["alerts"] = []
        report["alert_summary"] = {}

    try:
        # Cognitive scores
        cog = db.get_bot_cognitive_scores(patient_id=patient_id, limit=days * 3)
        report["cognitive"] = cog
        if cog:
            scores = [c.get("score", 0) for c in cog if c.get("score") is not None]
            report["cognitive_stats"] = {
                "sessions": len(cog),
                "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
                "latest_score": scores[0] if scores else 0,
            }
        else:
            report["cognitive_stats"] = {}
    except Exception:
        report["cognitive"] = []
        report["cognitive_stats"] = {}

    try:
        # Vitals
        vitals = db.get_vitals_history(patient_id=0, limit=days * 4)
        report["vitals"] = vitals
    except Exception:
        report["vitals"] = []

    try:
        # Medications
        meds = db.get_medications()
        med_log = db.get_med_log(limit=days * 10)
        report["medications"] = meds
        if med_log:
            taken = sum(1 for m in med_log if m.get("status") == "taken")
            total = len(med_log) or 1
            report["med_adherence"] = {"taken": taken, "total": total, "pct": round(taken / total * 100, 1)}
        else:
            report["med_adherence"] = {}
    except Exception:
        report["medications"] = []
        report["med_adherence"] = {}

    try:
        # Facts / knowledge
        facts = db.get_bot_facts(patient_id=patient_id)
        report["facts_count"] = len(facts)
    except Exception:
        report["facts_count"] = 0

    try:
        # Streak
        report["streak"] = db.get_bot_streaks(patient_id=patient_id)
    except Exception:
        report["streak"] = 0

    try:
        # Weekly reports (AI-generated summaries)
        weekly = db.get_bot_weekly_reports(patient_id=patient_id, limit=2)
        report["weekly_reports"] = weekly
    except Exception:
        report["weekly_reports"] = []

    return jsonify(report)


if __name__ == "__main__":
    print("\n=== Caregiver Dashboard ===")
    print("Open http://localhost:5555 in your browser")
    print("Default login: admin / admin\n")
    app.run(host="0.0.0.0", port=5555, debug=True, threaded=True)
