"""Interactive storytelling — Reachy and the patient co-create a story
where the patient is the hero.  Uses their name and known facts to
personalise the adventure.  The story is built turn-by-turn: GPT
narrates a scene, the patient decides what happens next.

This module manages session state.  Conversation injection happens
in realtime_conversation.py.
"""


_STORY_TRIGGERS = [
    "tell me a story about me", "make up a story", "let's create a story",
    "interactive story", "i want to be in a story", "story where i'm the hero",
    "adventure story", "make me the hero", "let's make a story together",
    "story time with me in it", "put me in a story",
]


def is_story_trigger(text: str) -> bool:
    """Return True if the patient wants to start an interactive story."""
    lower = text.lower()
    return any(t in lower for t in _STORY_TRIGGERS)


class InteractiveStory:
    """Tracks one interactive storytelling session."""

    def __init__(self, patient_id="default", patient_name="", facts=None):
        self.patient_id = patient_id
        self.patient_name = patient_name or "our hero"
        self.facts = facts or []
        self.active = False
        self.turns = []       # list of (narrator, text) tuples
        self.turn_count = 0
        self.max_turns = 6    # story wraps up after ~6 patient choices

    def start(self) -> str:
        """Return the opening prompt to inject into the conversation."""
        self.active = True
        self.turns = []
        self.turn_count = 0

        # Build a fact string for personalisation
        fact_hint = ""
        if self.facts:
            sample = self.facts[:5]
            fact_hint = (
                f" Here are some things you know about them that you can weave "
                f"into the story: {'; '.join(sample)}."
            )

        return (
            f"(Start an interactive story where the patient is the main character. "
            f"Their name is {self.patient_name}.{fact_hint} "
            f"Set the scene in 3-4 sentences — something warm and magical, like "
            f"a garden, a seaside village, or a cozy town. End the scene with a "
            f"choice for the patient: give them two options of what to do next. "
            f"Keep the tone gentle, fun, and easy to follow. "
            f"Don't use complex vocabulary. This is meant to be joyful.)"
        )

    def continue_story(self, patient_choice: str) -> str:
        """Patient made a choice — return the next narration prompt."""
        self.turns.append(("patient", patient_choice))
        self.turn_count += 1

        if self.turn_count >= self.max_turns:
            return self._wrap_up(patient_choice)

        remaining = self.max_turns - self.turn_count
        return (
            f"(The patient chose: \"{patient_choice[:150]}\". "
            f"Continue the interactive story based on their choice. Narrate what "
            f"happens next in 3-4 sentences — make it vivid and fun. "
            f"Then give them another choice of what to do. "
            f"There are about {remaining} turns left in the story, so keep building "
            f"toward a satisfying ending. Keep using their name {self.patient_name}.)"
        )

    def record_narration(self, text: str):
        """Record what GPT narrated (for saving later)."""
        self.turns.append(("narrator", text))

    def _wrap_up(self, final_choice: str) -> str:
        """Final turn — tell GPT to wrap up the story."""
        self.active = False
        return (
            f"(The patient chose: \"{final_choice[:150]}\". "
            f"This is the final scene of the interactive story. Wrap it up with "
            f"a happy, satisfying ending in 4-5 sentences. Make {self.patient_name} "
            f"the hero who saved the day. End with something warm like "
            f"'And that's the story of {self.patient_name}, the bravest adventurer "
            f"of all.' Then ask if they'd like to hear it again sometime or create "
            f"a new adventure.)"
        )

    def save(self):
        """Save the completed story to Supabase."""
        if not self.turns:
            return
        # Build full story text
        parts = []
        for speaker, text in self.turns:
            if speaker == "narrator":
                parts.append(text)
            else:
                parts.append(f"[{self.patient_name} chose: {text}]")
        full_story = "\n\n".join(parts)

        try:
            import db_supabase as _db
            if _db.is_available():
                _db.save_fact(
                    "story",
                    f"Interactive story: {full_story[:500]}",
                    self.patient_id,
                )
                _db.save_conversation(
                    "story",
                    f"Completed interactive story ({len(self.turns)} parts)",
                    self.patient_id,
                    "assistant",
                    "joy",
                )
        except Exception as e:
            print(f"[STORY] Save error: {e}")

    @property
    def is_active(self) -> bool:
        return self.active
