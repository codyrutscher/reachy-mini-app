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
from flask import Flask, request, jsonify, render_template, Response, session, redirect, url_for
from flask_cors import CORS
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

# Create default admin user if none exist
if not db.get_users():
    pw = _hash_password("admin")
    db.add_user("admin", pw, role="admin", name="Administrator")
    print("[AUTH] Default user created: admin / admin")

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


@app.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html", active_page="login")


@app.route("/login", methods=["POST"])
def login_action():
    data = request.get_json(force=True)
    username = data.get("username", "")
    password = data.get("password", "")
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
    data = request.get_json(force=True)
    alert = db.add_alert(
        alert_type=data.get("type", "INFO"),
        message=data.get("message", ""),
        details=data.get("details", ""),
        user_said=data.get("user_said", ""),
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


# ── Messages API ────────────────────────────────────────────────────

@app.route("/api/messages", methods=["POST"])
def send_message():
    data = request.get_json(force=True)
    msg = db.add_message(text=data.get("text", ""), priority=data.get("priority", "normal"))
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
    return jsonify(db.get_conversation())

@app.route("/api/conversation", methods=["POST"])
def post_conversation():
    data = request.get_json(force=True)
    speaker = data.get("speaker", "patient")
    text = data.get("text", "")
    entry = db.add_conversation(speaker, text)
    if speaker == "patient":
        db.update_status(last_said=text, last_active=datetime.now().strftime("%H:%M:%S"))
        db.add_activity("patient_spoke", text[:80])
    notify_listeners("conversation", entry)
    return jsonify({"status": "ok"})

# ── Status API ──────────────────────────────────────────────────────

@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify(db.get_status())

@app.route("/api/status", methods=["POST"])
def update_status():
    data = request.get_json(force=True)
    db.update_status(**data)
    if "mood" in data:
        db.add_mood(data["mood"])
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
    data = request.get_json(force=True)
    db.add_checkin(data.get("results", {}))
    db.add_activity("checkin", f"Results: {data.get('results', {})}")
    return jsonify({"status": "ok"})

# ── Patients API ────────────────────────────────────────────────────

@app.route("/api/patients", methods=["GET"])
def get_patients():
    return jsonify(db.get_patients())

@app.route("/api/patients", methods=["POST"])
def add_patient():
    data = request.get_json(force=True)
    patient = db.add_patient(
        name=data.get("name", ""), room=data.get("room", ""),
        age=data.get("age"), conditions=data.get("conditions", ""),
        emergency_contact=data.get("emergency_contact", ""),
        patient_type=data.get("patient_type", "elderly"),
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
    data = request.get_json(force=True)
    facility = db.add_facility(
        name=data.get("name", ""), address=data.get("address", ""),
        ftype=data.get("type", "nursing_home"), robots=data.get("robots", 0),
        contact=data.get("contact", ""),
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
    data = request.get_json(force=True)
    msg = db.add_scheduled_message(
        text=data.get("text", ""), time_str=data.get("time", ""),
        repeat=data.get("repeat", "once"),
    )
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
    data = request.get_json(force=True)
    med = db.add_medication(
        name=data.get("name", ""), dosage=data.get("dosage", ""),
        times=data.get("times", ""), notes=data.get("notes", ""),
    )
    db.add_activity("med_added", f"Added: {med['name']} {med['dosage']}")
    return jsonify(med), 201

@app.route("/api/medications/<int:mid>", methods=["DELETE"])
def delete_medication(mid):
    db.delete_medication(mid)
    return jsonify({"status": "ok"})

@app.route("/api/medications/<int:mid>/log", methods=["POST"])
def log_medication(mid):
    data = request.get_json(force=True)
    status = data.get("status", "taken")
    db.log_med_event(mid, status, data.get("scheduled_time", ""))
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
    data = request.get_json(force=True)
    db.add_activity(data.get("action", ""), data.get("details", ""))
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
    data = request.get_json(force=True)
    db.save_settings(**data)
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
    data = request.get_json(force=True)
    user = session.get("user", {})
    note = db.add_note(
        note=data.get("note", ""),
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
    data = request.get_json(force=True)
    handoff = db.create_shift_handoff(
        from_caregiver=user.get("name", user.get("username", "Unknown")),
        to_caregiver=data.get("to_caregiver", ""),
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
    data = request.get_json(force=True)
    msg = db.add_family_message(
        family_member=data.get("family_member", "Family"),
        message=data.get("message", ""),
        patient_id=data.get("patient_id", 0),
        message_type=data.get("type", "text"),
    )
    # Also queue as a robot message so Reachy speaks it
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
    data = request.get_json(force=True)
    db.add_vitals(
        heart_rate=data.get("heart_rate"),
        spo2=data.get("spo2"),
        bp_sys=data.get("bp_systolic"),
        bp_dia=data.get("bp_diastolic"),
        temperature=data.get("temperature"),
        source=data.get("source", "device"),
        patient_id=data.get("patient_id", 0),
    )
    # Check for alerts
    alerts = []
    hr = data.get("heart_rate")
    if hr and (hr < 50 or hr > 120):
        alerts.append(f"Abnormal heart rate: {hr} bpm")
    spo2 = data.get("spo2")
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

# ── User Management API ────────────────────────────────────────────

@app.route("/api/users", methods=["GET"])
@login_required
def get_users():
    return jsonify(db.get_users())

@app.route("/api/users", methods=["POST"])
@login_required
def create_user():
    data = request.get_json(force=True)
    pw = _hash_password(data.get("password", "changeme"))
    ok = db.add_user(
        username=data.get("username", ""),
        password_hash=pw,
        role=data.get("role", "caregiver"),
        name=data.get("name", ""),
    )
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
    data = request.get_json(force=True)
    user = session.get("user", {})
    username = user.get("username", "")
    old_pw = data.get("old_password", "")
    new_pw = data.get("new_password", "")
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
    data = request.get_json(force=True)
    set_language(data.get("lang", "en"))
    return jsonify({"status": "ok"})

@app.route("/stream")
def stream():
    return Response(sse_stream(), mimetype="text/event-stream")


if __name__ == "__main__":
    print("\n=== Caregiver Dashboard ===")
    print("Open http://localhost:5555 in your browser")
    print("Default login: admin / admin\n")
    app.run(host="0.0.0.0", port=5555, debug=False, threaded=True)
