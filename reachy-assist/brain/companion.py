"""Companion conversation starters — Reachy initiates interesting
topics to keep the patient engaged and stimulated."""

import random

CONVERSATION_TOPICS = [
    {
        "topic": "travel",
        "starters": [
            "If you could visit anywhere in the world, where would you go?",
            "What's the most beautiful place you've ever been to?",
            "Do you have a favorite vacation memory?",
        ],
    },
    {
        "topic": "food",
        "starters": [
            "What's your all-time favorite meal?",
            "Do you enjoy cooking? What's your specialty?",
            "If you could eat one food for the rest of your life, what would it be?",
        ],
    },
    {
        "topic": "childhood",
        "starters": [
            "What was your favorite thing to do as a kid?",
            "Did you have a best friend growing up? Tell me about them.",
            "What was your neighborhood like when you were young?",
        ],
    },
    {
        "topic": "music",
        "starters": [
            "What kind of music do you enjoy? Do you have a favorite song?",
            "Did you ever play a musical instrument?",
            "What song always makes you want to dance?",
        ],
    },
    {
        "topic": "family",
        "starters": [
            "Tell me about your family. Who makes you smile the most?",
            "Do you have any grandchildren? What are they like?",
            "What's a family tradition you love?",
        ],
    },
    {
        "topic": "hobbies",
        "starters": [
            "What hobbies have you enjoyed over the years?",
            "Have you ever tried painting or drawing?",
            "Do you enjoy reading? What's a book you loved?",
        ],
    },
    {
        "topic": "nature",
        "starters": [
            "Do you enjoy being outdoors? What's your favorite season?",
            "Have you ever had a garden? What did you grow?",
            "What's your favorite animal and why?",
        ],
    },
    {
        "topic": "life wisdom",
        "starters": [
            "What's the best advice you've ever received?",
            "If you could tell your younger self one thing, what would it be?",
            "What's something you've learned that you wish everyone knew?",
        ],
    },
    {
        "topic": "fun",
        "starters": [
            "If you could have any superpower, what would you choose?",
            "What's the funniest thing that ever happened to you?",
            "If you could meet anyone, living or not, who would it be?",
        ],
    },
    {
        "topic": "achievements",
        "starters": [
            "What's something you're really proud of in your life?",
            "What was your favorite job or career moment?",
            "What accomplishment makes you smile when you think about it?",
        ],
    },
]

_used_topics = []


def get_conversation_starter() -> str:
    """Get a random conversation topic starter, avoiding repeats."""
    global _used_topics
    available = [t for t in CONVERSATION_TOPICS if t["topic"] not in _used_topics]
    if not available:
        _used_topics = []
        available = CONVERSATION_TOPICS
    topic = random.choice(available)
    _used_topics.append(topic["topic"])
    starter = random.choice(topic["starters"])
    return starter


def get_topic_starter(topic_name: str) -> str:
    """Get a starter for a specific topic."""
    for t in CONVERSATION_TOPICS:
        if t["topic"] == topic_name:
            return random.choice(t["starters"])
    return get_conversation_starter()


def list_topics() -> str:
    """List available conversation topics."""
    topics = [t["topic"] for t in CONVERSATION_TOPICS]
    return "I can chat about: " + ", ".join(topics) + ". What interests you?"

def add_topic(topic: str, starters: list[str]) -> str:
    for t in CONVERSATION_TOPICS:
        if t["topic"] == topic:
            return f"Topic '{topic}' already exists."
    # if we get here, topic wasn't found — add it
    CONVERSATION_TOPICS.append({"topic": topic, "starters": starters})
    return f"Added topic '{topic}' with {len(starters)} conversation starters."


class TopicExplorer:
    """Guides a conversation deeper into a topic, level by level."""

    DEPTH_QUESTIONS = {
        "family": {
            1: ["Tell me about your family.", "Do you have a big family?", "Who's in your family?"],
            2: ["Who are you closest to in your family?", "What do you love most about them?"],
            3: ["What's your most treasured family memory?", "What would you want your family to know?"],
        },
        "travel": {
            1: ["Have you traveled much?", "What's a place you've visited?"],
            2: ["What made that trip special?", "Who did you travel with?"],
            3: ["If you could relive one trip, which would it be?", "How did traveling change you?"],
        },
        "childhood": {
            1: ["Where did you grow up?", "What was your neighborhood like?"],
            2: ["Who was your best friend as a kid?", "What did you love doing after school?"],
            3: ["What's a childhood moment you'll never forget?", "What would you tell your younger self?"],
        },
        "food": {
            1: ["Do you enjoy cooking?", "What's your favorite meal?"],
            2: ["Who taught you to cook?", "What meal reminds you of home?"],
            3: ["Is there a meal that brings back a special memory?", "What food means comfort to you?"],
        },
    }

    def __init__(self):
        self._current_topic = None
        self._depth = 0
        self._asked = []

    def start_topic(self, topic: str) -> str:
        """Start exploring a topic at depth level 1."""
        if topic not in self.DEPTH_QUESTIONS:
            return f"I don't have deep questions for '{topic}' yet. Try: {', '.join(self.DEPTH_QUESTIONS.keys())}"
        self._current_topic = topic
        self._depth = 1
        self._asked = []
        return self._ask_question()

    def go_deeper(self) -> str:
        """Move to the next depth level."""
        if not self._current_topic:
            return "We're not exploring a topic yet. Pick one!"
        max_depth = max(self.DEPTH_QUESTIONS[self._current_topic])
        if self._depth >= max_depth:
            return f"We've gone as deep as we can on {self._current_topic}. That was a great conversation!"
        self._depth += 1
        self._asked = []
        return self._ask_question()

    def _ask_question(self) -> str:
        """Pick a question from the current depth level."""
        questions = self.DEPTH_QUESTIONS[self._current_topic][self._depth]
        available = [q for q in questions if q not in self._asked]
        if not available:
            available = questions
        question = random.choice(available)
        self._asked.append(question)
        return question


