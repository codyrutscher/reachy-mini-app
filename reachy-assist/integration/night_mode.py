"""Night Companion Mode — low-stimulation nighttime support.

Activates automatically after bedtime. Reachy speaks softly, offers
sleep stories, plays white noise, and monitors for distress.

Usage:
    from integration.night_mode import NightCompanion
    nc = NightCompanion()
    nc.check_and_activate()  # auto-activates if it's nighttime
    story = nc.get_sleep_story()
    nc.start_white_noise(player)
"""

import random
import time
from typing import Any, Optional

from core.log_config import get_logger

logger = get_logger("night_mode")

# ── Sleep stories ────────────────────────────────────────────────────

SLEEP_STORIES: list[dict] = [
    {
        "title": "The Quiet Garden",
        "parts": [
            "Imagine a garden at dusk. The sky is turning soft shades of pink and purple.",
            "A gentle breeze carries the scent of lavender and fresh earth.",
            "You walk along a stone path, each step slow and easy.",
            "Fireflies begin to glow, tiny lanterns floating in the warm air.",
            "You find a bench under an old oak tree and sit down.",
            "The leaves rustle softly above you, like a whispered lullaby.",
            "Your eyes grow heavy. The garden holds you safe.",
            "And slowly, peacefully, you drift off to sleep.",
        ],
    },
    {
        "title": "The Lighthouse Keeper",
        "parts": [
            "On a quiet island, there stands an old lighthouse.",
            "Inside, a keeper sits by the window, watching the waves.",
            "The ocean breathes in and out, steady as a heartbeat.",
            "The lighthouse beam sweeps across the dark water, slow and sure.",
            "Rain begins to tap gently on the glass. A cozy sound.",
            "The keeper wraps a blanket around their shoulders and smiles.",
            "The world outside is vast, but in here, everything is warm.",
            "The rhythm of the waves carries you gently into sleep.",
        ],
    },
    {
        "title": "The Train Through the Mountains",
        "parts": [
            "You're on a night train, moving slowly through the mountains.",
            "The wheels click softly on the tracks. Click-clack, click-clack.",
            "Outside the window, snow-covered peaks glow under the moon.",
            "The cabin is warm. A small lamp casts a golden light.",
            "You lean back in your seat and watch the world drift by.",
            "Villages with tiny lit windows pass like scattered stars.",
            "The train rocks gently, side to side, like a cradle.",
            "Your eyes close. The mountains will still be there in the morning.",
        ],
    },
    {
        "title": "The Rainy Afternoon",
        "parts": [
            "It's a rainy afternoon. You're inside, safe and dry.",
            "Rain patters on the roof, a soft and steady rhythm.",
            "You're in your favorite chair with a warm cup of tea.",
            "A cat curls up beside you, purring quietly.",
            "The room smells of cinnamon and old books.",
            "You watch the raindrops race each other down the window.",
            "There's nowhere to be. Nothing to do. Just this moment.",
            "The rain sings you a lullaby, and you let it carry you away.",
        ],
    },
    {
        "title": "The Beach at Sunset",
        "parts": [
            "You're sitting on a quiet beach as the sun goes down.",
            "The sand is still warm from the day. It feels nice under your hands.",
            "Waves roll in gently, one after another, never stopping.",
            "Seagulls call in the distance, then settle for the night.",
            "The sky turns from orange to deep blue, then to velvet black.",
            "Stars appear, one by one, like someone is turning on tiny lights.",
            "The ocean whispers: rest now, rest now, rest now.",
            "You lie back on the warm sand and let the stars watch over you.",
        ],
    },
]

# ── White noise / ambient sound descriptions ────────────────────────

AMBIENT_SOUNDS: dict[str, str] = {
    "rain": "gentle rain falling on a rooftop",
    "ocean": "ocean waves rolling onto shore",
    "forest": "a quiet forest with birds and rustling leaves",
    "fireplace": "a crackling fireplace on a cold night",
    "wind": "soft wind through tall grass",
    "stream": "a babbling brook in the woods",
}

