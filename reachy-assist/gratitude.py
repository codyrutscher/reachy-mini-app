"""Gratitude practice — structured "3 things you're grateful for" session.

Reachy asks the patient for 3 things they're grateful for, one at a time.
Each answer is saved as a fact to Supabase. At the end, Reachy gives a
warm summary of all three.

This module provides the prompts and state management. The actual
conversation injection happens in realtime_conversation.py.
"""


class GratitudeSession:
    """Tracks a single gratitude practice session."""

    def __init__(self, patient_id="default"):
        self.patient_id = patient_id
        self.answers = []  # list of gratitude answers
        self.active = False
        self._current_ask = 0  # 0, 1, 2

    def start(self) -> str:
        """Start the session. Returns the first prompt to inject."""
        self.active = True
        self.answers = []
        self._current_ask = 0
        return (
            "(Start a gratitude practice with the patient. Say something warm like: "
            "'Let's do something nice together — I'd love to hear three things "
            "you're grateful for today. They can be big or small. "
            "What's the first thing that comes to mind?')"
        )

    def record_answer(self, text: str) -> str | None:
        """Record an answer and return the next prompt, or None if done."""
        if not self.active:
            return None

        self.answers.append(text)
        self._current_ask += 1

        # Save to Supabase as a fact
        try:
            import db_supabase as _db
            if _db.is_available():
                _db.save_fact("gratitude", f"Grateful for: {text[:200]}", self.patient_id)
        except Exception:
            pass

        if self._current_ask == 1:
            return (
                "(The patient shared their first gratitude. Acknowledge it warmly — "
                "react to what they said specifically, don't be generic. Then ask: "
                "'That's lovely. What's the second thing you're grateful for?')"
            )
        elif self._current_ask == 2:
            return (
                "(The patient shared their second gratitude. React to it genuinely. "
                "Then ask: 'And one more — what's the third thing you're grateful for today?')"
            )
        else:
            # All 3 collected — build summary
            self.active = False
            summary = self._build_summary()
            return summary

    def _build_summary(self) -> str:
        """Build a warm summary prompt from all 3 answers."""
        items = []
        for i, ans in enumerate(self.answers):
            items.append(f"{i+1}. {ans[:100]}")
        items_text = "; ".join(items)

        # Save the full gratitude session to Supabase conversation log
        try:
            import db_supabase as _db
            if _db.is_available():
                _db.save_conversation(
                    "gratitude",
                    f"Gratitude session: {items_text}",
                    self.patient_id,
                    "patient",
                    "joy",
                )
        except Exception:
            pass

        return (
            f"(The patient just shared 3 things they're grateful for: {items_text}. "
            f"Give them a beautiful, warm summary. Reflect back what they said — "
            f"mention each one briefly. End with something uplifting like "
            f"'What a wonderful list. Thank you for sharing that with me.' "
            f"Make it feel like a special moment.)"
        )

    @property
    def is_active(self) -> bool:
        return self.active

    @property
    def remaining(self) -> int:
        return max(0, 3 - self._current_ask)
