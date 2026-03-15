"""Tests for the caregiver dashboard Flask API."""

import pytest
import sys
import os
import json

# Add dashboard to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "caregiver-dashboard"))


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Create a test Flask app with a temp database."""
    monkeypatch.setenv("REACHY_DB", str(tmp_path / "test.db"))
    # Re-import to pick up new DB path
    import importlib
    import db as dashboard_db
    importlib.reload(dashboard_db)
    dashboard_db.init_db()

    import app as dashboard_app
    importlib.reload(dashboard_app)
    dashboard_app.app.config["TESTING"] = True
    dashboard_app.app.config["SECRET_KEY"] = "test-secret"
    return dashboard_app.app


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
