"""Voice cloning for Reachy — speak in a familiar voice using ElevenLabs.

Lets Reachy speak in a family member's voice or any custom voice profile.
Family uploads a 30-second audio sample through the dashboard, and Reachy
can then use that voice for TTS.

Supports:
  - ElevenLabs Instant Voice Cloning (from audio sample)
  - Multiple voice profiles per patient
  - Fallback to OpenAI TTS if ElevenLabs unavailable
  - Voice preview before enabling

Requirements:
    pip install elevenlabs
    Set ELEVENLABS_API_KEY in .env

Usage:
    from integration.voice_clone import VoiceManager
    vm = VoiceManager()
    vm.create_voice("grandma_mary", "/path/to/sample.wav", "Mary's voice")
    audio_bytes = vm.speak("Hello dear!", voice_name="grandma_mary")
"""

import os
import json
import time
import tempfile
import threading
from pathlib import Path
from typing import Any, Optional

from core.log_config import get_logger

logger = get_logger("voice_clone")

# Store voice profiles and audio samples here
VOICES_DIR = Path(__file__).parent / "voice_profiles"
VOICES_DIR.mkdir(exist_ok=True)

# Profile metadata file
PROFILES_FILE = VOICES_DIR / "profiles.json"

# Max sample file size (10 MB)
MAX_SAMPLE_SIZE = 10 * 1024 * 1024

