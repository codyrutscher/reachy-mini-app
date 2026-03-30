"""Audiobook Reader — Reachy reads stories aloud with expressive movements.

Generates story segments via GPT and reads them through the Realtime API.
Reachy moves expressively to match the story mood — leaning in during
suspense, wiggling during funny parts, drooping during sad moments.

Usage:
    book = AudiobookReader(robot)
    prompt = book.start("fairy tale")  # returns GPT prompt to inject
    prompt = book.next_page()          # continues the story
    prompt = book.stop()               # ends the session
"""

import logging
import random

logger = logging.getLogger(__name__)

GENRES = {
    "fairy tale": {
        "prompt": (
            "Tell a gentle, classic fairy tale suitable for an elderly person. "
            "Use vivid descriptions and a warm, soothing narrative voice. "
            "Break it into short paragraphs. End each section with a natural pause point."
        ),
        "examples": ["a kind woodcutter", "a magical garden", "a wise old owl",
                      "a lost princess", "a friendly dragon"],
    },
    "adventure": {
        "prompt": (
            "Tell a light-hearted adventure story. Nothing scary — think treasure hunts, "
            "sailing voyages, or exploring a mysterious island. Keep it fun and engaging. "
            "Break into short paragraphs with natural pause points."
        ),
        "examples": ["a treasure map", "a sailing ship", "a hidden cave",
                      "a jungle expedition", "a mountain climb"],
    },
    "mystery": {
        "prompt": (
            "Tell a cozy mystery — like a village detective solving a missing pie case. "
            "Nothing dark or violent. Think Agatha Christie meets a friendly village. "
            "Build suspense gently. Break into short paragraphs."
        ),
        "examples": ["a missing necklace", "a secret letter", "a mysterious stranger",
                      "a locked room", "a hidden message"],
    },
    "memory lane": {
        "prompt": (
            "Tell a nostalgic story set in the 1950s or 1960s — a summer day, "
            "a county fair, a first dance, a road trip in a classic car. "
            "Rich in sensory details that evoke warm memories. "
            "Break into short paragraphs."
        ),
        "examples": ["a summer fair", "a first dance", "a road trip",
                      "a neighborhood picnic", "a drive-in movie"],
    },
    "nature": {
        "prompt": (
            "Tell a peaceful nature story — a walk through a forest, watching a sunset, "
            "a day by the ocean, following a butterfly. Slow, descriptive, calming. "
            "Focus on sensory details: sounds, smells, colors. "
            "Break into short paragraphs."
        ),
        "examples": ["a forest walk", "a sunset beach", "a mountain meadow",
                      "a rainy afternoon", "a garden in spring"],
    },
    "funny": {
        "prompt": (
            "Tell a lighthearted, funny story — a bumbling inventor, a talking pet, "
            "a mix-up at a bakery. Keep it clean and silly. The kind of story that "
            "makes you chuckle. Break into short paragraphs."
        ),
        "examples": ["a clumsy chef", "a talking parrot", "a mix-up at the post office",
                      "a dog who thinks he's a cat", "an inventor's mishap"],
    },
}


class AudiobookReader:
    """Reads stories aloud with expressive robot movements."""

    def __init__(self, robot=None, patient_name: str = "friend",
                 patient_facts: list[str] = None):
        self._robot = robot
        self._patient_name = patient_name
        self._patient_facts = patient_facts or []
        self._active = False
        self._genre = ""
        self._page = 0
        self._story_context = ""

    def start(self, genre: str = "fairy tale") -> str:
        """Start reading a story. Returns a GPT prompt to inject."""
        genre = genre.lower().strip()
        if genre not in GENRES:
            # Fuzzy match
            for key in GENRES:
                if genre in key or key in genre:
                    genre = key
                    break
            else:
                genre = "fairy tale"

        self._active = True
        self._genre = genre
        self._page = 1
        self._story_context = ""

        info = GENRES[genre]
        element = random.choice(info["examples"])

        # Build personalized prompt
        personal = ""
        if self._patient_name and self._patient_name != "friend":
            personal = f" The listener's name is {self._patient_name}."
        if self._patient_facts:
            # Pick a fact to weave in
            fact = random.choice(self._patient_facts[-5:])
            personal += f" Try to subtly reference: {fact}"

        prompt = (
            f"(AUDIOBOOK MODE: You are now reading a story aloud. "
            f"Genre: {genre}. {info['prompt']}{personal} "
            f"Start with a story about {element}. "
            f"Read it like a warm storyteller — vary your pace, add emotion. "
            f"After 3-4 paragraphs, pause and ask 'Shall I continue?' "
            f"Use descriptive language. This is page 1.)"
        )

        logger.info("Audiobook started: %s (element: %s)", genre, element)
        return prompt

    def next_page(self) -> str:
        """Continue the story. Returns a GPT prompt to inject."""
        if not self._active:
            return ""
        self._page += 1
        return (
            f"(AUDIOBOOK: Continue the story from where you left off. "
            f"This is page {self._page}. Keep the same warm storytelling voice. "
            f"After 3-4 more paragraphs, pause and ask if they want to continue. "
            f"If the story is reaching a natural end, wrap it up beautifully.)"
        )

    def stop(self) -> str:
        """Stop reading."""
        if not self._active:
            return ""
        self._active = False
        genre = self._genre
        pages = self._page
        self._genre = ""
        self._page = 0
        logger.info("Audiobook stopped after %d pages", pages)
        return (
            f"(AUDIOBOOK ENDED: The patient wants to stop the story. "
            f"Wrap up gracefully in 1-2 sentences: 'And that's where we'll "
            f"leave our story for now. We read {pages} pages together — "
            f"that was lovely.' Don't continue the plot.)"
        )

    @property
    def is_reading(self) -> bool:
        return self._active

    @property
    def current_genre(self) -> str:
        return self._genre

    def list_genres(self) -> list[str]:
        return list(GENRES.keys())

    def get_movement_for_text(self, text: str) -> str | None:
        """Suggest a robot movement based on story text content."""
        lower = text.lower()
        # Map story moods to movements
        if any(w in lower for w in ["laughed", "giggled", "funny", "silly", "chuckled"]):
            return "wiggle"
        if any(w in lower for w in ["sad", "cried", "tears", "lonely", "missed"]):
            return "empathy"
        if any(w in lower for w in ["surprised", "gasped", "suddenly", "unexpected"]):
            return "surprised"
        if any(w in lower for w in ["scared", "dark", "shadow", "creaked", "whispered"]):
            return "worried"
        if any(w in lower for w in ["beautiful", "wonderful", "amazing", "magnificent"]):
            return "celebrate"
        if any(w in lower for w in ["thought", "wondered", "pondered", "hmm"]):
            return "think"
        if any(w in lower for w in ["looked around", "searched", "explored", "wandered"]):
            return "look around"
        if any(w in lower for w in ["nodded", "agreed", "yes"]):
            return "nod"
        if any(w in lower for w in ["bowed", "thanked", "grateful"]):
            return "bow"
        return None
