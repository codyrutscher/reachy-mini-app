"""Daily check-in routine — structured wellness assessment."""

import random


# The check-in walks through these areas one at a time
_CHECKIN_QUESTIONS = [
    {
        "area": "sleep",
        "question": "How did you sleep last night?",
        "followups": {
            "good": "That's great to hear. Good rest makes such a difference.",
            "bad": "I'm sorry to hear that. Would you like to try a relaxation exercise before bed tonight?",
            "neutral": "I hope tonight is a restful one for you.",
        },
    },
    {
        "area": "pain",
        "question": "Are you feeling any pain or discomfort today?",
        "followups": {
            "good": "Wonderful, I'm glad you're comfortable.",
            "bad": "I'm sorry you're hurting. Have you been able to talk to your doctor about it?",
            "neutral": "Okay. Please let me know if anything changes.",
        },
    },
    {
        "area": "mood",
        "question": "How are you feeling emotionally today? Happy, sad, anxious, or something else?",
        "followups": {
            "good": "I'm really glad to hear that. What's making today a good day?",
            "bad": "Thank you for telling me. I'm here for you. Would you like to talk about it?",
            "neutral": "That's okay. Sometimes days are just... days. I'm here if you want to chat.",
        },
    },
    {
        "area": "eating",
        "question": "Have you had something to eat and drink today?",
        "followups": {
            "good": "Good! Staying nourished is so important.",
            "bad": "It's important to eat and stay hydrated. Even something small would help. Can I remind you in a bit?",
            "neutral": "Try to have a little something when you can. Even a glass of water helps.",
        },
    },
    {
        "area": "social",
        "question": "Have you talked to anyone today — family, friends, a neighbor?",
        "followups": {
            "good": "That's lovely. Social connection is so good for the soul.",
            "bad": "I'm here with you, and I enjoy our chats. Would you like to call someone?",
            "neutral": "Well, you're talking to me! That counts, right?",
        },
    },
    {
        "area": "movement",
        "question": "Have you been able to move around a bit today? Even a short walk or some stretching?",
        "followups": {
            "good": "That's wonderful. Every little bit of movement helps.",
            "bad": "That's okay. Even gentle stretching in your chair can feel nice. Want to try together?",
            "neutral": "When you feel up to it, even a few minutes of gentle movement can lift your spirits.",
        },
    },
]

# Positive keywords to classify responses
_GOOD_WORDS = ["good", "great", "fine", "well", "yes", "wonderful", "slept well",
               "no pain", "happy", "ate", "drank", "talked", "walked", "moved"]
_BAD_WORDS = ["bad", "terrible", "awful", "no", "pain", "hurt", "didn't sleep",
              "sad", "anxious", "scared", "lonely", "hungry", "thirsty", "haven't"]


class DailyCheckIn:
    """Guided daily wellness check-in."""

    def __init__(self):
        self.active = False
        self.step = 0
        self.results = {}

    def start(self) -> str:
        """Begin the check-in. Returns the first question."""
        self.active = True
        self.step = 0
        self.results = {}
        return (
            "Let's do our daily check-in! I'll ask you a few quick questions "
            "about how you're doing today. Just answer naturally.\n\n"
            + _CHECKIN_QUESTIONS[0]["question"]
        )

    def process_answer(self, text: str) -> str:
        """Process the user's answer and return the next question or summary."""
        if not self.active or self.step >= len(_CHECKIN_QUESTIONS):
            self.active = False
            return ""

        current = _CHECKIN_QUESTIONS[self.step]
        sentiment = self._classify(text)
        self.results[current["area"]] = sentiment

        followup = current["followups"][sentiment]
        self.step += 1

        if self.step >= len(_CHECKIN_QUESTIONS):
            self.active = False
            summary = self._summarize()
            return f"{followup}\n\n{summary}"

        next_q = _CHECKIN_QUESTIONS[self.step]["question"]
        return f"{followup}\n\n{next_q}"

    def _classify(self, text: str) -> str:
        lower = text.lower()
        # Handle negations: "no pain" → good, "didn't sleep bad" → neutral
        negations = ["no ", "not ", "don't ", "didn't ", "haven't ", "wasn't "]
        good_score = sum(1 for w in _GOOD_WORDS if w in lower)
        bad_score = sum(1 for w in _BAD_WORDS if w in lower)
        # If a bad word is negated, flip it
        for neg in negations:
            for w in _BAD_WORDS:
                if neg + w in lower:
                    bad_score -= 1
                    good_score += 1
        if good_score > bad_score:
            return "good"
        elif bad_score > good_score:
            return "bad"
        return "neutral"

    def _summarize(self) -> str:
        """Generate a warm summary of the check-in."""
        good = [k for k, v in self.results.items() if v == "good"]
        bad = [k for k, v in self.results.items() if v == "bad"]

        parts = ["That's our check-in done! Here's what I noticed:"]
        if good:
            parts.append(f"You're doing well with: {', '.join(good)}. That's great!")
        if bad:
            parts.append(f"We might want to keep an eye on: {', '.join(bad)}.")
        if not bad:
            parts.append("Everything sounds pretty good today!")

        parts.append("I'm always here if you need anything.")
        return " ".join(parts)

    @property
    def is_active(self) -> bool:
        return self.active