# Supported audio formats for voice samples
SUPPORTED_FORMATS = (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm")


def _load_profiles() -> dict:
    """Load voice profiles from disk."""
    if PROFILES_FILE.exists():
        try:
            return json.loads(PROFILES_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_profiles(profiles: dict) -> None:
    """Save voice profiles to disk."""
    PROFILES_FILE.write_text(json.dumps(profiles, indent=2))


class VoiceManager:
    """Manages voice profiles and TTS using ElevenLabs voice cloning."""

    def __init__(self) -> None:
        self._api_key: str = os.environ.get("ELEVENLABS_API_KEY", "")
        self._available: bool = False
        self._profiles: dict = _load_profiles()
        self._active_voice: Optional[str] = None  # currently selected voice name
        self._lock = threading.Lock()

        if self._api_key:
            try:
                import elevenlabs  # noqa: F401
                self._available = True
                logger.info("ElevenLabs available — voice cloning enabled (%d profiles loaded)",
                            len(self._profiles))
            except ImportError:
                logger.warning("elevenlabs package not installed. pip install elevenlabs")
        else:
            logger.info("No ELEVENLABS_API_KEY set — voice cloning disabled. "
                        "Set it in .env to enable custom voices.")

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def active_voice(self) -> Optional[str]:
        return self._active_voice

    def list_voices(self) -> list[dict]:
        """List all saved voice profiles."""
        result = []
        for name, profile in self._profiles.items():
            result.append({
                "name": name,
                "description": profile.get("description", ""),
                "elevenlabs_voice_id": profile.get("elevenlabs_voice_id", ""),
                "sample_file": profile.get("sample_file", ""),
                "created_at": profile.get("created_at", ""),
                "is_active": name == self._active_voice,
            })
        return result

    def set_active_voice(self, name: Optional[str]) -> bool:
        """Set the active voice profile. Pass None to use default OpenAI voice."""
        if name is None:
            self._active_voice = None
            logger.info("Voice reset to default (OpenAI)")
            return True
        if name not in self._profiles:
            logger.warning("Voice profile '%s' not found", name)
            return False
        self._active_voice = name
        logger.info("Active voice set to: %s", name)
        return True

    def create_voice(self, name: str, sample_path: str,
                     description: str = "") -> dict:
        """Create a new voice profile from an audio sample.

        Args:
            name: Unique name for this voice (e.g. "grandma_mary")
            sample_path: Path to audio file (30s+ recommended)
            description: Human-readable description

        Returns:
            dict with voice info or {"error": "..."} on failure
        """
        if not self._available:
            return {"error": "ElevenLabs not configured. Set ELEVENLABS_API_KEY in .env"}

        if not os.path.exists(sample_path):
            return {"error": f"Sample file not found: {sample_path}"}

        file_size = os.path.getsize(sample_path)
        if file_size > MAX_SAMPLE_SIZE:
            return {"error": f"Sample file too large ({file_size // 1024 // 1024}MB). Max is 10MB."}

        ext = os.path.splitext(sample_path)[1].lower()
        if ext not in SUPPORTED_FORMATS:
            return {"error": f"Unsupported format: {ext}. Use: {', '.join(SUPPORTED_FORMATS)}"}

        # Copy sample to our voices directory
        dest = VOICES_DIR / f"{name}{ext}"
        import shutil
        shutil.copy2(sample_path, dest)

        # Clone voice via ElevenLabs API
        try:
            from elevenlabs.client import ElevenLabs

            client = ElevenLabs(api_key=self._api_key)

            voice = client.clone(
                name=f"reachy_{name}",
                description=description or f"Cloned voice for Reachy: {name}",
                files=[str(dest)],
            )

            voice_id = voice.voice_id
            logger.info("Voice cloned: %s (id=%s)", name, voice_id)

            profile = {
                "elevenlabs_voice_id": voice_id,
                "description": description,
                "sample_file": str(dest),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            self._profiles[name] = profile
            _save_profiles(self._profiles)

            return {"name": name, "voice_id": voice_id, "status": "created"}

        except Exception as e:
            logger.error("Voice cloning failed: %s", e)
            return {"error": str(e)}

    def delete_voice(self, name: str) -> dict:
        """Delete a voice profile."""
        if name not in self._profiles:
            return {"error": f"Voice '{name}' not found"}

        profile = self._profiles[name]

        # Delete from ElevenLabs
        if self._available and profile.get("elevenlabs_voice_id"):
            try:
                from elevenlabs.client import ElevenLabs
                client = ElevenLabs(api_key=self._api_key)
                client.voices.delete(profile["elevenlabs_voice_id"])
                logger.info("Deleted ElevenLabs voice: %s", profile["elevenlabs_voice_id"])
            except Exception as e:
                logger.warning("Failed to delete from ElevenLabs: %s", e)

        # Delete local sample
        sample = profile.get("sample_file", "")
        if sample and os.path.exists(sample):
            os.remove(sample)

        # Remove from profiles
        del self._profiles[name]
        _save_profiles(self._profiles)

        if self._active_voice == name:
            self._active_voice = None

        return {"status": "deleted", "name": name}

    def speak(self, text: str, voice_name: Optional[str] = None) -> Optional[bytes]:
        """Generate speech audio using the specified or active cloned voice.

        Args:
            text: Text to speak
            voice_name: Voice profile name (uses active voice if None)

        Returns:
            WAV audio bytes, or None if failed/unavailable
        """
        if not self._available:
            return None

        name = voice_name or self._active_voice
        if not name or name not in self._profiles:
            return None

        voice_id = self._profiles[name].get("elevenlabs_voice_id")
        if not voice_id:
            return None

        try:
            from elevenlabs.client import ElevenLabs

            client = ElevenLabs(api_key=self._api_key)

            audio = client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )

            # Collect the audio bytes from the generator
            audio_bytes = b"".join(audio)
            logger.info("Generated speech with voice '%s' (%d bytes)", name, len(audio_bytes))
            return audio_bytes

        except Exception as e:
            logger.error("ElevenLabs TTS error: %s", e)
            return None

    def speak_to_file(self, text: str, voice_name: Optional[str] = None) -> Optional[str]:
        """Generate speech and save to a temp file. Returns file path or None."""
        audio_bytes = self.speak(text, voice_name)
        if not audio_bytes:
            return None

        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_bytes)
                return f.name
        except Exception as e:
            logger.error("Failed to write audio file: %s", e)
            return None

    def preview_voice(self, name: str) -> Optional[str]:
        """Generate a short preview of a voice. Returns path to audio file."""
        preview_text = "Hello! This is how I sound. I hope you like my voice."
        return self.speak_to_file(preview_text, voice_name=name)

    def get_status(self) -> dict:
        """Return voice system status for the dashboard."""
        return {
            "available": self._available,
            "has_api_key": bool(self._api_key),
            "profiles_count": len(self._profiles),
            "active_voice": self._active_voice,
            "profiles": self.list_voices(),
        }
