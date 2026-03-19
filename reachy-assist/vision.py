"""Photo description via GPT-4o vision — patient holds up a photo,
Reachy captures a frame and describes what it sees.  Great for
reminiscence therapy."""

import base64
import os

import cv2


def capture_frame() -> str | None:
    """Grab the latest camera frame and return it as a base64 JPEG string.
    Returns None if the camera isn't available."""
    try:
        from camera_stream import get_latest_frame
        frame = get_latest_frame()
        if frame is None:
            return None
        _, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return base64.b64encode(jpg.tobytes()).decode("utf-8")
    except Exception as e:
        print(f"[VISION] Frame capture error: {e}")
        return None


def describe_image(base64_image: str, user_prompt: str = "") -> str | None:
    """Send a base64 JPEG to GPT-4o vision and return the description.
    Returns None on failure."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("[VISION] No OPENAI_API_KEY set")
        return None

    prompt = (
        "You are Reachy, a warm companion robot for an elderly person. "
        "They are showing you a photo. Describe what you see in a friendly, "
        "conversational way — like a friend looking at a photo together. "
        "Notice people, places, objects, and emotions. If it looks like a "
        "family photo, mention that warmly. Keep it to 3-5 sentences. "
        "Don't say 'I see an image of' — just describe it naturally."
    )
    if user_prompt:
        prompt += f"\n\nThe patient said: \"{user_prompt}\""

    try:
        import urllib.request
        import json

        body = json.dumps({
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "low",
                            },
                        },
                    ],
                }
            ],
            "max_tokens": 300,
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[VISION] API error: {e}")
        return None


# ── Trigger detection ─────────────────────────────────────────────

_VISION_TRIGGERS = [
    "what do you see", "look at this", "what's in this photo",
    "describe this", "what is this", "can you see this",
    "look at this picture", "tell me about this photo",
    "what's this photo", "who is this", "do you see this",
    "check this out", "what do you think of this",
    "look at this photo", "see this picture",
]


def is_vision_request(text: str) -> bool:
    """Return True if the patient is asking Reachy to look at something."""
    lower = text.lower()
    return any(trigger in lower for trigger in _VISION_TRIGGERS)
