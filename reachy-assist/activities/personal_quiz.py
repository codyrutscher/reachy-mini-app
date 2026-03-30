"""Personalized Daily Quiz — generates memory exercise questions from
the patient's own life facts stored in Supabase.

Example: "You told me your daughter's name is Sarah — what city does she live in?"

The quiz pulls from bot_patient_facts and builds questions that test
and exercise the patient's memory using their real life details.
"""

import random

_QUIZ_TRIGGERS = [
    "quiz me", "test my memory", "memory game", "ask me questions",
    "quiz time", "let's do a quiz", "memory quiz", "brain game",
    "test me", "memory exercise",
]

# Templates: (category_match, question_template, follow_up)
# {fact} gets replaced with the actual fact text
_QUESTION_TEMPLATES = [
    ("family", "You've told me about your family. Can you tell me — {hint}?", "That's wonderful. Family is so important."),
    ("pet", "You mentioned a pet you love. Do you remember — {hint}?", "What a lovely memory."),
    ("career", "You shared something about your work life. Can you recall — {hint}?", "That's a great memory to hold onto."),
    ("hobby", "You told me about something you enjoy doing. What was it — {hint}?", "It's so nice that you remember that."),
    ("interest", "You mentioned something you're interested in. Do you remember — {hint}?", "You have great taste."),
    ("food", "You told me about a food you like. Can you remember — {hint}?", "That sounds delicious."),
    ("music", "You shared a song or music you enjoy. What was it — {hint}?", "Music is such a gift."),
    ("location", "You mentioned a place that's special to you. Where was it — {hint}?", "What a special place."),
    ("preference", "You told me about something you prefer. Do you recall — {hint}?", "Good to know."),
    ("general", "You shared something with me before. Can you remember — {hint}?", "You have a wonderful memory."),
]


def is_quiz_trigger(text: str) -> bool:
    """Return True if the patient wants to start a quiz."""
    lower = text.lower()
    return any(t in lower for t in _QUIZ_TRIGGERS)


def _make_hint(fact_text: str) -> str:
    """Turn a fact into a hint/question fragment."""
    # Remove common prefixes
    text = fact_text.strip()
    for prefix in ["Grateful for: ", "Patient mentioned: ", "Patient said: "]:
        if text.startswith(prefix):
            text = text[len(prefix):]
    # Truncate if too long
    if len(text) > 80:
        text = text[:77] + "..."
    return text


class PersonalQuiz:
    """Manages a quiz session using the patient's own facts."""

    def __init__(self, patient_id="default"):
        self.patient_id = patient_id
        self.active = False
        self.questions = []  # list of (question, follow_up, original_fact)
        self.current = 0
        self.score = 0
        self.total = 0

    def start(self) -> str:
        """Load facts and return the opening prompt."""
        facts = self._load_facts()
        if not facts or len(facts) < 2:
            return (
                "(The patient wants a memory quiz but there aren't enough facts "
                "stored yet. Warmly tell them you need to get to know them a bit "
                "more first. Suggest chatting about their family, hobbies, or "
                "favorite foods so you can make a personalized quiz next time.)"
            )

        self.active = True
        self.questions = self._build_questions(facts)
        self.current = 0
        self.score = 0
        self.total = len(self.questions)

        first_q = self.questions[0][0]
        return (
            f"(Start a personalized memory quiz with the patient. You have "
            f"{self.total} questions based on things they've told you before. "
            f"Say something warm like 'Let's exercise that wonderful memory of yours! "
            f"I have {self.total} questions based on things you've shared with me.' "
            f"Then ask the first question: {first_q})"
        )

    def check_answer(self, answer: str) -> str:
        """Process the patient's answer and return the next prompt."""
        if not self.active or self.current >= len(self.questions):
            self.active = False
            return ""

        _question, follow_up, original_fact = self.questions[self.current]
        self.current += 1
        # We always count it as correct — this is therapeutic, not a test
        self.score += 1

        if self.current >= len(self.questions):
            # Quiz complete
            self.active = False
            return self._wrap_up(follow_up, original_fact)

        next_q = self.questions[self.current][0]
        remaining = self.total - self.current
        return (
            f"(The patient answered the quiz question. The original fact was: "
            f"'{original_fact}'. React warmly to their answer — {follow_up} "
            f"If they got it right, celebrate. If they struggled, gently remind them "
            f"and be encouraging. Never make them feel bad. "
            f"Then ask the next question ({remaining} left): {next_q})"
        )

    def _wrap_up(self, last_follow_up: str, last_fact: str) -> str:
        """Build the closing prompt."""
        return (
            f"(The patient just finished the last quiz question. The fact was: "
            f"'{last_fact}'. {last_follow_up} "
            f"Now wrap up the quiz warmly. They answered {self.score} out of "
            f"{self.total} questions. Say something like 'You did wonderfully! "
            f"Your memory is really something special.' Don't give a score — "
            f"just make them feel good. Ask if they'd like to play again sometime.)"
        )

    def _load_facts(self):
        """Load patient facts from Supabase."""
        try:
            import memory.db_supabase as _db
            if not _db.is_available():
                return []
            return _db.get_facts(self.patient_id)
        except Exception:
            return []

    def _build_questions(self, facts, max_questions=5):
        """Build quiz questions from facts."""
        # Shuffle and pick up to max_questions
        random.shuffle(facts)
        selected = facts[:max_questions]

        questions = []
        for fact in selected:
            category = fact.get("category", "general")
            fact_text = fact.get("fact", "")
            if not fact_text:
                continue

            hint = _make_hint(fact_text)

            # Find a matching template
            template = None
            for cat, tmpl, follow in _QUESTION_TEMPLATES:
                if cat == category:
                    template = (tmpl, follow)
                    break
            if not template:
                template = _QUESTION_TEMPLATES[-1][1:]  # general fallback

            question = template[0].replace("{hint}", hint)
            questions.append((question, template[1], fact_text))

        return questions

    @property
    def is_active(self) -> bool:
        return self.active
