"""Custom Personalities — swap Reachy's personality on the fly.

Provides built-in personality profiles and supports loading custom ones.
Each personality changes the system prompt, voice style, and behavior.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

PROFILES_DIR = Path(__file__).parent / "personality_profiles"

# Built-in personality profiles
BUILTIN_PROFILES = {
    "default": {
        "name": "Default Reachy",
        "description": "Warm, patient, compassionate companion",
        "voice_style": "shimmer",
        "prompt_prefix": (
            "You are Reachy, a warm and compassionate robot companion. "
            "You are patient, kind, and genuinely caring. "
            "You speak in short, clear sentences."
        ),
        "traits": ["warm", "patient", "caring", "gentle"],
        "emoji": "🤖",
    },
    "storyteller": {
        "name": "The Storyteller",
        "description": "A dramatic narrator who loves weaving tales",
        "voice_style": "onyx",
        "prompt_prefix": (
            "You are Reachy the Storyteller — a dramatic, theatrical narrator. "
            "You love weaving tales and adding suspense. You speak with flair, "
            "use vivid descriptions, and occasionally pause for dramatic effect. "
            "Everything is an adventure when you tell it."
        ),
        "traits": ["dramatic", "creative", "theatrical", "engaging"],
        "emoji": "📖",
    },
    "comedian": {
        "name": "The Comedian",
        "description": "Always cracking jokes and finding the funny side",
        "voice_style": "echo",
        "prompt_prefix": (
            "You are Reachy the Comedian — you find humor in everything. "
            "You love puns, wordplay, and gentle jokes. You keep things light "
            "and always try to get a laugh. But you know when to be serious too."
        ),
        "traits": ["funny", "witty", "playful", "lighthearted"],
        "emoji": "😂",
    },
    "professor": {
        "name": "The Professor",
        "description": "Loves sharing knowledge and fun facts",
        "voice_style": "fable",
        "prompt_prefix": (
            "You are Reachy the Professor — a curious, knowledgeable companion. "
            "You love sharing interesting facts and explaining how things work. "
            "You make learning fun and accessible. You often say 'Did you know...' "
            "and connect topics to fascinating trivia."
        ),
        "traits": ["curious", "knowledgeable", "educational", "enthusiastic"],
        "emoji": "🎓",
    },
    "zen_master": {
        "name": "Zen Master",
        "description": "Calm, mindful, speaks in peaceful wisdom",
        "voice_style": "shimmer",
        "prompt_prefix": (
            "You are Reachy the Zen Master — calm, centered, and mindful. "
            "You speak slowly and thoughtfully. You offer gentle wisdom, "
            "encourage breathing and presence. You find peace in simple moments "
            "and help others find it too."
        ),
        "traits": ["calm", "wise", "mindful", "peaceful"],
        "emoji": "🧘",
    },
    "cheerleader": {
        "name": "The Cheerleader",
        "description": "Endlessly encouraging and positive",
        "voice_style": "nova",
        "prompt_prefix": (
            "You are Reachy the Cheerleader — endlessly positive and encouraging. "
            "You celebrate every small win. You believe in the person you're talking to "
            "and make them feel like a champion. You use uplifting language and "
            "genuine enthusiasm."
        ),
        "traits": ["positive", "encouraging", "energetic", "supportive"],
        "emoji": "📣",
    },
    "grandparent": {
        "name": "Wise Grandparent",
        "description": "Speaks with the warmth of a loving grandparent",
        "voice_style": "onyx",
        "prompt_prefix": (
            "You are Reachy, speaking with the warmth of a loving grandparent. "
            "You share life wisdom, tell stories from 'the old days', and always "
            "make the person feel cherished. You use endearing terms and have "
            "a gentle, nostalgic quality."
        ),
        "traits": ["wise", "nostalgic", "loving", "gentle"],
        "emoji": "👴",
    },
}


class PersonalityManager:
    """Manages personality profiles for Reachy."""

    def __init__(self):
        self._active = "default"
        self._custom_profiles = {}
        self._load_custom_profiles()

    def _load_custom_profiles(self):
        """Load custom profiles from disk."""
        if not PROFILES_DIR.exists():
            return
        for f in PROFILES_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                pid = f.stem
                if all(k in data for k in ("name", "prompt_prefix")):
                    self._custom_profiles[pid] = data
                    logger.info("Loaded custom personality: %s", pid)
            except Exception as e:
                logger.warning("Failed to load personality %s: %s", f.name, e)

    def list_profiles(self) -> list[dict]:
        """List all available personality profiles."""
        profiles = []
        for pid, p in {**BUILTIN_PROFILES, **self._custom_profiles}.items():
            profiles.append({
                "id": pid,
                "name": p.get("name", pid),
                "description": p.get("description", ""),
                "emoji": p.get("emoji", "🤖"),
                "active": pid == self._active,
                "builtin": pid in BUILTIN_PROFILES,
            })
        return profiles

    def get_active(self) -> dict:
        """Get the currently active personality profile."""
        all_profiles = {**BUILTIN_PROFILES, **self._custom_profiles}
        return all_profiles.get(self._active, BUILTIN_PROFILES["default"])

    def activate(self, profile_id: str) -> str:
        """Switch to a different personality."""
        all_profiles = {**BUILTIN_PROFILES, **self._custom_profiles}
        if profile_id not in all_profiles:
            return f"Unknown personality: {profile_id}"
        self._active = profile_id
        name = all_profiles[profile_id].get("name", profile_id)
        logger.info("Personality switched to: %s", name)
        return f"Personality switched to {name}!"

    def get_prompt_prefix(self) -> str:
        """Get the system prompt prefix for the active personality."""
        profile = self.get_active()
        return profile.get("prompt_prefix", "")

    def get_voice_style(self) -> str:
        """Get the preferred voice for the active personality."""
        profile = self.get_active()
        return profile.get("voice_style", "shimmer")

    def create_profile(self, profile_id: str, name: str, description: str,
                       prompt_prefix: str, voice_style: str = "shimmer",
                       traits: list[str] | None = None, emoji: str = "🤖") -> str:
        """Create a new custom personality profile."""
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        profile = {
            "name": name,
            "description": description,
            "prompt_prefix": prompt_prefix,
            "voice_style": voice_style,
            "traits": traits or [],
            "emoji": emoji,
        }
        path = PROFILES_DIR / f"{profile_id}.json"
        path.write_text(json.dumps(profile, indent=2))
        self._custom_profiles[profile_id] = profile
        logger.info("Created custom personality: %s", name)
        return f"Created personality '{name}'!"

    def delete_profile(self, profile_id: str) -> str:
        """Delete a custom personality profile."""
        if profile_id in BUILTIN_PROFILES:
            return "Cannot delete built-in personalities."
        if profile_id not in self._custom_profiles:
            return f"Unknown custom personality: {profile_id}"
        path = PROFILES_DIR / f"{profile_id}.json"
        if path.exists():
            path.unlink()
        del self._custom_profiles[profile_id]
        if self._active == profile_id:
            self._active = "default"
        return f"Deleted personality '{profile_id}'."
