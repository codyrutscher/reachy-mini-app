"""Medication and appointment reminder system for Reachy."""

import json
import os
import threading
import time
from datetime import datetime, timedelta

REMINDERS_FILE = os.path.join(os.path.dirname(__file__), "reminders.json")


class ReminderManager:
    """Tracks medications and appointments, fires reminders at the right time."""

    def __init__(self, on_reminder=None):
        self.medications = []   # {"name": "Aspirin", "times": ["08:00", "20:00"]}
        self.appointments = []  # {"what": "Dr. Smith", "when": "2026-03-20 14:00"}
        self.on_reminder = on_reminder  # callback(message: str)
        self._running = False
        self._thread = None
        self._reminded_today = set()  # track what we already reminded
        self._load()

    # ── Persistence ─────────────────────────────────────────────────

    def _load(self):
        if os.path.exists(REMINDERS_FILE):
            try:
                with open(REMINDERS_FILE) as f:
                    data = json.load(f)
                self.medications = data.get("medications", [])
                self.appointments = data.get("appointments", [])
                print(f"[REMIND] Loaded {len(self.medications)} meds, {len(self.appointments)} appointments")
            except Exception as e:
                print(f"[REMIND] Could not load reminders: {e}")

    def _save(self):
        data = {"medications": self.medications, "appointments": self.appointments}
        with open(REMINDERS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    # ── Add / remove ────────────────────────────────────────────────

    def add_medication(self, name: str, times: list[str]) -> str:
        """Add a medication. times = list of "HH:MM" strings."""
        self.medications.append({"name": name, "times": times})
        self._save()
        times_str = ", ".join(times)
        return f"Got it! I'll remind you to take {name} at {times_str} every day."

    def add_appointment(self, what: str, when: str) -> str:
        """Add an appointment. when = "YYYY-MM-DD HH:MM" string."""
        self.appointments.append({"what": what, "when": when})
        self._save()
        return f"I've noted your appointment: {what} on {when}. I'll remind you beforehand."

    def remove_medication(self, name: str) -> str:
        before = len(self.medications)
        self.medications = [m for m in self.medications if m["name"].lower() != name.lower()]
        self._save()
        if len(self.medications) < before:
            return f"Removed {name} from your medications."
        return f"I don't have {name} in your medication list."

    def list_reminders(self) -> str:
        parts = []
        if self.medications:
            parts.append("Your medications:")
            for m in self.medications:
                parts.append(f"  - {m['name']} at {', '.join(m['times'])}")
        else:
            parts.append("You don't have any medications set up.")

        if self.appointments:
            parts.append("Your upcoming appointments:")
            for a in self.appointments:
                parts.append(f"  - {a['what']} on {a['when']}")
        else:
            parts.append("No upcoming appointments.")

        return "\n".join(parts)

    # ── Background checker ──────────────────────────────────────────

    def start(self):
        """Start the background reminder thread."""
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[REMIND] Reminder system active")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def _loop(self):
        while self._running:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            today = now.strftime("%Y-%m-%d")

            # Reset reminded set at midnight
            if current_time == "00:00":
                self._reminded_today.clear()

            # Check medications
            for med in self.medications:
                for t in med["times"]:
                    key = f"med:{med['name']}:{t}:{today}"
                    if key not in self._reminded_today and current_time == t:
                        msg = f"Time to take your {med['name']}! Don't forget."
                        self._fire(msg)
                        self._reminded_today.add(key)

            # Check appointments (remind 1 hour before and 15 min before)
            for apt in self.appointments:
                try:
                    apt_time = datetime.strptime(apt["when"], "%Y-%m-%d %H:%M")
                    diff = (apt_time - now).total_seconds() / 60  # minutes

                    key_1h = f"apt:{apt['what']}:1h:{today}"
                    if 59 <= diff <= 61 and key_1h not in self._reminded_today:
                        msg = f"Reminder: you have {apt['what']} in about 1 hour."
                        self._fire(msg)
                        self._reminded_today.add(key_1h)

                    key_15m = f"apt:{apt['what']}:15m:{today}"
                    if 14 <= diff <= 16 and key_15m not in self._reminded_today:
                        msg = f"Heads up! {apt['what']} is in about 15 minutes."
                        self._fire(msg)
                        self._reminded_today.add(key_15m)
                except ValueError:
                    pass

            time.sleep(30)  # check every 30 seconds

    def _fire(self, message: str):
        print(f"[REMIND] 🔔 {message}")
        if self.on_reminder:
            self.on_reminder(message)

    def clear_past_appointments(self) -> str:
        """Remove appointments that have already passed."""
        now = datetime.now()
        before = len(self.appointments)
        self.appointments = [
            a for a in self.appointments
            if datetime.strptime(a["when"], "%Y-%m-%d %H:%M") > now
        ]
        self._save()
        removed = before - len(self.appointments)
        if removed:
            return f"Removed {removed} past appointment{'s' if removed > 1 else ''}."
        return "No past appointments to clear."
