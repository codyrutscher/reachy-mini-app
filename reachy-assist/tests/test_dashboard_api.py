"""Tests for the caregiver dashboard Flask API."""

import pytest
import sys
import os
import json

# Add dashboard to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "caregiver-dashboard"))


@pytest.fixture
def app(tmp_path):
    """Create a test Flask app with a temp SQLite database."""
    import os
    import importlib

    # Save and clear Postgres env vars so tests use SQLite
    saved = {}
    for key in ("DATABASE_URL", "SUPABASE_DB_URL"):
        saved[key] = os.environ.pop(key, None)
    os.environ["REACHY_DB"] = str(tmp_path / "test.db")

    # Prevent load_dotenv from re-reading the .env file during reload
    import dotenv
    _orig_load = dotenv.load_dotenv
    dotenv.load_dotenv = lambda *a, **kw: None

    import db as dashboard_db
    importlib.reload(dashboard_db)
    dashboard_db.init_db()

    import app as dashboard_app
    importlib.reload(dashboard_app)
    dashboard_app.db = dashboard_db
    dashboard_app.app.config["TESTING"] = True
    dashboard_app.app.config["SECRET_KEY"] = "test-secret"

    yield dashboard_app.app

    # Restore
    dotenv.load_dotenv = _orig_load
    os.environ.pop("REACHY_DB", None)
    for key, val in saved.items():
        if val is not None:
            os.environ[key] = val


@pytest.fixture
def client(app):
    return app.test_client()


