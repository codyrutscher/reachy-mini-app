"""Reminiscence therapy — guided conversations about past memories.

Reminiscence therapy is an evidence-based approach used in eldercare
to improve mood, reduce depression, and strengthen sense of identity."""

import random


# Themed conversation starters organized by life area
_THEMES = {
    "childhood": [
        "What's your earliest happy memory from when you were little?",
        "Did you have a favorite toy or game growing up?",
        "What was your neighborhood like when you were a child?",
        "Do you remember your favorite teacher? What made them special?",
        "What did you love to eat as a kid?",
    ],
    "family": [
        "Tell me about someone in your family who made you laugh.",
        "What's a family tradition you really loved?",
        "Do you have a favorite memory with your parents or grandparents?",
        "What's the best family gathering you can remember?",
        "Is there a family recipe that brings back good memories?",
    ],
    "love": [
        "Do you remember the first time you fell in love?",
        "What's the most romantic thing someone ever did for you?",
        "What's the best advice about love you've ever received?",
        "Tell me about a time someone made you feel really special.",
    ],
    "work": [
        "What was your first job? Did you enjoy it?",
        "What's the accomplishment you're most proud of in your career?",
        "Did you have a favorite coworker or boss? What made them great?",
        "If you could go back to any job you've had, which would it be?",
    ],
    "adventures": [
        "What's the most exciting trip you've ever taken?",
        "Have you ever done something that really surprised people?",
        "What's the bravest thing you've ever done?",
        "Is there a place you visited that you'll never forget?",
    ],
    "music_and_culture": [
        "What music did you love when you were young?",
        "Did you ever go to a concert or show that you'll never forget?",
        "What was your favorite movie or TV show growing up?",
        "Did you have a favorite song that always makes you smile?",
    ],
    "friendship": [
        "Tell me about your best friend. How did you meet?",
        "What's the funniest thing that ever happened with a friend?",
        "Is there a friend you've lost touch with that you think about?",
        "What makes someone a really good friend, in your experience?",
    ],
    "wisdom": [
        "What's the most important lesson life has taught you?",
        "If you could give advice to your younger self, what would it be?",
        "What do you think is the secret to a good life?",
        "What are you most grateful for when you look back?",
    ],
}

# Follow-up prompts to deepen the conversation
_DEEPENERS = [
    "That's a beautiful memory. What else do you remember about that?",
    "I love hearing about that. How did it make you feel?",
    "That sounds really special. Tell me more.",
    "What a wonderful story. Does it remind you of anything else?",
    "I can tell that means a lot to you. What made it so memorable?",
    "Thank you for sharing that with me. Was there more to that story?",
]


class ReminiscenceTherapy:
    """Guided reminiscence therapy sessions."""

    def __init__(self):
        self.active = False
        self.current_theme = None
        self.questions_asked = 0
        self.used_themes = []

    def start(self, theme: str = None) -> str:
        """Start a reminiscence session. Optionally pick a theme."""
        self.active = True
        self.questions_asked = 0

        if theme and theme in _THEMES:
            self.current_theme = theme
        else:
            # Pick a theme we haven't used recently
            available = [t for t in _THEMES if t not in self.used_themes]
            if not available:
                available = list(_THEMES.keys())
                self.used_themes.clear()
            self.current_theme = random.choice(available)

        self.used_themes.append(self.current_theme)
        theme_nice = self.current_theme.replace("_", " ")

        question = random.choice(_THEMES[self.current_theme])
        self.questions_asked += 1

        return (
            f"Let's take a little trip down memory lane. "
            f"I'd love to hear about your {theme_nice}.\n\n{question}"
        )

    def continue_session(self, user_response: str) -> str:
        """Continue the session with a follow-up or new question."""
        if not self.active:
            return ""

        self.questions_asked += 1

        # After 4-5 exchanges, gently wrap up
        if self.questions_asked >= 5:
            self.active = False
            return (
                random.choice(_DEEPENERS) + "\n\n"
                "Thank you so much for sharing those memories with me. "
                "I really enjoyed hearing about your life. "
                "We can do this again anytime you'd like."
            )

        # Alternate between deepening the current topic and asking new questions
        if self.questions_asked % 2 == 0:
            return random.choice(_DEEPENERS)
        else:
            remaining = [q for q in _THEMES[self.current_theme]]
            return random.choice(remaining)

    @property
    def is_active(self) -> bool:
        return self.active

    @staticmethod
    def available_themes() -> list[str]:
        return list(_THEMES.keys())
