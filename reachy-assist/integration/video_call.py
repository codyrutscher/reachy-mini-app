"""Video Call Assistant — helps the patient connect with family via video calls.

Manages contacts, initiates calls through the dashboard, facilitates
the call if patient gets confused, and summarizes afterward.
"""

import json
import logging
import os
import time
import urllib.request

logger = logging.getLogger(__name__)


class VideoCallAssistant:
    """Facilitates video calls between patient and family."""

    def __init__(self, dashboard_url: str = "http://localhost:5555"):
        self._dashboard_url = dashboard_url
        self._contacts = {}  # name -> {phone, relationship, schedule}
        self._call_active = False
        self._current_contact = ""
        self._call_start_time = 0
        self._call_history = []

    def add_contact(self, name: str, relationship: str = "", phone: str = "") -> str:
        self._contacts[name.lower()] = {
            "name": name,
            "relationship": relationship,
            "phone": phone,
            "schedule": "",
        }
        return f"Added {name} ({relationship}) to your contacts."

    def set_schedule(self, name: str, schedule: str) -> str:
        key = name.lower()
        if key in self._contacts:
            self._contacts[key]["schedule"] = schedule
            return f"I'll remind you about calls with {name}: {schedule}"
        return f"I don't have {name} in your contacts."

    def list_contacts(self) -> str:
        if not self._contacts:
            return "No contacts saved yet. Ask a caregiver to add family contacts."
        lines = []
        for c in self._contacts.values():
            rel = f" ({c['relationship']})" if c.get("relationship") else ""
            sched = f" — {c['schedule']}" if c.get("schedule") else ""
            lines.append(f"{c['name']}{rel}{sched}")
        return "Your contacts: " + ", ".join(lines)

    def initiate_call(self, name: str) -> str:
        """Start a video call with a contact."""
        key = name.lower()
        # Fuzzy match
        matched = None
        for k, c in self._contacts.items():
            if key in k or key in c.get("relationship", "").lower():
                matched = c
                break

        if not matched:
            return (
                f"I don't have '{name}' in your contacts. "
                f"Would you like me to list who's available?"
            )

        self._call_active = True
        self._current_contact = matched["name"]
        self._call_start_time = time.time()

        # Notify dashboard to initiate call
        try:
            data = json.dumps({
                "type": "VIDEO_CALL_REQUEST",
                "message": f"Patient wants to call {matched['name']} ({matched.get('relationship', '')})",
                "contact": matched,
            }).encode()
            req = urllib.request.Request(
                f"{self._dashboard_url}/api/alerts",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.error("Call notification failed: %s", e)

        rel = matched.get("relationship", "")
        return (
            f"I'm setting up a call with {matched['name']}"
            f"{' — your ' + rel if rel else ''}. "
            f"The caregiver will help connect you. Just a moment!"
        )

    def end_call(self) -> str:
        if not self._call_active:
            return "No call in progress."
        duration = round((time.time() - self._call_start_time) / 60, 1)
        self._call_history.append({
            "contact": self._current_contact,
            "duration_minutes": duration,
            "timestamp": time.strftime("%Y-%m-%d %H:%M"),
        })
        self._call_active = False
        contact = self._current_contact
        self._current_contact = ""
        return f"Call with {contact} ended. That was about {duration} minutes. How was it?"

    def get_facilitation_prompt(self) -> str:
        """Get a prompt to help if patient seems confused during call."""
        if not self._call_active:
            return ""
        contact = self._contacts.get(self._current_contact.lower(), {})
        rel = contact.get("relationship", "someone who cares about you")
        return (
            f"You're on a call with {self._current_contact}, your {rel}. "
            f"They called to check in on you. You can tell them about your day!"
        )

    def check_scheduled_calls(self) -> str | None:
        """Check if any scheduled calls are due."""
        now_day = time.strftime("%A").lower()
        for c in self._contacts.values():
            sched = c.get("schedule", "").lower()
            if now_day in sched:
                return f"{c['name']} usually calls on {time.strftime('%A')}s. Would you like to call them?"
        return None

    @property
    def is_call_active(self) -> bool:
        return self._call_active

    def get_status(self) -> dict:
        return {
            "call_active": self._call_active,
            "current_contact": self._current_contact,
            "contacts_count": len(self._contacts),
            "call_history": self._call_history[-5:],
        }
