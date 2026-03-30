"""Mood Report Email — sends daily/weekly mood summaries to family.

Generates a formatted mood report from session data and emails it
to configured family email addresses.
"""

import json
import os
import smtplib
from datetime import datetime, date
from email.mime.text import MIMEText
from core.log_config import get_logger

logger = get_logger("mood_report")

CAREGIVER_CONFIG = os.path.join(os.path.dirname(__file__), "caregiver.json")


def _get_config() -> dict:
    if os.path.exists(CAREGIVER_CONFIG):
        try:
            with open(CAREGIVER_CONFIG) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def generate_mood_report(patient_id: str = "default", days: int = 1) -> dict:
    """Generate a mood report for the last N days."""
    report = {"date": date.today().isoformat(), "period_days": days}

    try:
        from memory import db_supabase as db
        if not db.is_available():
            return report

        moods = db.get_moods(patient_id, limit=200)
        if moods:
            counts = {}
            for m in moods:
                mood = m.get("mood", "neutral")
                counts[mood] = counts.get(mood, 0) + 1
            total = sum(counts.values()) or 1
            report["mood_distribution"] = {k: round(v / total * 100, 1) for k, v in counts.items()}
            report["dominant_mood"] = max(counts, key=counts.get)
            report["total_readings"] = total

        sessions = db.get_session_summaries(patient_id, limit=days * 3)
        if sessions:
            report["total_sessions"] = len(sessions)
            report["total_interactions"] = sum(s.get("interactions", 0) for s in sessions)
            summaries = [s.get("summary_text", "") for s in sessions if s.get("summary_text")]
            report["session_highlights"] = summaries[:3]

        report["streak"] = db.get_streak(patient_id)
    except Exception as e:
        logger.debug("Report generation failed: %s", e)

    return report


def format_email(report: dict, patient_name: str = "your loved one") -> str:
    """Format the mood report as a readable email body."""
    lines = [f"Daily Mood Report for {patient_name}", f"Date: {report.get('date', '')}", ""]

    mood_dist = report.get("mood_distribution", {})
    if mood_dist:
        dominant = report.get("dominant_mood", "neutral")
        lines.append(f"Overall mood today: {dominant}")
        lines.append("Mood breakdown:")
        for mood, pct in sorted(mood_dist.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {mood}: {pct}%")
        lines.append("")

    sessions = report.get("total_sessions", 0)
    interactions = report.get("total_interactions", 0)
    if sessions:
        lines.append(f"Sessions today: {sessions}")
        lines.append(f"Total interactions: {interactions}")

    streak = report.get("streak", 0)
    if streak:
        lines.append(f"Conversation streak: {streak} days")

    highlights = report.get("session_highlights", [])
    if highlights:
        lines.append("")
        lines.append("Session highlights:")
        for h in highlights:
            lines.append(f"  • {h[:150]}")

    lines.extend(["", "— Reachy Care"])
    return "\n".join(lines)


def send_mood_report(patient_id: str = "default", days: int = 1) -> bool:
    """Generate and email a mood report."""
    cfg = _get_config()
    family_email = cfg.get("family_email") or cfg.get("email")
    if not family_email:
        logger.debug("No family email configured")
        return False

    report = generate_mood_report(patient_id, days)
    patient_name = "your loved one"
    try:
        from memory import db_supabase as db
        if db.is_available():
            profile = db.get_profile(patient_id)
            if profile and profile.get("user_name"):
                patient_name = profile["user_name"]
    except Exception:
        pass

    subject = f"Reachy Care — {'Weekly' if days > 1 else 'Daily'} Mood Report"
    body = format_email(report, patient_name)

    try:
        sender = cfg.get("sender_email", "")
        password = cfg.get("sender_password", "")
        if not all([sender, password]):
            logger.debug("SMTP not configured")
            return False

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = family_email

        with smtplib.SMTP(cfg.get("smtp_host", "smtp.gmail.com"), cfg.get("smtp_port", 587)) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)

        logger.info("Mood report emailed to %s", family_email)
        return True
    except Exception as e:
        logger.error("Failed to send mood report: %s", e)
        return False