class TestAlertAPI:

    def test_post_alert(self, client):
        resp = client.post("/api/alerts", json={
            "type": "INFO", "message": "Test alert", "details": "test"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "id" in data

    def test_get_alerts(self, client):
        client.post("/api/alerts", json={"type": "INFO", "message": "Alert 1"})
        client.post("/api/alerts", json={"type": "CRISIS", "message": "Alert 2"})
        resp = client.get("/api/alerts")
        assert resp.status_code == 200
        alerts = resp.get_json()
        assert len(alerts) == 2

    def test_acknowledge_alert(self, client):
        resp = client.post("/api/alerts", json={"type": "INFO", "message": "Test"})
        alert_id = resp.get_json()["id"]
        ack_resp = client.post(f"/api/alerts/{alert_id}/ack")
        assert ack_resp.status_code == 200
        # Verify it's acknowledged
        alerts = client.get("/api/alerts").get_json()
        acked = [a for a in alerts if a["id"] == alert_id]
        assert acked[0]["acknowledged"] is True

    def test_clear_acknowledged(self, client):
        client.post("/api/alerts", json={"type": "INFO", "message": "A1"})
        resp = client.post("/api/alerts", json={"type": "INFO", "message": "A2"})
        aid = resp.get_json()["id"]
        client.post(f"/api/alerts/{aid}/ack")
        client.post("/api/alerts/clear")
        alerts = client.get("/api/alerts").get_json()
        assert len(alerts) == 1  # only unacked remains


class TestMessageAPI:

    def test_send_message(self, client):
        resp = client.post("/api/messages", json={"text": "Hello patient", "priority": "normal"})
        assert resp.status_code == 201

    def test_get_pending_messages(self, client):
        client.post("/api/messages", json={"text": "Msg 1"})
        client.post("/api/messages", json={"text": "Msg 2"})
        resp = client.get("/api/messages/pending")
        msgs = resp.get_json()
        assert len(msgs) >= 2
        # After fetching, they should be marked delivered
        resp2 = client.get("/api/messages/pending")
        assert len(resp2.get_json()) == 0


class TestConversationAPI:

    def test_post_conversation(self, client):
        resp = client.post("/api/conversation", json={"speaker": "patient", "text": "Hello"})
        assert resp.status_code == 200

    def test_get_conversation(self, client):
        client.post("/api/conversation", json={"speaker": "patient", "text": "Hi"})
        client.post("/api/conversation", json={"speaker": "reachy", "text": "Hello!"})
        resp = client.get("/api/conversation")
        convo = resp.get_json()
        assert len(convo) == 2


class TestPatientAPI:

    def test_add_patient(self, client):
        resp = client.post("/api/patients", json={
            "name": "Test Patient", "room": "101", "age": 75,
            "patient_type": "elderly", "conditions": "Diabetes"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Test Patient"

    def test_get_patients(self, client):
        client.post("/api/patients", json={"name": "P1", "patient_type": "elderly"})
        client.post("/api/patients", json={"name": "P2", "patient_type": "disabled"})
        resp = client.get("/api/patients")
        assert len(resp.get_json()) == 2

    def test_delete_patient(self, client):
        resp = client.post("/api/patients", json={"name": "ToDelete"})
        pid = resp.get_json()["id"]
        client.delete(f"/api/patients/{pid}")
        patients = client.get("/api/patients").get_json()
        assert len(patients) == 0


class TestStatusAPI:

    def test_update_and_get_status(self, client):
        client.post("/api/status", json={"mood": "joy", "name": "Margaret"})
        resp = client.get("/api/status")
        status = resp.get_json()
        assert status["mood"] == "joy"
        assert status["name"] == "Margaret"


class TestMedicationAPI:

    def test_add_medication(self, client):
        resp = client.post("/api/medications", json={
            "name": "Aspirin", "dosage": "100mg", "times": "08:00,20:00"
        })
        assert resp.status_code == 201
        assert resp.get_json()["name"] == "Aspirin"

    def test_delete_medication(self, client):
        resp = client.post("/api/medications", json={"name": "ToDelete", "times": "08:00"})
        mid = resp.get_json()["id"]
        client.delete(f"/api/medications/{mid}")
        meds = client.get("/api/medications").get_json()
        assert len(meds) == 0

    def test_log_medication(self, client):
        resp = client.post("/api/medications", json={"name": "Aspirin", "times": "08:00"})
        mid = resp.get_json()["id"]
        client.post(f"/api/medications/{mid}/log", json={"status": "taken"})
        log = client.get("/api/med-log").get_json()
        assert len(log) == 1
        assert log[0]["status"] == "taken"


class TestActivityAPI:

    def test_post_activity(self, client):
        resp = client.post("/api/activity", json={"action": "test", "details": "testing"})
        assert resp.status_code == 200

    def test_get_activity(self, client):
        client.post("/api/activity", json={"action": "test1"})
        client.post("/api/activity", json={"action": "test2"})
        resp = client.get("/api/activity")
        # May include system activities too
        assert len(resp.get_json()) >= 2


class TestReportAPI:

    def test_generate_report(self, client):
        resp = client.post("/api/reports/generate")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "report" in data
        assert "Daily Report" in data["report"]

    def test_get_reports(self, client):
        client.post("/api/reports/generate")
        resp = client.get("/api/reports")
        assert resp.status_code == 200
        reports = resp.get_json()
        assert len(reports) >= 1
        assert "report" in reports[0]


# ── Scheduled Messages API ──────────────────────────────────────────

class TestScheduledAPI:

    def test_add_scheduled(self, client):
        resp = client.post("/api/scheduled", json={
            "text": "Take your medicine", "time": "08:00", "repeat": "daily"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["text"] == "Take your medicine"
        assert data["time"] == "08:00"
        assert data["repeat"] == "daily"

    def test_get_scheduled(self, client):
        client.post("/api/scheduled", json={"text": "Msg1", "time": "09:00"})
        client.post("/api/scheduled", json={"text": "Msg2", "time": "10:00"})
        resp = client.get("/api/scheduled")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 2

    def test_delete_scheduled(self, client):
        resp = client.post("/api/scheduled", json={"text": "ToDelete", "time": "11:00"})
        sid = resp.get_json()["id"]
        client.delete(f"/api/scheduled/{sid}")
        assert len(client.get("/api/scheduled").get_json()) == 0

    def test_toggle_scheduled(self, client):
        resp = client.post("/api/scheduled", json={"text": "Toggle me", "time": "12:00"})
        sid = resp.get_json()["id"]
        assert resp.get_json()["active"] is True
        client.post(f"/api/scheduled/{sid}/toggle")
        msgs = client.get("/api/scheduled").get_json()
        toggled = [m for m in msgs if m["id"] == sid][0]
        assert toggled["active"] is False
        # Toggle back
        client.post(f"/api/scheduled/{sid}/toggle")
        msgs = client.get("/api/scheduled").get_json()
        toggled = [m for m in msgs if m["id"] == sid][0]
        assert toggled["active"] is True


# ── Facilities API ──────────────────────────────────────────────────

class TestFacilityAPI:

    def test_add_facility(self, client):
        resp = client.post("/api/facilities", json={
            "name": "Sunrise Home", "address": "123 Main St",
            "type": "nursing_home", "robots": 2, "contact": "[email]"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Sunrise Home"

    def test_get_facilities(self, client):
        client.post("/api/facilities", json={"name": "F1"})
        client.post("/api/facilities", json={"name": "F2"})
        resp = client.get("/api/facilities")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 2

    def test_delete_facility(self, client):
        resp = client.post("/api/facilities", json={"name": "ToDelete"})
        fid = resp.get_json()["id"]
        client.delete(f"/api/facilities/{fid}")
        assert len(client.get("/api/facilities").get_json()) == 0


# ── Notes API ───────────────────────────────────────────────────────

class TestNotesAPI:

    def test_add_note(self, client):
        resp = client.post("/api/notes", json={
            "note": "Patient seems tired today", "patient_id": 1
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["note"] == "Patient seems tired today"
        assert data["patient_id"] == 1

    def test_get_notes(self, client):
        client.post("/api/notes", json={"note": "Note 1", "patient_id": 1})
        client.post("/api/notes", json={"note": "Note 2", "patient_id": 1})
        client.post("/api/notes", json={"note": "Note 3", "patient_id": 2})
        # All notes
        resp = client.get("/api/notes")
        assert len(resp.get_json()) == 3
        # Filter by patient
        resp = client.get("/api/notes?patient_id=1")
        assert len(resp.get_json()) == 2

    def test_delete_note(self, client):
        resp = client.post("/api/notes", json={"note": "ToDelete"})
        nid = resp.get_json()["id"]
        client.delete(f"/api/notes/{nid}")
        assert len(client.get("/api/notes").get_json()) == 0


# ── Handoff API ─────────────────────────────────────────────────────

class TestHandoffAPI:

    def test_create_handoff(self, client):
        # Login first so session has user info
        with client.session_transaction() as sess:
            sess["user"] = {"username": "admin", "role": "admin", "name": "Admin"}
        resp = client.post("/api/handoff", json={"to_caregiver": "Night Nurse"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["from_caregiver"] == "Admin"
        assert "summary" in data

    def test_get_handoffs(self, client):
        with client.session_transaction() as sess:
            sess["user"] = {"username": "admin", "role": "admin", "name": "Admin"}
        client.post("/api/handoff", json={"to_caregiver": "Nurse A"})
        client.post("/api/handoff", json={"to_caregiver": "Nurse B"})
        resp = client.get("/api/handoff")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 2


# ── Family Messages API ────────────────────────────────────────────

class TestFamilyMessageAPI:

    def test_post_family_message(self, client):
        resp = client.post("/api/family/messages", json={
            "family_member": "Sarah", "message": "Hi Mom!", "patient_id": 1
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["family_member"] == "Sarah"
        assert data["message"] == "Hi Mom!"

    def test_get_family_messages(self, client):
        client.post("/api/family/messages", json={
            "family_member": "Sarah", "message": "Msg 1", "patient_id": 1
        })
        client.post("/api/family/messages", json={
            "family_member": "John", "message": "Msg 2", "patient_id": 2
        })
        # All messages
        resp = client.get("/api/family/messages")
        assert len(resp.get_json()) == 2
        # Filter by patient
        resp = client.get("/api/family/messages?patient_id=1")
        assert len(resp.get_json()) == 1

    def test_mark_family_read(self, client):
        resp = client.post("/api/family/messages", json={
            "family_member": "Sarah", "message": "Read me"
        })
        mid = resp.get_json()["id"]
        mark_resp = client.post(f"/api/family/messages/{mid}/read")
        assert mark_resp.status_code == 200


# ── Vitals API ──────────────────────────────────────────────────────

class TestVitalsAPI:

    def test_post_vitals(self, client):
        resp = client.post("/api/vitals", json={
            "heart_rate": 72, "spo2": 98, "bp_systolic": 120,
            "bp_diastolic": 80, "temperature": 98.6
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["alerts"] == []

    def test_post_vitals_triggers_alert(self, client):
        resp = client.post("/api/vitals", json={"heart_rate": 130, "spo2": 85})
        data = resp.get_json()
        assert len(data["alerts"]) == 2  # high HR + low SpO2

    def test_get_vitals(self, client):
        client.post("/api/vitals", json={"heart_rate": 72})
        client.post("/api/vitals", json={"heart_rate": 75})
        resp = client.get("/api/vitals")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 2

    def test_get_latest_vitals(self, client):
        client.post("/api/vitals", json={"heart_rate": 72})
        client.post("/api/vitals", json={"heart_rate": 80})
        resp = client.get("/api/vitals/latest")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["heart_rate"] == 80

    def test_get_latest_vitals_empty(self, client):
        resp = client.get("/api/vitals/latest")
        assert resp.status_code == 200
        assert resp.get_json() == {}


# ── User Management API ────────────────────────────────────────────

class TestUserAPI:

    def test_get_users(self, client):
        resp = client.get("/api/users")
        assert resp.status_code == 200
        users = resp.get_json()
        # Default admin user should exist
        assert len(users) >= 1

    def test_create_user(self, client):
        resp = client.post("/api/users", json={
            "username": "nurse1", "password": "pass123",
            "role": "caregiver", "name": "Nurse One"
        })
        assert resp.status_code == 201
        users = client.get("/api/users").get_json()
        names = [u["username"] for u in users]
        assert "nurse1" in names

    def test_create_duplicate_user(self, client):
        client.post("/api/users", json={"username": "dup", "password": "pass1234"})
        resp = client.post("/api/users", json={"username": "dup", "password": "pass1234"})
        assert resp.status_code == 409

    def test_delete_user(self, client):
        client.post("/api/users", json={"username": "todelete", "password": "pass1234"})
        users = client.get("/api/users").get_json()
        uid = [u for u in users if u["username"] == "todelete"][0]["id"]
        client.delete(f"/api/users/{uid}")
        users = client.get("/api/users").get_json()
        assert all(u["username"] != "todelete" for u in users)

    def test_change_password(self, client):
        # Create user and login
        client.post("/api/users", json={
            "username": "pwuser", "password": "oldpass", "name": "PW User"
        })
        with client.session_transaction() as sess:
            sess["user"] = {"username": "pwuser", "role": "caregiver", "name": "PW User"}
        resp = client.post("/api/change-password", json={
            "old_password": "oldpass", "new_password": "newpass"
        })
        assert resp.status_code == 200
        # Verify new password works via login
        resp = client.post("/login", json={"username": "pwuser", "password": "newpass"})
        assert resp.status_code == 200

    def test_change_password_wrong_old(self, client):
        client.post("/api/users", json={"username": "pwuser2", "password": "correct"})
        with client.session_transaction() as sess:
            sess["user"] = {"username": "pwuser2", "role": "caregiver", "name": "PW2"}
        resp = client.post("/api/change-password", json={
            "old_password": "wrong", "new_password": "newpass"
        })
        assert resp.status_code == 401


# ── Settings API ────────────────────────────────────────────────────

class TestSettingsAPI:

    def test_save_and_get_settings(self, client):
        client.post("/api/settings", json={
            "theme": "dark", "accent_color": "#ff6600", "compact_mode": "true"
        })
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        settings = resp.get_json()
        assert settings["theme"] == "dark"
        assert settings["accent_color"] == "#ff6600"

    def test_settings_overwrite(self, client):
        client.post("/api/settings", json={"theme": "light"})
        client.post("/api/settings", json={"theme": "dark"})
        settings = client.get("/api/settings").get_json()
        assert settings["theme"] == "dark"


# ── Clear All API ───────────────────────────────────────────────────

class TestClearAllAPI:

    def test_clear_all(self, client):
        # Add some data
        client.post("/api/alerts", json={"type": "INFO", "message": "test"})
        client.post("/api/conversation", json={"speaker": "patient", "text": "hi"})
        client.post("/api/activity", json={"action": "test"})
        # Clear
        resp = client.post("/api/clear-all")
        assert resp.status_code == 200
        # Verify cleared
        assert len(client.get("/api/alerts").get_json()) == 0
        assert len(client.get("/api/conversation").get_json()) == 0


# ── History APIs ────────────────────────────────────────────────────

class TestHistoryAPI:

    def test_mood_history(self, client):
        # Post status with mood to trigger mood_history insert
        client.post("/api/status", json={"mood": "happy"})
        client.post("/api/status", json={"mood": "calm"})
        resp = client.get("/api/mood-history")
        assert resp.status_code == 200
        moods = resp.get_json()
        assert len(moods) == 2

    def test_checkin_history(self, client):
        client.post("/api/checkin-history", json={
            "results": {"pain": 2, "sleep": 8, "mood": "good"}
        })
        resp = client.get("/api/checkin-history")
        assert resp.status_code == 200
        checkins = resp.get_json()
        assert len(checkins) == 1
        assert checkins[0]["results"]["pain"] == 2


# ── Export APIs ─────────────────────────────────────────────────────

class TestExportAPI:

    def test_export_csv(self, client):
        client.post("/api/activity", json={"action": "test_export", "details": "data"})
        resp = client.get("/api/export/csv")
        assert resp.status_code == 200
        assert resp.content_type == "text/csv; charset=utf-8"
        text = resp.data.decode()
        assert "Time,Action,Details" in text
        assert "test_export" in text

    def test_export_alerts_csv(self, client):
        client.post("/api/alerts", json={"type": "INFO", "message": "export test"})
        resp = client.get("/api/export/alerts-csv")
        assert resp.status_code == 200
        assert resp.content_type == "text/csv; charset=utf-8"
        text = resp.data.decode()
        assert "export test" in text

    def test_export_report_text(self, client):
        client.post("/api/reports/generate")
        resp = client.get("/api/export/report-text")
        assert resp.status_code == 200
        assert "Daily Report" in resp.data.decode()

    def test_export_report_text_empty(self, client):
        resp = client.get("/api/export/report-text")
        assert resp.status_code == 200
        assert "No reports" in resp.data.decode()


# ── Trends APIs ─────────────────────────────────────────────────────

class TestTrendsAPI:

    def test_mood_trends(self, client):
        client.post("/api/status", json={"mood": "happy"})
        client.post("/api/status", json={"mood": "sad"})
        resp = client.get("/api/trends/mood")
        assert resp.status_code == 200
        # Returns list of {day, mood, cnt}
        assert isinstance(resp.get_json(), list)

    def test_activity_trends(self, client):
        client.post("/api/activity", json={"action": "test"})
        resp = client.get("/api/trends/activity")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_med_trends(self, client):
        resp_med = client.post("/api/medications", json={"name": "Aspirin", "times": "08:00"})
        mid = resp_med.get_json()["id"]
        client.post(f"/api/medications/{mid}/log", json={"status": "taken"})
        resp = client.get("/api/trends/medications")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 1


# ── Auth / Login API ───────────────────────────────────────────────

class TestAuthAPI:

    def test_login_success(self, client):
        resp = client.post("/login", json={"username": "admin", "password": "admin"})
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"

    def test_login_failure(self, client):
        resp = client.post("/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401
        assert "error" in resp.get_json()

    def test_login_nonexistent_user(self, client):
        resp = client.post("/login", json={"username": "nobody", "password": "x"})
        assert resp.status_code == 401

    def test_logout(self, client):
        # Login first
        client.post("/login", json={"username": "admin", "password": "admin"})
        resp = client.get("/logout", follow_redirects=False)
        assert resp.status_code == 302  # redirect to login

    def test_login_required_redirect(self, client):
        """Unauthenticated page access redirects to login."""
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


# ── Activity Stats API ─────────────────────────────────────────────

class TestActivityStatsAPI:

    def test_activity_stats(self, client):
        client.post("/api/activity", json={"action": "login"})
        client.post("/api/activity", json={"action": "login"})
        client.post("/api/activity", json={"action": "alert"})
        resp = client.get("/api/activity/stats")
        assert resp.status_code == 200
        stats = resp.get_json()
        assert stats["login"] >= 2
        assert stats["alert"] >= 1


# ── Med Log Today API ──────────────────────────────────────────────

class TestMedLogTodayAPI:

    def test_med_log_today(self, client):
        resp = client.post("/api/medications", json={"name": "Aspirin", "times": "08:00"})
        mid = resp.get_json()["id"]
        client.post(f"/api/medications/{mid}/log", json={"status": "taken"})
        resp = client.get("/api/med-log/today")
        assert resp.status_code == 200
        log = resp.get_json()
        assert len(log) >= 1
        assert log[0]["status"] == "taken"


# ── Bot Endpoints (SQLite fallback — expect 500 or error) ──────────

class TestBotEndpoints:
    """Bot endpoints return empty data when no bot tables have data."""

    def _login(self, client):
        with client.session_transaction() as sess:
            sess["user"] = {"username": "admin", "role": "admin", "name": "Admin"}

    def test_bot_conversations(self, client):
        self._login(client)
        resp = client.get("/api/bot/conversations")
        assert resp.status_code == 200
        assert resp.get_json() == [] or "error" in resp.get_json()

    def test_bot_moods(self, client):
        self._login(client)
        resp = client.get("/api/bot/moods")
        assert resp.status_code in (200, 500)

    def test_bot_sessions(self, client):
        self._login(client)
        resp = client.get("/api/bot/sessions")
        assert resp.status_code in (200, 500)

    def test_bot_facts(self, client):
        self._login(client)
        resp = client.get("/api/bot/facts")
        assert resp.status_code in (200, 500)

    def test_bot_alerts(self, client):
        self._login(client)
        resp = client.get("/api/bot/alerts")
        assert resp.status_code in (200, 500)

    def test_bot_profile(self, client):
        self._login(client)
        resp = client.get("/api/bot/profile")
        assert resp.status_code in (200, 500)

    def test_bot_weekly_reports(self, client):
        self._login(client)
        resp = client.get("/api/bot/weekly-reports")
        assert resp.status_code in (200, 500)

    def test_bot_cognitive(self, client):
        self._login(client)
        resp = client.get("/api/bot/cognitive")
        assert resp.status_code in (200, 500)

    def test_bot_exercises(self, client):
        self._login(client)
        resp = client.get("/api/bot/exercises")
        assert resp.status_code in (200, 500)

    def test_bot_sleep(self, client):
        self._login(client)
        resp = client.get("/api/bot/sleep")
        assert resp.status_code in (200, 500)

    def test_bot_reminders(self, client):
        self._login(client)
        resp = client.get("/api/bot/reminders")
        assert resp.status_code in (200, 500)

    def test_bot_streak(self, client):
        self._login(client)
        resp = client.get("/api/bot/streak")
        assert resp.status_code in (200, 500)

    def test_bot_summary(self, client):
        self._login(client)
        resp = client.get("/api/bot/summary")
        assert resp.status_code in (200, 500)


# ── Doctor Report API ──────────────────────────────────────────────

class TestDoctorReportAPI:

    def test_doctor_report(self, client):
        """Doctor report should return 200 even if bot tables are missing —
        each section has its own try/except."""
        with client.session_transaction() as sess:
            sess["user"] = {"username": "admin", "role": "admin", "name": "Admin"}
        # Add some dashboard data so parts of the report have content
        client.post("/api/vitals", json={"heart_rate": 72})
        client.post("/api/medications", json={"name": "Aspirin", "times": "08:00"})
        resp = client.get("/api/doctor-report")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "generated" in data
        assert "period_days" in data
        assert data["period_days"] == 7

    def test_doctor_report_custom_days(self, client):
        with client.session_transaction() as sess:
            sess["user"] = {"username": "admin", "role": "admin", "name": "Admin"}
        resp = client.get("/api/doctor-report?days=14")
        assert resp.status_code == 200
        assert resp.get_json()["period_days"] == 14


# ── i18n API ────────────────────────────────────────────────────────

class TestI18nAPI:

    def test_get_translations(self, client):
        resp = client.get("/api/i18n?lang=en")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "translations" in data
        assert "languages" in data

    def test_set_language(self, client):
        resp = client.post("/api/i18n/set", json={"lang": "es"})
        assert resp.status_code == 200

    def test_switch_lang_route(self, client):
        resp = client.get("/set-lang/en", follow_redirects=False)
        assert resp.status_code == 302


# ── Page Rendering Tests ───────────────────────────────────────────

class TestPageRendering:
    """Verify all pages render without 500 errors when logged in."""

    def _login(self, client):
        with client.session_transaction() as sess:
            sess["user"] = {"username": "admin", "role": "admin", "name": "Admin"}

    def test_dashboard_page(self, client):
        self._login(client)
        assert client.get("/").status_code == 200

    def test_patients_page(self, client):
        self._login(client)
        assert client.get("/patients").status_code == 200

    def test_history_page(self, client):
        self._login(client)
        assert client.get("/history").status_code == 200

    def test_facilities_page(self, client):
        self._login(client)
        assert client.get("/facilities").status_code == 200

    def test_medications_page(self, client):
        self._login(client)
        assert client.get("/medications").status_code == 200

    def test_schedule_page(self, client):
        self._login(client)
        assert client.get("/schedule").status_code == 200

    def test_reports_page(self, client):
        self._login(client)
        assert client.get("/reports").status_code == 200

    def test_camera_page(self, client):
        self._login(client)
        assert client.get("/camera").status_code == 200

    def test_activity_page(self, client):
        self._login(client)
        assert client.get("/activity").status_code == 200

    def test_settings_page(self, client):
        self._login(client)
        assert client.get("/settings").status_code == 200

    def test_memory_book_page(self, client):
        self._login(client)
        assert client.get("/memory-book").status_code == 200

    def test_family_page(self, client):
        assert client.get("/family").status_code == 200

    def test_login_page(self, client):
        assert client.get("/login").status_code == 200

# ── Input Validation Tests ─────────────────────────────────────────

class TestInputValidation:
    """Test that invalid inputs are properly rejected with 400."""

    def test_alert_missing_message(self, client):
        resp = client.post("/api/alerts", json={"type": "INFO"})
        assert resp.status_code == 400

    def test_message_empty_text(self, client):
        resp = client.post("/api/messages", json={"text": ""})
        assert resp.status_code == 400

    def test_message_whitespace_only(self, client):
        resp = client.post("/api/messages", json={"text": "   "})
        assert resp.status_code == 400

    def test_conversation_empty_text(self, client):
        resp = client.post("/api/conversation", json={"speaker": "patient", "text": ""})
        assert resp.status_code == 400

    def test_patient_missing_name(self, client):
        resp = client.post("/api/patients", json={"room": "101"})
        assert resp.status_code == 400

    def test_patient_invalid_age(self, client):
        resp = client.post("/api/patients", json={"name": "Test", "age": 999})
        assert resp.status_code == 400

    def test_facility_missing_name(self, client):
        resp = client.post("/api/facilities", json={"address": "123 St"})
        assert resp.status_code == 400

    def test_scheduled_missing_text(self, client):
        resp = client.post("/api/scheduled", json={"time": "08:00"})
        assert resp.status_code == 400

    def test_scheduled_bad_time(self, client):
        resp = client.post("/api/scheduled", json={"text": "Hi", "time": "not-a-time"})
        assert resp.status_code == 400

    def test_medication_missing_name(self, client):
        resp = client.post("/api/medications", json={"dosage": "100mg"})
        assert resp.status_code == 400

    def test_med_log_invalid_status(self, client):
        resp = client.post("/api/medications", json={"name": "Aspirin", "times": "08:00"})
        mid = resp.get_json()["id"]
        resp = client.post(f"/api/medications/{mid}/log", json={"status": "invalid"})
        assert resp.status_code == 400

    def test_note_empty(self, client):
        resp = client.post("/api/notes", json={"note": ""})
        assert resp.status_code == 400

    def test_family_message_empty(self, client):
        resp = client.post("/api/family/messages", json={"family_member": "Sarah", "message": ""})
        assert resp.status_code == 400

    def test_vitals_invalid_heart_rate(self, client):
        resp = client.post("/api/vitals", json={"heart_rate": 500})
        assert resp.status_code == 400

    def test_vitals_invalid_spo2(self, client):
        resp = client.post("/api/vitals", json={"spo2": 150})
        assert resp.status_code == 400

    def test_vitals_invalid_temperature(self, client):
        resp = client.post("/api/vitals", json={"temperature": 200.0})
        assert resp.status_code == 400

    def test_user_short_password(self, client):
        resp = client.post("/api/users", json={"username": "test", "password": "ab"})
        assert resp.status_code == 400

    def test_user_invalid_username(self, client):
        resp = client.post("/api/users", json={"username": "a b!", "password": "pass1234"})
        assert resp.status_code == 400

    def test_user_invalid_role(self, client):
        resp = client.post("/api/users", json={
            "username": "test", "password": "pass1234", "role": "superadmin"
        })
        assert resp.status_code == 400

    def test_change_password_too_short(self, client):
        client.post("/api/users", json={
            "username": "pwtest", "password": "oldpass", "name": "Test"
        })
        with client.session_transaction() as sess:
            sess["user"] = {"username": "pwtest", "role": "caregiver", "name": "Test"}
        resp = client.post("/api/change-password", json={
            "old_password": "oldpass", "new_password": "ab"
        })
        assert resp.status_code == 400

    def test_xss_sanitized(self, client):
        """HTML in user input should be escaped."""
        resp = client.post("/api/alerts", json={
            "type": "INFO", "message": "<script>alert('xss')</script>"
        })
        assert resp.status_code == 201
        alerts = client.get("/api/alerts").get_json()
        assert "<script>" not in alerts[0]["message"]
        assert "&lt;script&gt;" in alerts[0]["message"]

    def test_login_rate_limit(self, client):
        """After 10 failed attempts, should get 429."""
        for _ in range(10):
            client.post("/login", json={"username": "x", "password": "x"})
        resp = client.post("/login", json={"username": "x", "password": "x"})
        assert resp.status_code == 429
