"""Vision-Aware Buddy — enhanced vision capabilities for Reachy.

Extends the existing vision.py with:
- Object identification and counting
- Text/sign reading (OCR via GPT-4o)
- Room description and scene understanding
- Proactive observations ("I notice you have a new book!")
"""

import logging
import os
import time

logger = logging.getLogger(__name__)


def describe_scene(base64_image: str) -> str | None:
    """Describe the full scene — objects, people, environment."""
    return _vision_query(
        base64_image,
        "Describe what you see in this room/scene. Mention objects, people, "
        "colors, lighting, and the general atmosphere. Be conversational and "
        "warm, like a friend looking around the room with them. 3-5 sentences."
    )


def identify_objects(base64_image: str) -> str | None:
    """Identify and list objects visible in the frame."""
    return _vision_query(
        base64_image,
        "List the main objects you can see in this image. For each object, "
        "briefly describe it (color, size, position). Be conversational. "
        "Format as a natural spoken list, not bullet points."
    )


def read_text(base64_image: str) -> str | None:
    """Read any visible text in the image (signs, books, screens)."""
    return _vision_query(
        base64_image,
        "Look for any text visible in this image — on signs, books, screens, "
        "labels, or papers. Read it out and mention where you see it. "
        "If there's no readable text, say so naturally."
    )


def describe_person(base64_image: str) -> str | None:
    """Describe a person's appearance and apparent mood (no identification)."""
    return _vision_query(
        base64_image,
        "Describe the person or people you see. Mention what they're wearing, "
        "their posture, and what they seem to be doing. Comment on their "
        "apparent mood based on body language. Be warm and respectful. "
        "Do NOT try to identify who they are by name."
    )


def _vision_query(base64_image: str, prompt: str) -> str | None:
    """Send a vision query to GPT-4o."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None
    try:
        import json
        import urllib.request

        body = json.dumps({
            "model": "gpt-4o",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}",
                        "detail": "low",
                    }},
                ],
            }],
            "max_tokens": 300,
        }).encode()

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode())
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error("Vision query failed: %s", e)
        return None


# Additional trigger phrases for the enhanced vision buddy
VISION_BUDDY_TRIGGERS = {
    "scene": [
        "describe the room", "what's around me", "look around",
        "what's in the room", "describe my surroundings",
    ],
    "objects": [
        "what objects", "identify objects", "what things do you see",
        "count the", "how many",
    ],
    "text": [
        "read that", "what does it say", "read the sign",
        "what's written", "read this", "can you read",
    ],
    "person": [
        "how do i look", "describe me", "what am i wearing",
        "do i look okay", "how's my outfit",
    ],
}


def detect_vision_type(text: str) -> str | None:
    """Detect what type of vision request the user is making."""
    lower = text.lower()
    for vtype, triggers in VISION_BUDDY_TRIGGERS.items():
        if any(t in lower for t in triggers):
            return vtype
    return None
