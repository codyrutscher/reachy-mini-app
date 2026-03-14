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
