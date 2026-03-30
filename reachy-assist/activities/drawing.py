"""Collaborative Drawing Prompts — Reachy suggests drawing prompts and encourages.

Themed prompts for fine motor skills and creative expression.
Captures finished drawings via camera and saves to memory book.
"""

import logging
import random
import time

logger = logging.getLogger(__name__)

PROMPTS = {
    "nature": [
        "Draw your favorite flower",
        "Sketch a tree you remember from childhood",
        "Draw what the sky looks like right now",
        "Draw a butterfly with colorful wings",
        "Sketch a mountain landscape",
        "Draw a garden with three different plants",
    ],
    "family": [
        "Draw a portrait of someone you love",
        "Sketch your childhood home",
        "Draw a family dinner scene",
        "Draw your favorite family pet",
        "Sketch a happy memory with a friend",
    ],
    "seasons": [
        "Draw a snowy winter scene",
        "Sketch a spring garden in bloom",
        "Draw a summer beach day",
        "Sketch autumn leaves falling",
    ],
    "memories": [
        "Draw your favorite place to visit",
        "Sketch something that makes you smile",
        "Draw what you had for your favorite meal",
        "Sketch a scene from your favorite holiday",
    ],
    "simple": [
        "Draw a circle and turn it into something",
        "Draw five stars of different sizes",
        "Sketch a cup of tea or coffee",
        "Draw a simple house with a door and windows",
        "Draw a smiley face",
    ],
}

ENCOURAGEMENTS = [
    "That's looking wonderful! Keep going!",
    "I love the way you're doing that!",
    "You have such a creative eye!",
    "Beautiful work! What are you adding next?",
    "That's really coming together nicely!",
    "I can see so much personality in your drawing!",
    "Take your time, there's no rush. It's looking great!",
    "What lovely colors you're using!",
]


class DrawingCoach:
    """Suggests drawing prompts and encourages the patient."""

    def __init__(self, dashboard_url: str = "http://localhost:5555"):
        self._dashboard_url = dashboard_url
        self._current_prompt = ""
        self._current_category = ""
        self._drawings_completed = 0
        self._session_active = False

    def get_prompt(self, category: str = "") -> str:
        """Get a drawing prompt, optionally from a specific category."""
        category = category.lower().strip()
        if category and category in PROMPTS:
            self._current_category = category
        elif not category:
            self._current_category = random.choice(list(PROMPTS.keys()))
        else:
            self._current_category = "simple"

        self._current_prompt = random.choice(PROMPTS[self._current_category])
        self._session_active = True
        return f"🎨 Here's your prompt: {self._current_prompt}"

    def encourage(self) -> str:
        """Give encouragement while drawing."""
        return random.choice(ENCOURAGEMENTS)

    def capture_drawing(self) -> str:
        """Capture the finished drawing via camera and save it."""
        try:
            from perception.vision import capture_frame, describe_image
            frame_b64 = capture_frame()
            if not frame_b64:
                return "I can't see the drawing right now. Hold it up to my camera!"

            description = describe_image(
                frame_b64,
                f"The patient just finished drawing based on the prompt: '{self._current_prompt}'. "
                f"Describe their artwork warmly and specifically."
            )
            self._drawings_completed += 1
            self._session_active = False

            # Save to dashboard activity
            try:
                import json
                import urllib.request
                data = json.dumps({
                    "type": "drawing",
                    "description": description or self._current_prompt,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                }).encode()
                req = urllib.request.Request(
                    f"{self._dashboard_url}/api/activity",
                    data=data,
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass

            return description or "What a lovely drawing! I saved it to your gallery."
        except Exception as e:
            return f"I had trouble capturing that: {e}"

    def list_categories(self) -> str:
        return f"Drawing categories: {', '.join(PROMPTS.keys())}. Pick one or I'll surprise you!"

    @property
    def is_active(self) -> bool:
        return self._session_active

    def get_status(self) -> dict:
        return {
            "active": self._session_active,
            "current_prompt": self._current_prompt,
            "drawings_completed": self._drawings_completed,
            "categories": list(PROMPTS.keys()),
        }
