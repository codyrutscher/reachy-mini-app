"""Daily Routine Coach — Reachy guides the patient through their day.

Time-based activity suggestions, adaptive pacing, and progress tracking.
Integrates with existing reminders and medication systems.
"""

import logging
import time

logger = logging.getLogger(__name__)

# Default daily routine template
DEFAULT_ROUTINE = [
    {"time": "07:00", "activity": "Wake up and morning stretch", "category": "morning", "icon": "🌅"},
    {"time": "07:30", "activity": "Breakfast", "category": "meal", "icon": "🥣"},
    {"time": "08:00", "activity": "Morning medications", "category": "medication", "icon": "💊"},
    {"time": "09:00", "activity": "Light exercise or walk", "category": "exercise", "icon": "🚶"},
    {"time": "10:00", "activity": "Social activity or hobby", "category": "social", "icon": "🎨"},
    {"time": "11:00", "activity": "Brain game or reading", "category": "cognitive", "icon": "🧩"},
    {"time": "12:00", "activity": "Lunch", "category": "meal", "icon": "🍽️"},
    {"time": "13:00", "activity": "Rest or nap", "category": "rest", "icon": "😴"},
    {"time": "14:00", "activity": "Afternoon activity", "category": "activity", "icon": "🎵"},
    {"time": "15:00", "activity": "Snack and hydration", "category": "meal", "icon": "🥤"},
    {"time": "16:00", "activity": "Gentle movement or garden time", "category": "exercise", "icon": "🌿"},
    {"time": "17:00", "activity": "Evening medications", "category": "medication", "icon": "💊"},
    {"time": "18:00", "activity": "Dinner", "category": "meal", "icon": "🍲"},
    {"time": "19:00", "activity": "Family time or phone call", "category": "social", "icon": "📞"},
    {"time": "20:00", "activity": "Relaxation — music or stories", "category": "relaxation", "icon": "📖"},
    {"time": "21:00", "activity": "Bedtime routine", "category": "bedtime", "icon": "🌙"},
]


class RoutineCoach:
    """Guides the patient through daily activities with adaptive pacing."""

    def __init__(self):
        self._routine = list(DEFAULT_ROUTINE)
        self._completed = set()  # indices of completed activities today
        self._last_reset_day = time.strftime("%Y-%m-%d")
        self._patient_energy = "normal"  # low, normal, high
        self._skipped = set()

    def _reset_if_new_day(self):
        today = time.strftime("%Y-%m-%d")
        if today != self._last_reset_day:
            self._completed.clear()
            self._skipped.clear()
            self._last_reset_day = today
            self._patient_energy = "normal"

    def get_current_activity(self) -> dict | None:
        """Get the activity for the current time."""
        self._reset_if_new_day()
        now = time.strftime("%H:%M")
        # Find the most recent activity that hasn't been completed
        current = None
        for i, item in enumerate(self._routine):
            if item["time"] <= now and i not in self._completed and i not in self._skipped:
                current = {**item, "index": i}
        return current

    def get_next_activity(self) -> dict | None:
        """Get the next upcoming activity."""
        self._reset_if_new_day()
        now = time.strftime("%H:%M")
        for i, item in enumerate(self._routine):
            if item["time"] > now and i not in self._completed and i not in self._skipped:
                return {**item, "index": i}
        return None

    def complete_activity(self, index: int = -1) -> str:
        """Mark an activity as completed."""
        self._reset_if_new_day()
        if index < 0:
            current = self.get_current_activity()
            if current:
                index = current["index"]
            else:
                return "No current activity to complete."
        if 0 <= index < len(self._routine):
            self._completed.add(index)
            done = len(self._completed)
            total = len(self._routine)
            return f"Great job! {done} of {total} activities done today."
        return "Invalid activity."

    def skip_activity(self, index: int = -1) -> str:
        """Skip the current activity."""
        self._reset_if_new_day()
        if index < 0:
            current = self.get_current_activity()
            if current:
                index = current["index"]
            else:
                return "No current activity to skip."
        if 0 <= index < len(self._routine):
            self._skipped.add(index)
            return "No problem, we'll skip that one. Rest is important too."
        return "Invalid activity."

    def set_energy(self, level: str) -> str:
        """Set patient energy level to adapt suggestions."""
        level = level.lower()
        if level in ("low", "tired", "exhausted"):
            self._patient_energy = "low"
            return "I understand you're tired. Let's take it easy today."
        elif level in ("high", "energetic", "great"):
            self._patient_energy = "high"
            return "Wonderful! Let's make the most of that energy."
        else:
            self._patient_energy = "normal"
            return "Got it. We'll keep a nice steady pace."

    def get_suggestion(self) -> str:
        """Get a contextual suggestion based on time and energy."""
        self._reset_if_new_day()
        current = self.get_current_activity()
        if not current:
            nxt = self.get_next_activity()
            if nxt:
                return f"You're all caught up! Next up at {nxt['time']}: {nxt['icon']} {nxt['activity']}"
            return "You've had a full day! Time to relax."

        # Adapt based on energy
        if self._patient_energy == "low" and current["category"] == "exercise":
            return (
                f"I see it's time for {current['activity']}, but you mentioned feeling tired. "
                f"How about a gentle seated stretch instead? Or we can skip it and rest."
            )

        done = len(self._completed)
        total = len(self._routine)
        progress = f"({done}/{total} done today)"
        return f"{current['icon']} Time for: {current['activity']} {progress}"

    def get_progress(self) -> dict:
        self._reset_if_new_day()
        done = len(self._completed)
        skipped = len(self._skipped)
        total = len(self._routine)
        return {
            "completed": done,
            "skipped": skipped,
            "total": total,
            "percentage": round(done / total * 100) if total else 0,
            "energy": self._patient_energy,
            "activities": [
                {**item, "status": "done" if i in self._completed else "skipped" if i in self._skipped else "pending"}
                for i, item in enumerate(self._routine)
            ],
        }
