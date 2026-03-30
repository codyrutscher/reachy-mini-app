"""Adaptive Trivia — difficulty scales based on patient performance.

Personalized questions from patient facts, category selection,
streak tracking, and gentle encouragement.
"""

import logging
import os
import random

logger = logging.getLogger(__name__)

CATEGORIES = {
    "history": [
        {"q": "In what year did World War II end?", "a": "1945", "difficulty": 1},
        {"q": "Who was the first president of the United States?", "a": "George Washington", "difficulty": 1},
        {"q": "What ancient wonder was located in Egypt?", "a": "Great Pyramid", "difficulty": 2},
        {"q": "In what year did the Berlin Wall fall?", "a": "1989", "difficulty": 2},
        {"q": "Who wrote the Declaration of Independence?", "a": "Thomas Jefferson", "difficulty": 2},
        {"q": "What empire was ruled by Julius Caesar?", "a": "Roman", "difficulty": 1},
    ],
    "music": [
        {"q": "Who sang 'Imagine'?", "a": "John Lennon", "difficulty": 1},
        {"q": "What instrument has 88 keys?", "a": "piano", "difficulty": 1},
        {"q": "Who was known as the King of Rock and Roll?", "a": "Elvis Presley", "difficulty": 1},
        {"q": "What musical features 'Do Re Mi'?", "a": "The Sound of Music", "difficulty": 2},
        {"q": "How many strings does a standard guitar have?", "a": "six", "difficulty": 1},
    ],
    "nature": [
        {"q": "What is the largest ocean on Earth?", "a": "Pacific", "difficulty": 1},
        {"q": "What gas do plants absorb from the air?", "a": "carbon dioxide", "difficulty": 2},
        {"q": "What is the tallest type of tree?", "a": "redwood", "difficulty": 2},
        {"q": "How many legs does a spider have?", "a": "eight", "difficulty": 1},
        {"q": "What planet is known as the Red Planet?", "a": "Mars", "difficulty": 1},
    ],
    "sports": [
        {"q": "How many players are on a baseball team?", "a": "nine", "difficulty": 1},
        {"q": "In what sport do you use a shuttlecock?", "a": "badminton", "difficulty": 2},
        {"q": "What country hosted the first modern Olympics?", "a": "Greece", "difficulty": 2},
        {"q": "How many holes are on a standard golf course?", "a": "eighteen", "difficulty": 1},
    ],
}

ENCOURAGEMENTS = [
    "You're on fire! 🔥",
    "Great job, keep it up!",
    "That's right! You really know your stuff!",
    "Excellent! Your memory is sharp!",
    "Wonderful answer!",
]

GENTLE_WRONG = [
    "Good try! The answer was {answer}. You'll get the next one!",
    "Almost! It was {answer}. No worries, you're doing great!",
    "Not quite — it was {answer}. But you're learning!",
]


class AdaptiveTrivia:
    """Trivia game that adjusts difficulty based on performance."""

    def __init__(self, patient_facts: list[str] | None = None, patient_name: str = "friend"):
        self._patient_facts = patient_facts or []
        self._patient_name = patient_name
        self._active = False
        self._category = ""
        self._difficulty = 1  # 1=easy, 2=medium, 3=hard
        self._current_question = None
        self._score = 0
        self._streak = 0
        self._best_streak = 0
        self._questions_asked = 0
        self._asked_indices = set()

    def start(self, category: str = "") -> str:
        category = category.lower().strip()
        if category and category in CATEGORIES:
            self._category = category
        else:
            self._category = random.choice(list(CATEGORIES.keys()))
        self._active = True
        self._score = 0
        self._streak = 0
        self._questions_asked = 0
        self._asked_indices.clear()
        return self._next_question()

    def _next_question(self) -> str:
        # Try to generate a personal question first (every 3rd question)
        if self._questions_asked > 0 and self._questions_asked % 3 == 0 and self._patient_facts:
            personal = self._generate_personal_question()
            if personal:
                self._current_question = personal
                self._questions_asked += 1
                return f"Here's a personal one: {personal['q']}"

        # Pick from category based on difficulty
        pool = CATEGORIES.get(self._category, [])
        available = [
            (i, q) for i, q in enumerate(pool)
            if i not in self._asked_indices and q["difficulty"] <= self._difficulty
        ]
        if not available:
            self._asked_indices.clear()
            available = [(i, q) for i, q in enumerate(pool) if q["difficulty"] <= self._difficulty]

        if not available:
            return self.stop()

        idx, question = random.choice(available)
        self._asked_indices.add(idx)
        self._current_question = question
        self._questions_asked += 1
        return f"Question {self._questions_asked}: {question['q']}"

    def answer(self, text: str) -> str:
        if not self._active or not self._current_question:
            return "No active question. Say 'trivia' to start!"

        correct_answer = self._current_question["a"].lower()
        user_answer = text.lower().strip()

        # Flexible matching
        is_correct = (
            correct_answer in user_answer or
            user_answer in correct_answer or
            any(w in user_answer for w in correct_answer.split() if len(w) > 3)
        )

        if is_correct:
            self._score += 1
            self._streak += 1
            self._best_streak = max(self._best_streak, self._streak)
            # Increase difficulty after 3 correct in a row
            if self._streak >= 3 and self._difficulty < 3:
                self._difficulty += 1
            response = random.choice(ENCOURAGEMENTS)
            if self._streak >= 3:
                response += f" That's {self._streak} in a row!"
        else:
            self._streak = 0
            # Decrease difficulty after wrong answer
            if self._difficulty > 1:
                self._difficulty -= 1
            response = random.choice(GENTLE_WRONG).format(answer=self._current_question["a"])

        # Auto-continue or end after 10 questions
        if self._questions_asked >= 10:
            response += "\n" + self.stop()
        else:
            response += "\n" + self._next_question()

        return response

    def _generate_personal_question(self) -> dict | None:
        """Try to create a question from patient facts using GPT."""
        try:
            import openai
            client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
            facts_str = "; ".join(self._patient_facts[:5])
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": (
                        "Generate a simple, warm trivia question based on these personal facts. "
                        "The question should be answerable from the facts. "
                        "Return JSON: {\"q\": \"question\", \"a\": \"answer\"}"
                    ),
                }, {
                    "role": "user",
                    "content": f"Facts about {self._patient_name}: {facts_str}",
                }],
                max_tokens=100,
            )
            import json
            return json.loads(resp.choices[0].message.content.strip())
        except Exception:
            return None

    def stop(self) -> str:
        self._active = False
        return (
            f"Game over! You scored {self._score}/{self._questions_asked}. "
            f"Best streak: {self._best_streak}. Great job, {self._patient_name}!"
        )

    @property
    def is_active(self) -> bool:
        return self._active

    def list_categories(self) -> str:
        return f"Categories: {', '.join(CATEGORIES.keys())}, or personal questions from your life!"

    def get_status(self) -> dict:
        return {
            "active": self._active,
            "category": self._category,
            "score": self._score,
            "streak": self._streak,
            "best_streak": self._best_streak,
            "difficulty": self._difficulty,
            "questions_asked": self._questions_asked,
        }
