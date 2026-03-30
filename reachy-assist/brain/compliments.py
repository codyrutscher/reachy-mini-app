"""Compliment Generator — gives genuine, specific compliments based on
what Reachy knows about the patient.

Pulls from known facts, recent conversations, and personality traits
to generate personalized compliments rather than generic ones.
"""

import random
from core.log_config import get_logger

logger = get_logger("compliments")

_GENERIC = [
    "You have such a wonderful way of looking at things.",
    "I always enjoy our conversations. You make them so interesting.",
    "You have a really kind heart. I can tell from how you talk about people.",
    "Your sense of humor always brightens my day.",
    "You're one of the most thoughtful people I know.",
    "I admire how curious you are about the world.",
    "You have such a warm presence. It's lovely talking with you.",
    "Your stories are always so vivid. You paint pictures with words.",
]

_TEMPLATES = {
    "family": [
        "The way you talk about {detail}, I can tell what a loving {role} you are.",
        "Your family is lucky to have someone who cares as much as you do.",
        "{detail} sounds wonderful. You've built such a beautiful family.",
    ],
    "hobbies": [
        "Your passion for {detail} really shines through when you talk about it.",
        "I love how dedicated you are to {detail}. That takes real commitment.",
        "Not everyone has a talent like yours for {detail}.",
    ],
    "career": [
        "Being a {detail} for all those years — that takes real dedication.",
        "The skills you built as a {detail} are really impressive.",
        "Your experience as a {detail} gives you such a unique perspective.",
    ],
    "memories": [
        "You have such vivid memories. That's a real gift.",
        "The way you remember details from years ago is remarkable.",
        "Your memory for the little things is what makes your stories so special.",
    ],
}


def generate_compliment(patient_id: str = "default") -> str:
    """Generate a personalized compliment based on known facts."""
    facts = _get_facts(patient_id)

    if not facts:
        return random.choice(_GENERIC)

    # Try to find a fact that matches a template category
    for category, templates in _TEMPLATES.items():
        matching = [f for f in facts if category in f.get("category", "").lower()]
        if matching:
            fact = random.choice(matching)
            detail = fact.get("fact", "").strip()
            # Extract a short detail for the template
            short = detail[:60].rstrip(".")
            template = random.choice(templates)
            try:
                return template.format(detail=short, role="person")
            except (KeyError, IndexError):
                return template.replace("{detail}", short).replace("{role}", "person")

    # Fallback to generic but warm
    return random.choice(_GENERIC)


def _get_facts(patient_id: str) -> list[dict]:
    """Get known facts about the patient."""
    try:
        from memory import db_supabase as db
        if db.is_available():
            return db.get_facts(patient_id) or []
    except Exception:
        pass
    return []
