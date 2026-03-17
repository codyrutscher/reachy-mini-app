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
        import time as _time
        import subprocess

        # Quick non-blocking beep
        subprocess.Popen(
            ["afplay", "/System/Library/Sounds/Tink.aiff"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        # Voice-activity-based recording — stops when you stop talking
        max_duration = 20       # absolute max seconds
        silence_threshold = 0.008  # RMS below this = silence
        silence_timeout = 2.5   # seconds of silence after speech to auto-stop
        min_speech = 0.4        # min speech duration before silence-stop kicks in
        chunk_ms = 100          # chunk size in ms
        chunk_size = int(SAMPLE_RATE * chunk_ms / 1000)

        chunks = []
        speech_started = False
        silence_start = None
        speech_duration = 0.0

        stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                                dtype="float32", blocksize=chunk_size)
        stream.start()

        try:
            total = 0
            max_frames = int(SAMPLE_RATE * max_duration)
            while total < max_frames:
                data, _ = stream.read(chunk_size)
                chunks.append(data.copy())
                total += len(data)

                rms = float(np.sqrt(np.mean(data ** 2)))
                if rms > silence_threshold:
                    speech_started = True
                    silence_start = None
                    speech_duration += chunk_ms / 1000
                elif speech_started:
                    if silence_start is None:
                        silence_start = _time.time()
                    elif (_time.time() - silence_start > silence_timeout
                          and speech_duration > min_speech):
                        break
        finally:
            stream.stop()
            stream.close()

        if not chunks:
            return ""

        audio_flat = np.concatenate(chunks).flatten()
        peak_rms = float(np.sqrt(np.mean(audio_flat ** 2)))
        if peak_rms < 0.002 or not speech_started:
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

        # Try OpenAI TTS first (sounds human)
        if self._speak_openai(text):
            self._post_speak_pause()
            return

        # Fallback to macOS 'say'
        self._speak_macos(text)
        self._post_speak_pause()

    def _post_speak_pause(self):
        """Brief pause after speaking so the mic doesn't pick up echo."""
        import time
        time.sleep(0.6)

    def _speak_openai(self, text: str) -> bool:
        """Use OpenAI TTS for natural-sounding speech. Returns True if successful."""
        import os
        if not os.environ.get("OPENAI_API_KEY"):
            return False
        try:
            from openai import OpenAI
            import subprocess
            import tempfile

            client = OpenAI()
            # Voices: alloy, echo, fable, nova, onyx, shimmer
            # nova = warm female, onyx = deep male, shimmer = gentle female
            voice = os.environ.get("REACHY_VOICE", "nova")
            resp = client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
                speed=0.95,
            )
            # Write to temp file and play
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(resp.content)
                tmp_path = f.name
            subprocess.run(["afplay", tmp_path], timeout=30)
            os.unlink(tmp_path)
            return True
        except Exception as e:
            print(f"[SPEECH] OpenAI TTS error: {e}")
            return False

    def _speak_macos(self, text: str):
        """Fallback: macOS say command."""
        import subprocess
        voice_map = {
            "en": "Samantha", "es": "Monica", "fr": "Thomas",
            "de": "Anna", "it": "Alice", "pt": "Luciana",
            "zh": "Ting-Ting", "ja": "Kyoko", "ko": "Yuna",
        }
        voice = voice_map.get(self.language, "Samantha")
        clean = text.replace('"', '\\"')
        try:
            subprocess.run(
                ["say", "-v", voice, "-r", str(self.tts_rate), clean],
                timeout=30,
            )
        except Exception as e:
            print(f"[SPEECH] TTS error: {e}")
            if self.tts_engine:
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
