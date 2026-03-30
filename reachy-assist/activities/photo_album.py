"""Photo Album Narrator — Reachy looks at photos and tells stories.

Uses the camera to capture what the patient is showing, sends it to
GPT-4o vision, and cross-references with known patient facts for
personalized commentary.

Usage:
    from activities.photo_album import PhotoAlbumNarrator
    narrator = PhotoAlbumNarrator(patient_facts=["daughter named Sarah", "loves gardening"])
    description = narrator.narrate()  # captures frame + describes
    narrator.start_slideshow()        # continuous narration mode
"""

import time
import threading
from typing import Any, Optional

from core.log_config import get_logger

logger = get_logger("photo_album")

# Trigger phrases for photo narration
PHOTO_TRIGGERS: list[str] = [
    "look at this photo", "tell me about this picture",
    "what do you see in this photo", "describe this photo",
    "who is in this picture", "show me a photo",
    "look at this picture", "narrate this photo",
    "what's in this photo", "photo album", "show you a photo",
    "look at this", "check this out",
]

SLIDESHOW_TRANSITIONS: list[str] = [
    "That's a lovely one. Show me the next photo whenever you're ready.",
    "What a beautiful picture. Got another one to show me?",
    "I enjoyed that one. Ready for the next?",
    "That was really nice. Hold up the next photo when you'd like.",
    "Wonderful. I'm ready for the next one whenever you are.",
]


def is_photo_trigger(text: str) -> bool:
    """Check if the patient wants Reachy to look at a photo."""
    lower = text.lower()
    return any(t in lower for t in PHOTO_TRIGGERS)


class PhotoAlbumNarrator:
    """Narrates photos using camera + GPT-4o vision + patient facts."""

    def __init__(self, patient_facts: Optional[list[str]] = None,
                 patient_name: Optional[str] = None) -> None:
        self.patient_facts = patient_facts or []
        self.patient_name = patient_name
        self._slideshow_active: bool = False
        self._photos_narrated: int = 0
        self._narrations: list[dict] = []  # history of narrated photos

    def set_facts(self, facts: list[str]) -> None:
        """Update known patient facts for personalized narration."""
        self.patient_facts = facts

    def set_name(self, name: str) -> None:
        self.patient_name = name

    def narrate(self, user_prompt: str = "") -> Optional[str]:
        """Capture a frame from the camera and narrate what's in it.
        Returns the narration text or None if camera/API unavailable."""
        try:
            from perception.vision import capture_frame, describe_image
        except ImportError:
            logger.error("vision module not available")
            return None

        frame_b64 = capture_frame()
        if not frame_b64:
            return "I can't see anything right now. Make sure the camera is on and hold the photo up for me."

        # Build a personalized prompt
        prompt = self._build_prompt(user_prompt)
        description = describe_image(frame_b64, prompt)

        if not description:
            return "I had trouble seeing that. Could you hold it a little closer?"

        self._photos_narrated += 1
        self._narrations.append({
            "description": description,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "user_prompt": user_prompt,
        })

        logger.info("Photo narrated (#%d): %s...", self._photos_narrated, description[:60])

        # Save to memory book on dashboard
        self._save_to_memory_book(description)

        return description

    def _build_prompt(self, user_prompt: str) -> str:
        """Build a personalized prompt that includes patient facts."""
        parts = []
        if user_prompt:
            parts.append(f'The patient said: "{user_prompt}"')

        if self.patient_name:
            parts.append(f"The patient's name is {self.patient_name}.")

        if self.patient_facts:
            facts_str = "; ".join(self.patient_facts[:10])
            parts.append(
                f"Things you know about them: {facts_str}. "
                "If you recognize anyone or anything from these facts in the photo, "
                "mention it warmly — like 'Is that your daughter Sarah? She looks so happy!'"
            )

        parts.append(
            "You're looking at a photo together. Describe it warmly and personally. "
            "Ask a follow-up question about the photo to encourage reminiscence."
        )
        return " ".join(parts)

    def _save_to_memory_book(self, description: str) -> None:
        """Save the narrated photo to the dashboard memory book."""
        import os
        import json
        import urllib.request
        dashboard_url = os.environ.get("DASHBOARD_URL", "http://localhost:5555")
        try:
            data = json.dumps({
                "action": "photo_narration",
                "details": description[:500],
            }).encode()
            req = urllib.request.Request(
                f"{dashboard_url}/api/activity",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=3)
        except Exception:
            pass

    def start_slideshow(self) -> str:
        """Enter slideshow mode — patient shows photos one by one."""
        self._slideshow_active = True
        logger.info("Slideshow mode started")
        return (
            "Slideshow mode is on! Hold up a photo whenever you're ready "
            "and I'll tell you what I see. Say 'stop slideshow' when you're done."
        )

    def stop_slideshow(self) -> str:
        """Exit slideshow mode."""
        self._slideshow_active = False
        count = self._photos_narrated
        logger.info("Slideshow ended after %d photos", count)
        return f"That was fun! We looked at {count} photos together. I loved seeing them."

    @property
    def is_slideshow_active(self) -> bool:
        return self._slideshow_active

    def get_status(self) -> dict:
        return {
            "slideshow_active": self._slideshow_active,
            "photos_narrated": self._photos_narrated,
            "recent_narrations": self._narrations[-5:],
        }
