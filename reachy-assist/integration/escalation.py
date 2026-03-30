"""Emergency Contact Chain — escalates alerts if caregiver doesn't respond.

When a critical alert is sent and not acknowledged within a timeout,
escalates to family contacts via email and dashboard notification.
"""

import json
import os
import smtplib
import threading
import time
from email.mime.text import MIMEText
from core.log_config import get_logger

logger = get_logger("escalation")

CAREGIVER_CONFIG = os.path.join(os.path.dirname(__file__), "caregiver.json")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:5555")

# How long to wait before escalating (seconds)
ESCALATION_TIMEOUT = int(os.environ.get("ESCALATION_TIMEOUT", "300"))  # 5 minutes

_pending_escalations = {}  # alert_id -> {alert, timestamp}


def _get_config() -> dict:
    if os.path.exists(CAREGIVER_CONFIG):
        try:
            with open(CAREGIVER_CONFIG) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def schedule_escalation(alert_type: str, message: str, patient_id: str = "default") -> None:
    """Schedule an escalation check for a critical alert."""
    if alert_type not in ("CRISIS", "EMERGENCY", "FALL_DETECTED"):
        return

    alert_id = f"{alert_type}_{int(time.time())}"
    _pending_escalations[alert_id] = {
        "type": alert_type,
        "message": message,
        "patient_id": patient_id,
        "timestamp": time.time(),
    }

    # Start a background timer to check if it was acknowledged
    threading.Thread(
        target=_check_and_escalate,
        args=(alert_id,),
        daemon=True,
    ).start()

    logger.info("Escalation scheduled for %s (timeout: %ds)", alert_type, ESCALATION_TIMEOUT)


def cancel_escalation(alert_type: str) -> None:
    """Cancel pending escalation (called when alert is acknowledged)."""
    to_remove = [k for k, v in _pending_escalations.items() if v["type"] == alert_type]
    for k in to_remove:
        del _pending_escalations[k]
        logger.info("Escalation cancelled for %s", alert_type)


def _check_and_escalate(alert_id: str) -> None:
    """Wait for timeout, then check if alert was acknowledged."""
    time.sleep(ESCALATION_TIMEOUT)

    if alert_id not in _pending_escalations:
        return  # was cancelled (acknowledged)

    alert = _pending_escalations.pop(alert_id, None)
    if not alert:
        return

    logger.warning("Alert not acknowledged — escalating: %s", alert["type"])
    _escalate_to_family(alert)


def _escalate_to_family(alert: dict) -> None:
    """Send escalation to family contacts."""
    cfg = _get_config()
    family_email = cfg.get("family_email")
    emergency_contacts = cfg.get("emergency_contacts", [])

    # Send to dashboard as high-priority alert
    try:
        import urllib.request
        data = json.dumps({
            "type": f"ESCALATED_{alert['type']}",
            "message": f"⚠️ ESCALATED: {alert['message']} (caregiver did not respond within {ESCALATION_TIMEOUT // 60} minutes)",
            "details": "This alert was escalated because no caregiver acknowledged it.",
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{DASHBOARD_URL}/api/alerts",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass

    # Email family
    recipients = []
    if family_email:
        recipients.append(family_email)
    recipients.extend(emergency_contacts)

    if not recipients:
        logger.warning("No emergency contacts configured for escalation")
        return

    sender = cfg.get("sender_email", "")
    password = cfg.get("sender_password", "")
    if not all([sender, password]):
        return

    subject = f"⚠️ URGENT: Reachy Care Alert — {alert['type']}"
    body = (
        f"This is an automated escalation from Reachy Care.\n\n"
        f"Alert: {alert['type']}\n"
        f"Message: {alert['message']}\n\n"
        f"This alert was not acknowledged by the caregiver within "
        f"{ESCALATION_TIMEOUT // 60} minutes and has been escalated to you.\n\n"
        f"Please check on the patient or contact the care facility.\n\n"
        f"— Reachy Care Emergency System"
    )

    for recipient in recipients:
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = recipient
            with smtplib.SMTP(cfg.get("smtp_host", "smtp.gmail.com"), cfg.get("smtp_port", 587)) as server:
                server.starttls()
                server.login(sender, password)
                server.send_message(msg)
            logger.info("Escalation email sent to %s", recipient)
        except Exception as e:
            logger.error("Escalation email failed for %s: %s", recipient, e)
