"""Speech-to-text and text-to-speech utilities with multilingual support."""

import sys
from config import WHISPER_MODEL, SAMPLE_RATE, RECORD_SECONDS

# Supported languages for TTS voice selection
_TTS_VOICES = {
    "en": None,       # default system voice
    "es": "es_ES",    # Spanish
    "fr": "fr_FR",    # French
    "de": "de_DE",    # German
    "it": "it_IT",    # Italian
    "pt": "pt_BR",    # Portuguese
    "zh": "zh_CN",    # Chinese
    "ja": "ja_JP",    # Japanese
    "ko": "ko_KR",    # Korean
}


class SpeechEngine:
    def __init__(self, text_mode: bool = False, language: str = "en", tts_rate: int = 150):
        self.text_mode = text_mode
        self.language = language
        self.tts_rate = tts_rate
        self.stt_model = None
        self.tts_engine = None

        if text_mode:
            print(f"[SPEECH] Running in text mode (language={language})")
            return

        import numpy as np
        import sounddevice as sd
        import whisper
        import pyttsx3

        print("[SPEECH] Loading Whisper model...")
        self.stt_model = whisper.load_model(WHISPER_MODEL)
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty("rate", self.tts_rate)  # Adjusted for profile

        # Try to set language-specific voice
        if language != "en":
            self._set_voice(language)

        print(f"[SPEECH] Ready (language={language})")

    def _set_voice(self, language: str):
        """Try to set a TTS voice matching the language."""
        if not self.tts_engine:
            return
        target = _TTS_VOICES.get(language)
        if not target:
            return
        try:
            voices = self.tts_engine.getProperty("voices")
            for voice in voices:
                if target.lower() in voice.id.lower() or language in voice.id.lower():
                    self.tts_engine.setProperty("voice", voice.id)
                    print(f"[SPEECH] Set voice to: {voice.id}")
                    return
            print(f"[SPEECH] No voice found for {language}, using default")
        except Exception as e:
            print(f"[SPEECH] Could not set voice: {e}")

    def listen(self) -> str:
        """Record audio from microphone and transcribe, or read from stdin."""
        if self.text_mode:
            try:
                text = input("[YOU] > ").strip()
                return text
            except EOFError:
                return ""

        import numpy as np
        import sounddevice as sd
        import subprocess

        # Play a short beep so user knows to start talking
        subprocess.Popen(
            ["afplay", "/System/Library/Sounds/Tink.aiff"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        duration = 8  # seconds — generous window
        print(f"[SPEECH] Listening for {duration}s... (speak now)")

        audio = sd.rec(
            int(SAMPLE_RATE * duration),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
        )
        sd.wait()

        # Trim trailing silence so Whisper doesn't hallucinate
        audio_flat = audio.flatten()
        rms_window = int(SAMPLE_RATE * 0.1)  # 100ms windows
        end = len(audio_flat)
        for i in range(len(audio_flat) - rms_window, 0, -rms_window):
            window_rms = float(np.sqrt(np.mean(audio_flat[i:i+rms_window] ** 2)))
            if window_rms > 0.003:
                end = min(i + rms_window * 3, len(audio_flat))  # keep 300ms after last speech
                break
        audio_flat = audio_flat[:end]

        # Check if there was any speech at all
        peak_rms = float(np.sqrt(np.mean(audio_flat ** 2)))
        if peak_rms < 0.002:
            print("[SPEECH] No speech detected")
            return ""

        print(f"[SPEECH] Processing {len(audio_flat)/SAMPLE_RATE:.1f}s of audio")

        result = self.stt_model.transcribe(
            audio_flat, fp16=False,
            language=self.language if self.language != "en" else None,
        )
        text = result["text"].strip()
        detected_lang = result.get("language", self.language)
        print(f"[SPEECH] Heard ({detected_lang}): '{text}'")
        return text

    def speak(self, text: str):
        """Speak text aloud using TTS, or print to stdout in text mode."""
        # Send to visual simulator if running
        try:
            from robot_sim import send_speech, _running as sim_running
            if sim_running:
                send_speech(text)
        except Exception:
            pass

        if self.text_mode:
            print(f"[REACHY] {text}")
            return

        print(f"[SPEECH] Saying: '{text}'")
        # Use macOS 'say' command — more reliable than pyttsx3
        import subprocess
        # Pick a voice based on language
        voice_map = {
            "en": "Samantha", "es": "Monica", "fr": "Thomas",
            "de": "Anna", "it": "Alice", "pt": "Luciana",
            "zh": "Ting-Ting", "ja": "Kyoko", "ko": "Yuna",
        }
        voice = voice_map.get(self.language, "Samantha")
        # Clean text for shell safety
        clean = text.replace('"', '\\"')
        try:
            subprocess.run(
                ["say", "-v", voice, "-r", str(self.tts_rate), clean],
                timeout=30,
            )
        except Exception as e:
            print(f"[SPEECH] TTS error: {e}")
            # Fallback to pyttsx3
            if self.tts_engine:
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
