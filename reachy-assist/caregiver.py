"""Caregiver alert system — notifies a caregiver via web dashboard, email,
or log when Reachy detects distress, emergencies, or care requests."""

import json
import os
import smtplib
import threading
from datetime import datetime
from email.mime.text import MIMEText

ALERTS_LOG = os.path.join(os.path.dirname(__file__), "alerts.log")
CAREGIVER_CONFIG = os.path.join(os.path.dirname(__file__), "caregiver.json")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:5555")


class CaregiverAlerts:
    """Sends alerts to caregivers when concerning patterns are detected."""

    def __init__(self):
        self.config = self._load_config()
        self.alert_history = []
        self.dashboard_url = DASHBOARD_URL
        print("[ALERT] Caregiver alert system initialized")
        print(f"[ALERT] Dashboard: {self.dashboard_url}")
        if self.config.get("email"):
            print(f"[ALERT] Email alerts: {self.config['email']}")

    def _load_config(self) -> dict:
        """Load caregiver contact info from config file."""
        if os.path.exists(CAREGIVER_CONFIG):
            try:
                with open(CAREGIVER_CONFIG) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def alert(self, alert_type: str, message: str, details: str = "",
              user_said: str = ""):
        """Send an alert to the caregiver."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alert = {
            "type": alert_type,
            "message": message,
            "details": details,
            "user_said": user_said,
            "time": timestamp,
        }
        self.alert_history.append(alert)

        # Always log to file
        self._log_alert(alert)

        # Send to web dashboard
        threading.Thread(
            target=self._send_to_dashboard, args=(alert,), daemon=True
        ).start()

        # Send email if configured
        if self.config.get("email"):
            threading.Thread(
                target=self._send_email, args=(alert,), daemon=True
            ).start()

        print(f"[ALERT] ⚠️  {alert_type}: {message}")

    def alert_crisis(self, user_text: str):
        """Alert for mental health crisis keywords."""
        self.alert(
            "CRISIS",
            "User expressed concerning thoughts that may indicate a mental health crisis.",
            user_said=user_text,
        )

    def alert_emergency(self, user_text: str):
        """Alert for physical emergency keywords."""
        self.alert(
            "EMERGENCY",
            "User may be experiencing a physical emergency (fall, pain, etc).",
            user_said=user_text,
        )

    def alert_sustained_distress(self, mood_history: list):
        """Alert when user has been sad/distressed for extended period."""
        self.alert(
            "SUSTAINED_DISTRESS",
            "User has shown signs of sadness or distress for an extended period.",
            details=f"Recent mood history: {mood_history[-5:]}",
        )

    def alert_checkin_concern(self, results: dict):
        """Alert when daily check-in reveals concerning patterns."""
        bad_areas = [k for k, v in results.items() if v == "bad"]
        if bad_areas:
            self.alert(
                "CHECKIN_CONCERN",
                f"Daily check-in flagged concerns in: {', '.join(bad_areas)}",
                details=f"Full results: {results}",
            )

    def alert_medication_request(self, user_text: str):
        """Alert when user asks for medication."""
        self.alert(
            "MEDICATION_REQUEST",
            "User is requesting medication assistance.",
            user_said=user_text,
        )

    def alert_food_request(self, user_text: str):
        """Alert when user asks for food or drink."""
        self.alert(
            "FOOD_REQUEST",
            "User is requesting food or drink.",
            user_said=user_text,
        )

    def alert_help_request(self, user_text: str):
        """Alert when user asks for general help."""
        self.alert(
            "HELP_REQUEST",
            "User is requesting help from a caregiver.",
            user_said=user_text,
        )

    def _send_to_dashboard(self, alert: dict):
        """POST alert to the caregiver web dashboard."""
        try:
            import urllib.request
            data = json.dumps(alert).encode("utf-8")
            req = urllib.request.Request(
                f"{self.dashboard_url}/api/alerts",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
            print("[ALERT] Sent to dashboard")
        except Exception as e:
            print(f"[ALERT] Dashboard unreachable: {e}")

    def _log_alert(self, alert: dict):
        """Append alert to the log file."""
        try:
            with open(ALERTS_LOG, "a") as f:
                f.write(f"[{alert['time']}] {alert['type']}: {alert['message']}")
                if alert["details"]:
                    f.write(f" | {alert['details']}")
                f.write("\n")
        except Exception as e:
            print(f"[ALERT] Could not write log: {e}")

    def _send_email(self, alert: dict):
        """Send email alert to caregiver (requires SMTP config)."""
        try:
            cfg = self.config
            smtp_host = cfg.get("smtp_host", "smtp.gmail.com")
            smtp_port = cfg.get("smtp_port", 587)
            sender = cfg.get("sender_email", "")
            password = cfg.get("sender_password", "")
            recipient = cfg.get("email", "")

            if not all([sender, password, recipient]):
                return

            subject = f"[Reachy Alert] {alert['type']}: {alert['message'][:50]}"
            body = (
                f"Alert Type: {alert['type']}\n"
                f"Time: {alert['time']}\n"
                f"Message: {alert['message']}\n"
                f"Details: {alert['details']}\n"
                f"\n— Reachy Accessibility Assistant"
            )

            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = recipient

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(sender, password)
                server.send_message(msg)

            print(f"[ALERT] Email sent to {recipient}")
        except Exception as e:
            print(f"[ALERT] Email failed: {e}")