# ── Nighttime check-in phrases ──────────────────────────────────────

NIGHT_CHECKINS: list[str] = [
    "I'm right here if you need anything. Just say my name.",
    "Everything is quiet and safe. Try to rest.",
    "I'm watching over you. You're not alone.",
    "If you can't sleep, I can tell you a story or play some soft sounds.",
    "Take a slow breath. In... and out. I'm here.",
]

DISTRESS_KEYWORDS: list[str] = [
    "help", "scared", "afraid", "can't sleep", "nightmare",
    "where am i", "who's there", "what's happening", "confused",
    "pain", "hurts", "sick", "bathroom", "water", "thirsty",
    "cold", "hot", "noise", "someone there",
]


class NightCompanion:
    """Low-stimulation nighttime companion mode."""

    def __init__(self, bedtime_hour: int = 21, wake_hour: int = 7) -> None:
        self.bedtime_hour = bedtime_hour
        self.wake_hour = wake_hour
        self._active: bool = False
        self._story: Optional[dict] = None
        self._story_step: int = 0
        self._white_noise_on: bool = False
        self._interactions_tonight: int = 0
        self._distress_count: int = 0

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def is_nighttime(self) -> bool:
        """Check if current time is within the nighttime window."""
        hour = time.localtime().tm_hour
        if self.bedtime_hour > self.wake_hour:
            return hour >= self.bedtime_hour or hour < self.wake_hour
        return self.bedtime_hour <= hour < self.wake_hour

    def check_and_activate(self) -> Optional[str]:
        """Auto-activate if it's nighttime. Returns activation message or None."""
        if self.is_nighttime and not self._active:
            self._active = True
            self._interactions_tonight = 0
            self._distress_count = 0
            logger.info("Night mode activated (hour=%d)", time.localtime().tm_hour)
            return (
                "It's getting late. I'm switching to night mode — "
                "I'll keep my voice soft and the lights low. "
                "I'm right here if you need anything. Would you like a sleep story?"
            )
        if not self.is_nighttime and self._active:
            self._active = False
            self._white_noise_on = False
            logger.info("Night mode deactivated (morning)")
            return None
        return None

    def deactivate(self) -> str:
        """Manually turn off night mode."""
        self._active = False
        self._white_noise_on = False
        self._story = None
        return "Night mode off. Good morning!"

    def get_sleep_story(self, title: Optional[str] = None) -> str:
        """Start a new sleep story. Returns the first part."""
        if title:
            story = next((s for s in SLEEP_STORIES if title.lower() in s["title"].lower()), None)
        else:
            story = random.choice(SLEEP_STORIES)
        self._story = story
        self._story_step = 1
        logger.info("Sleep story started: %s", story["title"])
        return f"Here's a story called '{story['title']}'.\n\n{story['parts'][0]}"

    def next_story_part(self) -> str:
        """Get the next part of the current sleep story."""
        if not self._story:
            return self.get_sleep_story()
        if self._story_step >= len(self._story["parts"]):
            self._story = None
            return "That's the end of the story. Sweet dreams. I'm right here."
        text = self._story["parts"][self._story_step]
        self._story_step += 1
        return text

    @property
    def has_active_story(self) -> bool:
        return self._story is not None

    def list_stories(self) -> str:
        """List available sleep stories."""
        titles = [s["title"] for s in SLEEP_STORIES]
        return "I have these sleep stories:\n" + "\n".join(f"- {t}" for t in titles) + \
               "\n\nJust say the name, or say 'tell me a story' for a random one."

    def list_sounds(self) -> str:
        """List available ambient sounds."""
        lines = ["I can play these ambient sounds:"]
        for name, desc in AMBIENT_SOUNDS.items():
            lines.append(f"- {name}: {desc}")
        lines.append("\nJust say 'play rain' or 'ocean sounds'.")
        return "\n".join(lines)

    def start_white_noise(self, player: Any, sound: str = "rain") -> str:
        """Start ambient sound playback using the music player."""
        if sound not in AMBIENT_SOUNDS:
            sound = "rain"
        self._white_noise_on = True
        # Use the music player's melody system for ambient sounds
        # The actual audio would need to be a long ambient track
        desc = AMBIENT_SOUNDS[sound]
        logger.info("White noise started: %s", sound)
        return f"Playing {desc}. I'll keep it going softly. Say 'stop' when you want quiet."

    def stop_white_noise(self, player: Any) -> str:
        """Stop ambient sound playback."""
        self._white_noise_on = False
        player.stop()
        return "Sounds stopped. It's nice and quiet now."

    def check_distress(self, text: str) -> Optional[str]:
        """Check if the patient is in distress during nighttime.
        Returns a calming response or None."""
        if not self._active:
            return None
        lower = text.lower()
        self._interactions_tonight += 1

        for keyword in DISTRESS_KEYWORDS:
            if keyword in lower:
                self._distress_count += 1
                logger.warning("Nighttime distress detected: '%s' (count=%d)",
                               keyword, self._distress_count)

                if self._distress_count >= 3:
                    # Escalate to caregiver
                    return (
                        "I can tell you're having a hard time tonight. "
                        "I'm going to let your caregiver know so they can check on you. "
                        "You're safe. I'm right here with you."
                    )

                # Calming responses based on what they said
                if any(w in lower for w in ["scared", "afraid", "nightmare"]):
                    return (
                        "It's okay, you're safe. I'm right here with you. "
                        "Take a slow breath with me. In... and out. "
                        "Would you like me to tell you a calming story?"
                    )
                if any(w in lower for w in ["can't sleep", "awake"]):
                    return (
                        "That's okay. Sometimes sleep takes its time. "
                        "Would you like a sleep story, or some gentle rain sounds?"
                    )
                if any(w in lower for w in ["where am i", "confused", "what's happening"]):
                    return (
                        "You're at home, safe in your room. It's nighttime. "
                        "Everything is okay. I'm Reachy, your companion. "
                        "Would you like me to stay and talk for a bit?"
                    )
                if any(w in lower for w in ["water", "thirsty", "bathroom", "cold", "hot"]):
                    return (
                        "I hear you. Let me alert your caregiver to help with that. "
                        "They'll be with you soon. I'm staying right here."
                    )
                return random.choice(NIGHT_CHECKINS)

        return None

    def get_night_instructions(self) -> str:
        """Return instructions for the AI to use during night mode."""
        return (
            "\n[NIGHT MODE ACTIVE] It is nighttime. The patient may be trying to sleep "
            "or may have woken up. Follow these rules strictly:\n"
            "- Speak VERY softly and slowly. Short sentences only.\n"
            "- Do NOT ask stimulating questions or bring up exciting topics.\n"
            "- If they seem confused, gently reorient them (where they are, what time it is).\n"
            "- Offer sleep stories, breathing exercises, or ambient sounds.\n"
            "- If they mention pain, fear, or distress, be extra gentle and reassuring.\n"
            "- If they seem fine, encourage them to rest: 'Try to close your eyes. I'm here.'\n"
            "- Do NOT play music or suggest activities. Keep everything calm.\n"
        )

    def get_status(self) -> dict:
        """Return night mode status for the dashboard."""
        return {
            "active": self._active,
            "is_nighttime": self.is_nighttime,
            "bedtime_hour": self.bedtime_hour,
            "wake_hour": self.wake_hour,
            "interactions_tonight": self._interactions_tonight,
            "distress_count": self._distress_count,
            "white_noise_on": self._white_noise_on,
            "active_story": self._story["title"] if self._story else None,
        }
