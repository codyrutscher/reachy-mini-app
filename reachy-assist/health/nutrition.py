"""Hydration & Nutrition Companion — tracks meals and water intake via conversation.

Proactive reminders, intake logging, and caregiver alerts if patient
hasn't eaten or drunk in too long.
"""

import logging
import re
import time

logger = logging.getLogger(__name__)

MEAL_KEYWORDS = [
    "breakfast", "lunch", "dinner", "supper", "snack", "ate", "eaten",
    "had a meal", "just ate", "finished eating", "had some food",
    "had toast", "had soup", "had sandwich", "had cereal",
]

DRINK_KEYWORDS = [
    "water", "drank", "drinking", "had a drink", "tea", "coffee",
    "juice", "milk", "had some water", "glass of", "cup of",
    "hydrated", "thirsty",
]

REMINDER_INTERVALS = {
    "water": 7200,   # remind every 2 hours
    "meal": 18000,   # remind every 5 hours
}


class NutritionCompanion:
    """Tracks meals and hydration through conversation."""

    def __init__(self, dashboard_url: str = "http://localhost:5555"):
        self._dashboard_url = dashboard_url
        self._meals_today = []
        self._drinks_today = []
        self._last_meal_time = 0
        self._last_drink_time = 0
        self._last_meal_reminder = 0
        self._last_drink_reminder = 0
        self._last_reset = time.strftime("%Y-%m-%d")

    def _reset_if_new_day(self):
        today = time.strftime("%Y-%m-%d")
        if today != self._last_reset:
            self._meals_today = []
            self._drinks_today = []
            self._last_reset = today

    def check_intake(self, text: str) -> str | None:
        """Check if the patient mentioned eating or drinking. Returns a response or None."""
        self._reset_if_new_day()
        lower = text.lower()
        now = time.time()

        # Detect meal mention
        if any(kw in lower for kw in MEAL_KEYWORDS):
            self._meals_today.append({
                "time": time.strftime("%H:%M"),
                "description": text[:100],
            })
            self._last_meal_time = now
            count = len(self._meals_today)
            logger.info("Meal logged: %s (total today: %d)", text[:50], count)
            self._log_to_dashboard("meal", text[:100])
            return f"That's meal number {count} today. Good to hear you're eating well!"

        # Detect drink mention
        if any(kw in lower for kw in DRINK_KEYWORDS):
            self._drinks_today.append({
                "time": time.strftime("%H:%M"),
                "description": text[:100],
            })
            self._last_drink_time = now
            count = len(self._drinks_today)
            logger.info("Drink logged: %s (total today: %d)", text[:50], count)
            self._log_to_dashboard("drink", text[:100])
            return f"Staying hydrated — that's drink number {count} today!"

        return None

    def should_remind_water(self) -> bool:
        """Check if it's time for a water reminder."""
        self._reset_if_new_day()
        now = time.time()
        hour = int(time.strftime("%H"))
        if hour < 7 or hour > 21:
            return False
        if now - self._last_drink_time > REMINDER_INTERVALS["water"] and \
           now - self._last_drink_reminder > REMINDER_INTERVALS["water"]:
            self._last_drink_reminder = now
            return True
        return False

    def should_remind_meal(self) -> bool:
        """Check if it's time for a meal reminder."""
        self._reset_if_new_day()
        now = time.time()
        hour = int(time.strftime("%H"))
        if hour < 7 or hour > 21:
            return False
        if now - self._last_meal_time > REMINDER_INTERVALS["meal"] and \
           now - self._last_meal_reminder > REMINDER_INTERVALS["meal"]:
            self._last_meal_reminder = now
            return True
        return False

    def get_water_reminder(self) -> str:
        hours = round((time.time() - self._last_drink_time) / 3600, 1) if self._last_drink_time else 0
        if hours > 3:
            return f"It's been about {hours:.0f} hours since your last drink. How about some water?"
        return "Just a gentle reminder — have you had some water recently?"

    def get_meal_reminder(self) -> str:
        hours = round((time.time() - self._last_meal_time) / 3600, 1) if self._last_meal_time else 0
        if hours > 5:
            return f"It's been a while since you last ate. Would you like a snack?"
        return "Have you had anything to eat recently? It's important to keep your energy up."

    def _log_to_dashboard(self, intake_type: str, description: str):
        try:
            import json
            import urllib.request
            data = json.dumps({
                "type": f"nutrition_{intake_type}",
                "description": description,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }).encode()
            req = urllib.request.Request(
                f"{self._dashboard_url}/api/activity",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    def get_status(self) -> dict:
        self._reset_if_new_day()
        return {
            "meals_today": len(self._meals_today),
            "drinks_today": len(self._drinks_today),
            "meals": self._meals_today,
            "drinks": self._drinks_today,
            "last_meal": self._meals_today[-1]["time"] if self._meals_today else "none",
            "last_drink": self._drinks_today[-1]["time"] if self._drinks_today else "none",
        }
