"""Speech-to-text and text-to-speech utilities with multilingual support."""

import sys
from core.config import WHISPER_MODEL, SAMPLE_RATE, RECORD_SECONDS
from core.log_config import get_logger

logger = get_logger("speech")

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
        self._use_openai_stt = False
        self._voice_manager = None  # VoiceManager for cloned voices

        # Adaptive silence detection — set before each listen() call
        # "question" = Reachy asked something, wait longer for patient to think
        # "quick"    = short exchange, cut silence faster
        # "default"  = normal 1.8s
        self._silence_hint = "default"

        # Interrupt support — set to True when patient talks over Reachy
        self.interrupted = False
        self._interrupt_audio = None   # numpy array of captured speech during interrupt
        self._current_playback = None  # subprocess.Popen handle for audio
        self._allow_interrupt = True   # keyboard interrupt is always safe

        if text_mode:
            logger.info("Running in text mode (language=%s)", language)
            return

        import os
        import numpy as np
        import sounddevice as sd

        # Prefer OpenAI Whisper API (faster + more accurate) over local model
        if os.environ.get("OPENAI_API_KEY"):
            try:
                from openai import OpenAI
                self._openai_client = OpenAI()
                self._use_openai_stt = True
                logger.info("Using OpenAI Whisper API (cloud, most accurate)")
            except ImportError:
                logger.info("openai package not installed, falling back to local Whisper")

        if not self._use_openai_stt:
            import whisper
            logger.info("Loading local Whisper model (%s)...", WHISPER_MODEL)
            self.stt_model = whisper.load_model(WHISPER_MODEL)

        # TTS engine (fallback)
        try:
            import pyttsx3
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty("rate", self.tts_rate)
        except Exception:
            pass

        # Try to set language-specific voice
        if language != "en":
            self._set_voice(language)

        logger.info("Ready (language=%s)", language)

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
                    logger.info("Set voice to: %s", voice.id)
                    return
            logger.info("No voice found for %s, using default", language)
        except Exception as e:
            logger.warning("Could not set voice: %s", e)

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

        # Voice-activity-based recording — stops when you stop talking
        max_duration = 15       # absolute max seconds
        silence_threshold = 0.01   # RMS below this = silence (raised to reject background noise)
        min_speech = 0.3        # min speech duration before silence-stop kicks in
        chunk_ms = 100          # chunk size in ms
        chunk_size = int(SAMPLE_RATE * chunk_ms / 1000)

        # Adaptive silence timeout based on context hint
        hint = self._silence_hint
        self._silence_hint = "default"  # reset after use
        if hint == "question":
            silence_timeout = 2.5   # patient might be thinking
        elif hint == "quick":
            silence_timeout = 1.3   # fast back-and-forth
        else:
            silence_timeout = 1.8   # normal

        logger.info("Listening (silence=%.1fs, hint=%s)", silence_timeout, hint)

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

        duration = len(audio_flat) / SAMPLE_RATE
        logger.debug("Processing %.1fs of audio", duration)

        # Use OpenAI Whisper API (cloud) for best accuracy + speed
        if self._use_openai_stt:
            text = self._transcribe_openai(audio_flat)
        else:
            result = self.stt_model.transcribe(
                audio_flat, fp16=False,
                language=self.language,
            )
            text = result["text"].strip()

        # Reject hallucinated garbage (Whisper hallucinates on silence/noise)
        if len(text) < 2 or not any(c.isalpha() for c in text):
            return ""

        # Reject common Whisper hallucination phrases (from training data)
        _hallucination_phrases = [
            "thank you for watching", "thanks for watching", "subscribe",
            "like and subscribe", "please subscribe", "see you next time",
            "thank you for listening", "thanks for listening",
            "the end", "music playing", "applause",
            "subtitles by", "translated by", "captions by",
            "you", "bye", "bye bye", "so", "okay",
            "hmm", "uh", "um", "ah",
        ]
        text_lower = text.lower().strip().rstrip(".")
        if text_lower in _hallucination_phrases:
            print(f"[SPEECH] Rejected hallucination: '{text}'")
            return ""

        logger.info("Heard: '%s'", text)
        return text

    def listen_after_interrupt(self) -> str:
        """Continue listening after an interrupt — uses the audio already captured
        during playback as a head start, then keeps recording until silence.
        No beep, no delay — seamless transition from interrupt to listening."""
        if self.text_mode:
            return self.listen()

        import numpy as np
        import sounddevice as sd
        import time as _time

        logger.info("Continuing listen after interrupt (no beep)")

        # Start with whatever the mic captured during playback
        # Ensure all chunks are 1D before concatenating
        pre_chunks = []
        if self._interrupt_audio is not None and len(self._interrupt_audio) > 0:
            flat = self._interrupt_audio.flatten()
            pre_chunks.append(flat)
            pre_duration = len(flat) / SAMPLE_RATE
            print(f"[SPEECH] Using {pre_duration:.1f}s of pre-captured audio")
        self._interrupt_audio = None

        # Continue recording until silence (same logic as listen())
        max_duration = 15
        silence_threshold = 0.01
        min_speech = 0.3
        chunk_ms = 100
        chunk_size = int(SAMPLE_RATE * chunk_ms / 1000)
        silence_timeout = 1.8

        speech_started = True
        silence_start = None
        speech_duration = 0.5

        rec_chunks = []
        stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                                dtype="float32", blocksize=chunk_size)
        stream.start()

        try:
            total = 0
            max_frames = int(SAMPLE_RATE * max_duration)
            while total < max_frames:
                data, _ = stream.read(chunk_size)
                rec_chunks.append(data.flatten())  # always flatten to 1D
                total += len(data)

                rms = float(np.sqrt(np.mean(data ** 2)))
                if rms > silence_threshold:
                    silence_start = None
                    speech_duration += chunk_ms / 1000
                else:
                    if silence_start is None:
                        silence_start = _time.time()
                    elif (_time.time() - silence_start > silence_timeout
                          and speech_duration > min_speech):
                        break
        finally:
            stream.stop()
            stream.close()

        # Combine pre-captured + newly recorded (all 1D)
        all_chunks = pre_chunks + rec_chunks
        if not all_chunks:
            print("[MIC→LISTEN] No audio chunks captured")
            return ""

        audio_flat = np.concatenate(all_chunks)
        peak_rms = float(np.sqrt(np.mean(audio_flat ** 2)))
        duration = len(audio_flat) / SAMPLE_RATE
        print(f"[MIC→LISTEN] Total audio: {duration:.1f}s, peak_rms={peak_rms:.4f}, chunks={len(pre_chunks)}+{len(rec_chunks)}")

        if peak_rms < 0.002:
            print("[MIC→LISTEN] Audio too quiet, discarding")
            return ""

        duration = len(audio_flat) / SAMPLE_RATE
        print(f"[SPEECH] Processing {duration:.1f}s of audio (interrupt)")

        if self._use_openai_stt:
            text = self._transcribe_openai(audio_flat)
        else:
            result = self.stt_model.transcribe(
                audio_flat, fp16=False, language=self.language,
            )
            text = result["text"].strip()

        if len(text) < 2 or not any(c.isalpha() for c in text):
            return ""
        _hallucination_phrases = [
            "thank you for watching", "thanks for watching", "subscribe",
            "like and subscribe", "please subscribe", "see you next time",
            "thank you for listening", "thanks for listening",
            "the end", "music playing", "applause",
            "subtitles by", "translated by", "captions by",
            "you", "bye", "bye bye", "so", "okay",
            "hmm", "uh", "um", "ah",
        ]
        text_lower = text.lower().strip().rstrip(".")
        if text_lower in _hallucination_phrases:
            logger.debug("Rejected hallucination: '%s'", text)
            return ""

        logger.info("Heard (interrupt): '%s'", text)
        return text

    def _transcribe_openai(self, audio_data) -> str:
        """Transcribe audio using OpenAI Whisper API for best accuracy."""
        import tempfile
        import os
        import numpy as np
        import soundfile as sf

        try:
            # Write audio to a temp WAV file (OpenAI API needs a file)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                sf.write(f.name, audio_data, SAMPLE_RATE)
                tmp_path = f.name

            with open(tmp_path, "rb") as audio_file:
                result = self._openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=self.language,
                )
            os.unlink(tmp_path)
            return result.text.strip()
        except Exception as e:
            print(f"[SPEECH] OpenAI STT error: {e}, falling back to local")
            # Fallback to local model if available
            if self.stt_model:
                result = self.stt_model.transcribe(
                    audio_data, fp16=False, language=self.language,
                )
                return result["text"].strip()
            return ""

    def speak(self, text: str):
        """Speak text aloud using TTS, or print to stdout in text mode."""
        # Send to visual simulator if running
        try:
            from robot.robot_sim import send_speech, _running as sim_running
            if sim_running:
                send_speech(text)
        except Exception:
            pass

        if self.text_mode:
            print(f"[REACHY] {text}")
            return

        print(f"[SPEECH] Saying: '{text}'")

        # Try cloned voice first (ElevenLabs)
        if self._speak_cloned(text):
            if not self.interrupted:
                self._post_speak_pause()
            return

        # Try OpenAI TTS (sounds human)
        if self._speak_openai(text):
            if not self.interrupted:
                self._post_speak_pause()
            return

        # Fallback to macOS 'say'
        self._speak_macos(text)
        if not self.interrupted:
            self._post_speak_pause()

    def _post_speak_pause(self):
        """Brief pause after speaking so the mic doesn't pick up echo."""
        import time
        time.sleep(0.3)

    def _speak_cloned(self, text: str) -> bool:
        """Try to speak using a cloned voice via ElevenLabs. Returns True if successful."""
        if not self._voice_manager:
            return False
        if not self._voice_manager.active_voice:
            return False
        try:
            path = self._voice_manager.speak_to_file(text)
            if not path:
                return False
            import soundfile as sf
            audio_data, audio_sr = sf.read(path)
            import os
            os.unlink(path)
            self._play_with_mic_monitor(audio_data, audio_sr)
            return True
        except Exception as e:
            print(f"[SPEECH] Cloned voice error: {e}")
            return False

    def _fetch_tts_audio(self, text: str):
        """Fetch TTS audio from OpenAI and return (audio_data, sample_rate) or None."""
        import os
        if not os.environ.get("OPENAI_API_KEY"):
            return None
        try:
            from openai import OpenAI
            import tempfile
            import soundfile as sf

            client = OpenAI()
            voice = os.environ.get("REACHY_VOICE", "nova")
            resp = client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
                speed=0.95,
                response_format="wav",
            )
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(resp.content)
                tmp_path = f.name
            audio_data, audio_sr = sf.read(tmp_path)
            os.unlink(tmp_path)
            return (audio_data, audio_sr)
        except Exception as e:
            print(f"[SPEECH] OpenAI TTS fetch error: {e}")
            return None

    def _speak_openai(self, text: str) -> bool:
        """Use OpenAI TTS for natural-sounding speech. Returns True if successful.
        Plays audio through sounddevice so we can monitor the mic simultaneously."""
        import os
        if not os.environ.get("OPENAI_API_KEY"):
            return False
        try:
            from openai import OpenAI
            import tempfile
            import soundfile as sf

            client = OpenAI()
            voice = os.environ.get("REACHY_VOICE", "nova")
            resp = client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
                speed=0.95,
                response_format="wav",
            )
            # Decode WAV to numpy array
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(resp.content)
                tmp_path = f.name
            audio_data, audio_sr = sf.read(tmp_path)
            os.unlink(tmp_path)

            # Play through sounddevice with mic monitoring
            self._play_with_mic_monitor(audio_data, audio_sr)
            return True
        except Exception as e:
            print(f"[SPEECH] OpenAI TTS error: {e}")
            return False

    def _play_with_mic_monitor(self, audio_data, audio_sr):
        """Play audio through speaker while monitoring mic for interrupts.
        Uses separate output and input streams so both run simultaneously.

        Interrupt detection: we compare mic RMS during playback against a
        running average. When someone speaks INTO the mic, the RMS jumps
        significantly above the speaker-bleed baseline. We detect this jump
        rather than using an absolute threshold.
        """
        import numpy as np
        import sounddevice as sd
        import threading
        import time as _time

        self.interrupted = False
        self._interrupt_audio = None

        # Track playback position
        play_pos = [0]
        play_done = threading.Event()

        def _output_callback(outdata, frames, time_info, status):
            start = play_pos[0]
            end = start + frames
            if start >= len(audio_data):
                outdata[:] = 0
                play_done.set()
                raise sd.CallbackStop
            chunk = audio_data[start:end]
            if len(chunk) < frames:
                outdata[:len(chunk), 0] = chunk
                outdata[len(chunk):] = 0
                play_done.set()
                raise sd.CallbackStop
            else:
                outdata[:, 0] = chunk
            play_pos[0] = end

        # Rolling RMS tracker — detects sudden jumps above the running average
        # Speaker bleed is relatively constant; human voice causes spikes
        rms_history = []           # rolling window of recent RMS values
        voice_frames = [0]
        mic_chunks = []
        playback_start = [0.0]
        warmup_done = [False]
        log_counter = [0]          # throttle logging to every 5th frame

        # 3 consecutive frames (~300ms) of elevated RMS to trigger interrupt
        interrupt_frames_needed = 3

        def _input_callback(indata, frames, time_info, status):
            if play_done.is_set():
                return
            rms = float(np.sqrt(np.mean(indata ** 2)))
            elapsed = _time.time() - playback_start[0]

            # Skip first 0.3s — let audio output stabilize
            if elapsed < 0.3:
                return

            # Build rolling baseline from recent RMS (last 10 frames = 1s)
            rms_history.append(rms)
            if len(rms_history) > 10:
                rms_history.pop(0)

            # Need at least 3 samples to establish baseline
            if len(rms_history) < 3:
                return

            if not warmup_done[0]:
                warmup_done[0] = True
                avg = sum(rms_history) / len(rms_history)
                print(f"[MIC] Monitor active, avg bleed={avg:.4f}")

            # Baseline = average of rolling window (excludes current spike)
            baseline_samples = rms_history[:-1] if len(rms_history) > 1 else rms_history
            avg_rms = sum(baseline_samples) / len(baseline_samples)

            # Voice detected if RMS is significantly above baseline
            # The jump must be at least 0.04 absolute AND 2x the baseline
            jump = rms - avg_rms
            is_voice = jump > 0.04 and rms > avg_rms * 2.0

            # Log every 5th frame (~500ms) so we can see what's happening
            log_counter[0] += 1
            if log_counter[0] % 5 == 0 or is_voice:
                print(f"[MIC] rms={rms:.4f} avg={avg_rms:.4f} jump={jump:.4f} voice={is_voice} streak={voice_frames[0]}")

            if voice_frames[0] > 0:
                mic_chunks.append(indata.copy().flatten())

            if is_voice:
                voice_frames[0] += 1
                if voice_frames[0] == 1:
                    mic_chunks.append(indata.copy().flatten())
                if voice_frames[0] >= interrupt_frames_needed:
                    print(f"[MIC] INTERRUPT TRIGGERED after {voice_frames[0]} frames")
                    self.interrupted = True
                    play_done.set()
            else:
                voice_frames[0] = max(0, voice_frames[0] - 1)

        try:
            out_stream = sd.OutputStream(
                samplerate=audio_sr, channels=1, dtype="float32",
                callback=_output_callback, blocksize=2400,
            )
            in_stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                callback=_input_callback, blocksize=int(SAMPLE_RATE * 0.1),
            )

            playback_start[0] = _time.time()
            out_stream.start()
            in_stream.start()

            play_done.wait(timeout=30)

            out_stream.stop()
            out_stream.close()
            in_stream.stop()
            in_stream.close()

            if self.interrupted:
                print("[SPEECH] Interrupted by patient")
                if mic_chunks:
                    self._interrupt_audio = np.concatenate(mic_chunks).flatten()
                else:
                    self._interrupt_audio = None

        except Exception as e:
            print(f"[SPEECH] Playback error: {e}, falling back to afplay")
            import subprocess, tempfile
            import soundfile as sf
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                sf.write(f.name, audio_data, audio_sr)
                tmp = f.name
            subprocess.run(["afplay", tmp], timeout=30)
            import os; os.unlink(tmp)

    def _play_audio_interruptible(self, filepath: str, allow_interrupt: bool = True) -> bool:
        """Play an audio file via afplay (fallback for macOS say)."""
        import subprocess

        self.interrupted = False
        proc = subprocess.Popen(
            ["afplay", filepath],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self._current_playback = proc
        proc.wait(timeout=30)
        self._current_playback = None
        return self.interrupted

    def stop_speaking(self):
        """Stop any currently playing audio (called externally for interrupt)."""
        if self._current_playback and self._current_playback.poll() is None:
            self._current_playback.terminate()
            try:
                self._current_playback.wait(timeout=1)
            except Exception:
                pass
            self.interrupted = True
            print("[SPEECH] Interrupted by patient")

    def speak_streamed(self, sentence_gen):
        """Play sentences from a generator with pipelined TTS fetching.

        Three-stage pipeline running in parallel:
        1. GPT generates sentences → text_q
        2. TTS fetches audio for each sentence → audio_q (pre-fetches next while current plays)
        3. Playback plays audio clips back-to-back with ONE continuous mic monitor

        This eliminates the gap between sentences because the next clip's audio
        is already fetched while the current one is playing.

        Returns the full concatenated text."""
        import queue
        import threading
        import numpy as np
        import time as _time

        if self.text_mode:
            full = ""
            for sentence in sentence_gen:
                print(f"[REACHY] {sentence}")
                full += (" " if full else "") + sentence
            return full

        # ── Stage 1: GPT sentence generator → text queue ─────────
        text_q = queue.Queue()
        gen_done = threading.Event()

        def _text_producer():
            try:
                for sentence in sentence_gen:
                    if sentence and sentence.strip():
                        text_q.put(sentence.strip())
            except Exception as e:
                print(f"[SPEECH] Stream producer error: {e}")
            finally:
                gen_done.set()

        threading.Thread(target=_text_producer, daemon=True).start()

        # ── Stage 2: text queue → TTS audio queue (pre-fetch) ────
        # Fetches TTS in background so audio is ready before current clip ends
        _SENTINEL = object()
        audio_q = queue.Queue(maxsize=3)
        tts_done = threading.Event()

        def _tts_producer():
            while True:
                try:
                    text = text_q.get(timeout=0.1)
                except queue.Empty:
                    if gen_done.is_set() and text_q.empty():
                        break
                    continue
                # Fetch TTS audio
                result = self._fetch_tts_audio(text)
                audio_q.put((text, result))  # (sentence_text, (audio_data, sr) or None)
            tts_done.set()
            audio_q.put(_SENTINEL)

        threading.Thread(target=_tts_producer, daemon=True).start()

        # ── Stage 3: Play audio clips with continuous mic monitor ─
        import sounddevice as sd

        self.interrupted = False
        self._interrupt_audio = None
        self._allow_interrupt = True
        full_text = ""

        # Shared mic state across all clips (one continuous monitor)
        # Uses rolling RMS comparison — detects sudden jumps above running average
        voice_frames = [0]
        rms_history = []
        mic_chunks = []
        playback_start = [0.0]
        warmup_done = [False]
        log_counter = [0]
        interrupt_frames_needed = 3
        interrupt_event = threading.Event()

        def _input_callback(indata, frames, time_info, status):
            if interrupt_event.is_set():
                return
            rms = float(np.sqrt(np.mean(indata ** 2)))
            elapsed = _time.time() - playback_start[0]

            # Skip first 0.3s — let audio output stabilize
            if elapsed < 0.3:
                return

            # Build rolling baseline from recent RMS (last 10 frames = 1s)
            rms_history.append(rms)
            if len(rms_history) > 10:
                rms_history.pop(0)

            if len(rms_history) < 3:
                return

            if not warmup_done[0]:
                warmup_done[0] = True
                avg = sum(rms_history) / len(rms_history)
                print(f"[MIC] Stream monitor active, avg bleed={avg:.4f}")

            baseline_samples = rms_history[:-1] if len(rms_history) > 1 else rms_history
            avg_rms = sum(baseline_samples) / len(baseline_samples)

            # Voice = RMS jumps significantly above rolling baseline
            jump = rms - avg_rms
            is_voice = jump > 0.04 and rms > avg_rms * 2.0

            # Log every 5th frame (~500ms) or on voice detection
            log_counter[0] += 1
            if log_counter[0] % 5 == 0 or is_voice:
                print(f"[MIC] rms={rms:.4f} avg={avg_rms:.4f} jump={jump:.4f} voice={is_voice} streak={voice_frames[0]}")

            if voice_frames[0] > 0:
                mic_chunks.append(indata.copy().flatten())

            if is_voice:
                voice_frames[0] += 1
                if voice_frames[0] == 1:
                    mic_chunks.append(indata.copy().flatten())
                if voice_frames[0] >= interrupt_frames_needed:
                    print(f"[MIC] INTERRUPT TRIGGERED after {voice_frames[0]} frames")
                    self.interrupted = True
                    interrupt_event.set()
            else:
                voice_frames[0] = max(0, voice_frames[0] - 1)

        # Start ONE persistent mic input stream for the entire response
        try:
            in_stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                callback=_input_callback, blocksize=int(SAMPLE_RATE * 0.1),
            )
            playback_start[0] = _time.time()
            in_stream.start()
        except Exception as e:
            print(f"[SPEECH] Mic stream error: {e}")
            in_stream = None

        # Play each audio clip back-to-back
        while True:
            try:
                item = audio_q.get(timeout=0.1)
            except queue.Empty:
                if tts_done.is_set() and audio_q.empty():
                    break
                continue

            if item is _SENTINEL:
                break

            sentence_text, audio_result = item
            full_text += (" " if full_text else "") + sentence_text

            # Send to visual simulator
            try:
                from robot.robot_sim import send_speech, _running as sim_running
                if sim_running:
                    send_speech(sentence_text)
            except Exception:
                pass

            print(f"[SPEECH] Saying: '{sentence_text}'")

            if audio_result and not self.interrupted:
                audio_data, audio_sr = audio_result
                # Play this clip through sounddevice (mic already monitoring)
                play_pos = [0]
                clip_done = threading.Event()

                def _make_output_cb(ad, pp, cd):
                    def _output_callback(outdata, frames, time_info, status):
                        start = pp[0]
                        end = start + frames
                        if start >= len(ad):
                            outdata[:] = 0
                            cd.set()
                            raise sd.CallbackStop
                        chunk = ad[start:end]
                        if len(chunk) < frames:
                            outdata[:len(chunk), 0] = chunk
                            outdata[len(chunk):] = 0
                            cd.set()
                            raise sd.CallbackStop
                        else:
                            outdata[:, 0] = chunk
                        pp[0] = end
                    return _output_callback

                try:
                    out_stream = sd.OutputStream(
                        samplerate=audio_sr, channels=1, dtype="float32",
                        callback=_make_output_cb(audio_data, play_pos, clip_done),
                        blocksize=2400,
                    )
                    out_stream.start()

                    # Wait for this clip to finish or interrupt
                    while not clip_done.is_set() and not interrupt_event.is_set():
                        clip_done.wait(timeout=0.05)

                    out_stream.stop()
                    out_stream.close()
                except Exception as e:
                    print(f"[SPEECH] Clip playback error: {e}")

            elif not audio_result and not self.interrupted:
                # TTS fetch failed — fall back to macOS say for this sentence
                self._speak_macos(sentence_text)

            if self.interrupted:
                break

        # Clean up mic stream
        if in_stream:
            try:
                in_stream.stop()
                in_stream.close()
            except Exception:
                pass

        # Save captured interrupt audio
        if self.interrupted:
            print("[SPEECH] Interrupted by patient")
            if mic_chunks:
                self._interrupt_audio = np.concatenate(mic_chunks).flatten()
            else:
                self._interrupt_audio = None

        self._allow_interrupt = False
        if full_text and not self.interrupted:
            self._post_speak_pause()

        return full_text

    def _speak_macos(self, text: str):
        """Fallback: macOS say command (interruptible)."""
        import subprocess
        import tempfile
        import os
        voice_map = {
            "en": "Samantha", "es": "Monica", "fr": "Thomas",
            "de": "Anna", "it": "Alice", "pt": "Luciana",
            "zh": "Ting-Ting", "ja": "Kyoko", "ko": "Yuna",
        }
        voice = voice_map.get(self.language, "Samantha")
        clean = text.replace('"', '\\"')
        try:
            # Write to AIFF file first, then play interruptibly
            with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as f:
                tmp_path = f.name
            subprocess.run(
                ["say", "-v", voice, "-r", str(self.tts_rate), "-o", tmp_path, clean],
                timeout=30,
            )
            self._play_audio_interruptible(tmp_path, allow_interrupt=self._allow_interrupt)
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        except Exception as e:
            print(f"[SPEECH] TTS error: {e}")
            if self.tts_engine:
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
