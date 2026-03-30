"""Sound Effects Engine — plays sound effects through Reachy's built-in speaker.

Generates WAV files programmatically using numpy (no external files needed).
Sounds are cached after first generation. Can be triggered by voice commands,
conversation events, or game logic.

Usage:
    sfx = SoundEffects(robot)
    sfx.play("ding")
    sfx.play("applause")
    sfx.play("drumroll")
"""

import logging
import os
import struct
import threading
import time
import wave
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

SOUNDS_DIR = Path(__file__).parent / "sounds"


def _ensure_dir():
    SOUNDS_DIR.mkdir(exist_ok=True)


def _write_wav(path: Path, samples: np.ndarray, rate: int = 16000):
    """Write a float32 numpy array to a 16-bit WAV file."""
    pcm = (samples * 32767).astype(np.int16)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm.tobytes())


def _generate_tone(freq: float, duration: float, rate: int = 16000,
                   fade_ms: int = 20) -> np.ndarray:
    """Generate a sine wave tone with fade in/out."""
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    tone = np.sin(2 * np.pi * freq * t).astype(np.float32) * 0.6
    # Fade
    fade_samples = int(rate * fade_ms / 1000)
    if fade_samples > 0 and len(tone) > fade_samples * 2:
        tone[:fade_samples] *= np.linspace(0, 1, fade_samples)
        tone[-fade_samples:] *= np.linspace(1, 0, fade_samples)
    return tone


def _generate_ding() -> np.ndarray:
    """Pleasant ding — correct answer, success."""
    rate = 16000
    t1 = _generate_tone(880, 0.15, rate)
    t2 = _generate_tone(1320, 0.3, rate)
    # Decay on t2
    decay = np.exp(-np.linspace(0, 4, len(t2)))
    t2 *= decay
    silence = np.zeros(int(rate * 0.05), dtype=np.float32)
    return np.concatenate([t1, silence, t2])


def _generate_buzzer() -> np.ndarray:
    """Wrong answer buzzer."""
    rate = 16000
    t = np.linspace(0, 0.4, int(rate * 0.4), endpoint=False)
    buzz = (np.sin(2 * np.pi * 150 * t) * 0.4 +
            np.sin(2 * np.pi * 180 * t) * 0.3).astype(np.float32)
    decay = np.exp(-np.linspace(0, 3, len(buzz)))
    return buzz * decay


def _generate_applause() -> np.ndarray:
    """Simulated applause — filtered noise bursts."""
    rate = 16000
    duration = 1.5
    n = int(rate * duration)
    noise = np.random.randn(n).astype(np.float32) * 0.3
    # Envelope — swell up then fade
    env = np.concatenate([
        np.linspace(0, 1, n // 4),
        np.ones(n // 2),
        np.linspace(1, 0, n - n // 4 - n // 2),
    ])
    return noise * env


def _generate_drumroll() -> np.ndarray:
    """Drumroll — rapid low-frequency bursts building up."""
    rate = 16000
    duration = 1.2
    n = int(rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    # Increasing frequency of bursts
    freq = 8 + t * 20  # 8 Hz to 32 Hz
    bursts = (np.sin(2 * np.pi * freq * t) > 0.3).astype(np.float32)
    noise = np.random.randn(n).astype(np.float32) * 0.15
    drum = (bursts * 0.4 + noise) * np.linspace(0.3, 1.0, n)
    # Final hit
    hit = _generate_tone(100, 0.15, rate) * 0.8
    return np.concatenate([drum, hit])


def _generate_tada() -> np.ndarray:
    """Ta-da! — celebration fanfare."""
    rate = 16000
    notes = [523, 659, 784, 1047]  # C5, E5, G5, C6
    parts = []
    for i, freq in enumerate(notes):
        dur = 0.12 if i < 3 else 0.4
        tone = _generate_tone(freq, dur, rate)
        if i == len(notes) - 1:
            tone *= np.exp(-np.linspace(0, 3, len(tone)))
        parts.append(tone)
        if i < len(notes) - 1:
            parts.append(np.zeros(int(rate * 0.03), dtype=np.float32))
    return np.concatenate(parts)


def _generate_whoops() -> np.ndarray:
    """Whoops/oops — descending slide."""
    rate = 16000
    t = np.linspace(0, 0.4, int(rate * 0.4), endpoint=False)
    freq = 600 - t * 800  # slide down
    tone = np.sin(2 * np.pi * freq * t).astype(np.float32) * 0.5
    tone *= np.exp(-np.linspace(0, 3, len(tone)))
    return tone


def _generate_thinking() -> np.ndarray:
    """Thinking/processing — gentle ascending pips."""
    rate = 16000
    parts = []
    for i in range(4):
        freq = 400 + i * 80
        pip = _generate_tone(freq, 0.08, rate) * 0.3
        parts.append(pip)
        parts.append(np.zeros(int(rate * 0.15), dtype=np.float32))
    return np.concatenate(parts)


def _generate_hello() -> np.ndarray:
    """Friendly hello chime — two ascending notes."""
    rate = 16000
    t1 = _generate_tone(523, 0.15, rate)  # C5
    gap = np.zeros(int(rate * 0.05), dtype=np.float32)
    t2 = _generate_tone(784, 0.25, rate)  # G5
    t2 *= np.exp(-np.linspace(0, 3, len(t2)))
    return np.concatenate([t1, gap, t2])


def _generate_goodbye() -> np.ndarray:
    """Gentle goodbye — descending two notes."""
    rate = 16000
    t1 = _generate_tone(784, 0.15, rate)  # G5
    gap = np.zeros(int(rate * 0.05), dtype=np.float32)
    t2 = _generate_tone(523, 0.3, rate)  # C5
    t2 *= np.exp(-np.linspace(0, 3, len(t2)))
    return np.concatenate([t1, gap, t2])


def _generate_tick() -> np.ndarray:
    """Single tick — for countdowns or metronome."""
    rate = 16000
    return _generate_tone(1000, 0.05, rate) * 0.5


def _generate_levelup() -> np.ndarray:
    """Level up — quick ascending arpeggio."""
    rate = 16000
    notes = [523, 659, 784, 1047, 1319]  # C E G C E
    parts = []
    for freq in notes:
        tone = _generate_tone(freq, 0.07, rate) * 0.5
        parts.append(tone)
    return np.concatenate(parts)


# Sound registry
SOUND_GENERATORS = {
    "ding": _generate_ding,
    "correct": _generate_ding,
    "success": _generate_ding,
    "buzzer": _generate_buzzer,
    "wrong": _generate_buzzer,
    "error": _generate_buzzer,
    "applause": _generate_applause,
    "clap": _generate_applause,
    "drumroll": _generate_drumroll,
    "tada": _generate_tada,
    "celebration": _generate_tada,
    "whoops": _generate_whoops,
    "oops": _generate_whoops,
    "thinking": _generate_thinking,
    "processing": _generate_thinking,
    "hello": _generate_hello,
    "greeting": _generate_hello,
    "goodbye": _generate_goodbye,
    "bye": _generate_goodbye,
    "tick": _generate_tick,
    "levelup": _generate_levelup,
}


class SoundEffects:
    """Plays sound effects through Reachy's speaker or system audio."""

    def __init__(self, robot=None):
        self._robot = robot
        self._cache: dict[str, Path] = {}
        _ensure_dir()
        logger.info("Sound effects engine ready (%d sounds)", len(set(SOUND_GENERATORS.values())))

    def play(self, name: str) -> bool:
        """Play a named sound effect. Returns True if played."""
        name = name.lower().strip()
        if name not in SOUND_GENERATORS:
            logger.warning("Unknown sound: %s", name)
            return False

        path = self._get_or_generate(name)
        if not path:
            return False

        threading.Thread(target=self._play_file, args=(path,), daemon=True).start()
        return True

    def play_file(self, path: str) -> bool:
        """Play an arbitrary WAV file."""
        if not os.path.exists(path):
            return False
        threading.Thread(target=self._play_file, args=(Path(path),), daemon=True).start()
        return True

    def list_sounds(self) -> list[str]:
        """Return list of available sound names."""
        return sorted(set(SOUND_GENERATORS.keys()))

    def _get_or_generate(self, name: str) -> Path | None:
        """Get cached WAV path or generate it."""
        if name in self._cache and self._cache[name].exists():
            return self._cache[name]

        generator = SOUND_GENERATORS.get(name)
        if not generator:
            return None

        # Use canonical name for file (multiple aliases share one file)
        canonical = generator.__name__.replace("_generate_", "")
        path = SOUNDS_DIR / f"{canonical}.wav"

        if not path.exists():
            try:
                samples = generator()
                _write_wav(path, samples)
                logger.debug("Generated sound: %s → %s", name, path)
            except Exception as e:
                logger.error("Failed to generate sound %s: %s", name, e)
                return None

        self._cache[name] = path
        return path

    def _play_file(self, path: Path):
        """Play a WAV file through Reachy's speaker or system audio."""
        # Try Reachy's built-in speaker first
        if (self._robot and not self._robot._sim_mode
                and self._robot.mini and self._robot.mini.media
                and self._robot.mini.media.audio):
            try:
                self._robot.mini.media.audio.play_sound(str(path))
                logger.info("Played sound via Reachy: %s", path.name)
                return
            except Exception as e:
                logger.warning("Reachy play_sound failed: %s", e)

        # Fallback: push audio samples manually
        if (self._robot and not self._robot._sim_mode
                and self._robot.mini and self._robot.mini.media
                and self._robot.mini.media.audio):
            try:
                self._play_via_push(path)
                return
            except Exception as e:
                logger.warning("Reachy push_audio failed: %s", e)

        # Final fallback: system audio
        try:
            import sounddevice as sd
            with wave.open(str(path), "r") as wf:
                rate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())
                pcm = np.frombuffer(frames, dtype=np.int16)
                sd.play(pcm, samplerate=rate, blocking=True)
            logger.info("Played sound via sounddevice: %s", path.name)
        except Exception as e:
            logger.error("All playback methods failed for %s: %s", path.name, e)

    def _play_via_push(self, path: Path):
        """Play WAV by pushing audio samples to Reachy's speaker."""
        audio = self._robot.mini.media.audio
        with wave.open(str(path), "r") as wf:
            rate = wf.getframerate()
            channels = wf.getnchannels()
            frames = wf.readframes(wf.getnframes())

        pcm = np.frombuffer(frames, dtype=np.int16)
        float_data = pcm.astype(np.float32) / 32767.0

        # Convert to stereo if mono (Reachy expects 2 channels)
        if channels == 1:
            float_data = np.column_stack([float_data, float_data])

        # Resample if needed (Reachy expects 16kHz)
        if rate != 16000:
            from scipy.signal import resample
            n_out = int(len(float_data) * 16000 / rate)
            float_data = resample(float_data, n_out)

        # Push in chunks
        chunk_size = 1600  # 100ms at 16kHz
        audio.start_playing()
        for i in range(0, len(float_data), chunk_size):
            chunk = float_data[i:i + chunk_size]
            audio.push_audio_sample(chunk.astype(np.float32))
            time.sleep(chunk_size / 16000 * 0.9)  # slight underrun to avoid gaps
        audio.stop_playing()
        logger.info("Played sound via push: %s", path.name)


# ── Ambient Soundscape Generators ─────────────────────────────────

def _generate_rain(duration: float = 30.0) -> np.ndarray:
    """Gentle rain — filtered noise with random droplet pings."""
    rate = 16000
    n = int(rate * duration)
    # Base rain noise
    noise = np.random.randn(n).astype(np.float32) * 0.08
    # Low-pass effect via rolling average
    kernel = np.ones(80) / 80
    rain = np.convolve(noise, kernel, mode="same").astype(np.float32)
    # Random droplet pings
    for _ in range(int(duration * 3)):
        pos = np.random.randint(0, n - 800)
        freq = np.random.uniform(2000, 4000)
        drop = _generate_tone(freq, 0.04, rate) * np.random.uniform(0.05, 0.15)
        rain[pos:pos + len(drop)] += drop
    return rain


def _generate_ocean(duration: float = 30.0) -> np.ndarray:
    """Ocean waves — slow modulated noise."""
    rate = 16000
    n = int(rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    # Wave envelope — slow sine modulation
    wave_env = (np.sin(2 * np.pi * 0.08 * t) * 0.5 + 0.5) * 0.15
    noise = np.random.randn(n).astype(np.float32)
    # Smooth the noise
    kernel = np.ones(200) / 200
    smooth = np.convolve(noise, kernel, mode="same").astype(np.float32)
    return (smooth * wave_env).astype(np.float32)


def _generate_birds(duration: float = 30.0) -> np.ndarray:
    """Bird songs — random chirps and trills."""
    rate = 16000
    n = int(rate * duration)
    result = np.zeros(n, dtype=np.float32)
    # Random bird chirps
    for _ in range(int(duration * 2)):
        pos = np.random.randint(0, n - rate)
        # Each bird: 2-4 quick notes
        num_notes = np.random.randint(2, 5)
        bird = []
        for _ in range(num_notes):
            freq = np.random.uniform(2000, 5000)
            dur = np.random.uniform(0.05, 0.12)
            note = _generate_tone(freq, dur, rate) * np.random.uniform(0.08, 0.2)
            note *= np.exp(-np.linspace(0, 4, len(note)))
            bird.append(note)
            gap = np.zeros(int(rate * np.random.uniform(0.03, 0.08)), dtype=np.float32)
            bird.append(gap)
        chirp = np.concatenate(bird)
        end = min(pos + len(chirp), n)
        result[pos:end] += chirp[:end - pos]
    return result


def _generate_fireplace(duration: float = 30.0) -> np.ndarray:
    """Crackling fireplace — noise bursts with low rumble."""
    rate = 16000
    n = int(rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    # Low rumble
    rumble = np.sin(2 * np.pi * 40 * t).astype(np.float32) * 0.03
    # Random crackles
    crackle = np.zeros(n, dtype=np.float32)
    for _ in range(int(duration * 8)):
        pos = np.random.randint(0, n - 1600)
        burst_len = np.random.randint(200, 1600)
        burst = np.random.randn(burst_len).astype(np.float32) * np.random.uniform(0.05, 0.15)
        burst *= np.exp(-np.linspace(0, 5, burst_len))
        crackle[pos:pos + burst_len] += burst
    return rumble + crackle


def _generate_wind(duration: float = 30.0) -> np.ndarray:
    """Gentle wind — slowly modulated filtered noise."""
    rate = 16000
    n = int(rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    env = (np.sin(2 * np.pi * 0.05 * t) * 0.3 +
           np.sin(2 * np.pi * 0.13 * t) * 0.2 + 0.5) * 0.1
    noise = np.random.randn(n).astype(np.float32)
    kernel = np.ones(300) / 300
    smooth = np.convolve(noise, kernel, mode="same").astype(np.float32)
    return (smooth * env).astype(np.float32)


def _generate_creek(duration: float = 30.0) -> np.ndarray:
    """Babbling creek — water-like filtered noise with variation."""
    rate = 16000
    n = int(rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    # Flowing water base
    noise = np.random.randn(n).astype(np.float32) * 0.1
    kernel = np.ones(120) / 120
    water = np.convolve(noise, kernel, mode="same").astype(np.float32)
    # Babble modulation
    babble = (np.sin(2 * np.pi * 0.3 * t) * 0.3 +
              np.sin(2 * np.pi * 0.7 * t) * 0.2 + 0.6)
    return (water * babble).astype(np.float32)


def _generate_night(duration: float = 30.0) -> np.ndarray:
    """Night sounds — crickets and gentle wind."""
    rate = 16000
    n = int(rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    # Cricket chirps — high frequency pulsing
    cricket_freq = 4500
    cricket = np.sin(2 * np.pi * cricket_freq * t).astype(np.float32) * 0.04
    # Pulse the crickets
    pulse = (np.sin(2 * np.pi * 8 * t) > 0.3).astype(np.float32)
    cricket *= pulse
    # Gentle wind underneath
    wind = _generate_wind(duration) * 0.4
    return cricket + wind


AMBIENT_GENERATORS = {
    "rain": _generate_rain,
    "ocean": _generate_ocean,
    "waves": _generate_ocean,
    "birds": _generate_birds,
    "birdsong": _generate_birds,
    "fireplace": _generate_fireplace,
    "fire": _generate_fireplace,
    "wind": _generate_wind,
    "creek": _generate_creek,
    "stream": _generate_creek,
    "water": _generate_creek,
    "night": _generate_night,
    "crickets": _generate_night,
}


class AmbientPlayer:
    """Loops ambient soundscapes through Reachy's speaker."""

    def __init__(self, sound_effects: SoundEffects):
        self._sfx = sound_effects
        self._playing = False
        self._current = ""
        self._thread = None
        self._stop_event = threading.Event()

    def play(self, name: str) -> str:
        """Start playing an ambient soundscape on loop."""
        name = name.lower().strip()
        if name not in AMBIENT_GENERATORS:
            available = ", ".join(sorted(set(
                k for k, v in AMBIENT_GENERATORS.items()
                if k == v.__name__.replace("_generate_", "")
            )))
            return f"I don't have that sound. Try: {available}"

        if self._playing:
            self.stop()

        # Generate the WAV if not cached
        generator = AMBIENT_GENERATORS[name]
        canonical = generator.__name__.replace("_generate_", "")
        path = SOUNDS_DIR / f"ambient_{canonical}.wav"
        if not path.exists():
            try:
                samples = generator(duration=30.0)
                _write_wav(path, samples)
            except Exception as e:
                logger.error("Failed to generate ambient %s: %s", name, e)
                return "Sorry, I couldn't create that sound."

        self._current = name
        self._playing = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop_play, args=(path,), daemon=True
        )
        self._thread.start()
        logger.info("Ambient started: %s", name)
        return f"Playing {canonical} sounds. Say 'stop ambient' when you want me to stop."

    def stop(self) -> str:
        """Stop the ambient soundscape."""
        if not self._playing:
            return "No ambient sound is playing."
        self._stop_event.set()
        self._playing = False
        name = self._current
        self._current = ""
        logger.info("Ambient stopped: %s", name)
        return "Ambient sounds stopped."

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def current(self) -> str:
        return self._current

    def _loop_play(self, path: Path):
        """Loop the ambient WAV until stopped."""
        while not self._stop_event.is_set():
            self._sfx._play_file(path)
            # Small gap between loops for seamless feel
            self._stop_event.wait(0.5)


# ── Sound Guessing Game Generators ────────────────────────────────

def _generate_cat() -> np.ndarray:
    rate = 16000
    t = np.linspace(0, 0.6, int(rate * 0.6), endpoint=False)
    freq = 350 + np.sin(2 * np.pi * 3 * t) * 80
    meow = np.sin(2 * np.pi * freq * t).astype(np.float32) * 0.4
    meow *= np.concatenate([np.linspace(0, 1, len(t)//4), np.ones(len(t)//2), np.linspace(1, 0, len(t) - len(t)//4 - len(t)//2)])
    return meow

def _generate_dog() -> np.ndarray:
    rate = 16000
    parts = []
    for _ in range(2):
        t = np.linspace(0, 0.15, int(rate * 0.15), endpoint=False)
        bark = np.sin(2 * np.pi * 400 * t).astype(np.float32) * 0.5
        bark *= np.exp(-np.linspace(0, 6, len(bark)))
        parts.append(bark)
        parts.append(np.zeros(int(rate * 0.1), dtype=np.float32))
    return np.concatenate(parts)

def _generate_bird_call() -> np.ndarray:
    rate = 16000
    parts = []
    for freq in [3000, 3500, 4000, 3200]:
        t = np.linspace(0, 0.08, int(rate * 0.08), endpoint=False)
        note = np.sin(2 * np.pi * freq * t).astype(np.float32) * 0.35
        note *= np.exp(-np.linspace(0, 4, len(note)))
        parts.append(note)
        parts.append(np.zeros(int(rate * 0.06), dtype=np.float32))
    return np.concatenate(parts)

def _generate_cow() -> np.ndarray:
    rate = 16000
    t = np.linspace(0, 1.0, int(rate * 1.0), endpoint=False)
    freq = 120 + np.sin(2 * np.pi * 0.8 * t) * 30
    moo = np.sin(2 * np.pi * freq * t).astype(np.float32) * 0.4
    moo *= np.concatenate([np.linspace(0, 1, len(t)//5), np.ones(len(t)*3//5), np.linspace(1, 0, len(t) - len(t)//5 - len(t)*3//5)])
    return moo

def _generate_piano() -> np.ndarray:
    rate = 16000
    t = np.linspace(0, 0.8, int(rate * 0.8), endpoint=False)
    tone = (np.sin(2 * np.pi * 440 * t) * 0.3 + np.sin(2 * np.pi * 880 * t) * 0.15).astype(np.float32)
    tone *= np.exp(-np.linspace(0, 5, len(tone)))
    return tone

def _generate_drum_hit() -> np.ndarray:
    rate = 16000
    t = np.linspace(0, 0.3, int(rate * 0.3), endpoint=False)
    hit = np.sin(2 * np.pi * 80 * t).astype(np.float32) * 0.5
    noise = np.random.randn(len(t)).astype(np.float32) * 0.2
    drum = (hit + noise) * np.exp(-np.linspace(0, 8, len(t)))
    return drum

def _generate_trumpet() -> np.ndarray:
    rate = 16000
    t = np.linspace(0, 0.6, int(rate * 0.6), endpoint=False)
    tone = (np.sin(2 * np.pi * 523 * t) * 0.25 +
            np.sin(2 * np.pi * 1046 * t) * 0.15 +
            np.sin(2 * np.pi * 1569 * t) * 0.08).astype(np.float32)
    tone *= np.concatenate([np.linspace(0, 1, len(t)//6), np.ones(len(t)*4//6), np.linspace(1, 0, len(t) - len(t)//6 - len(t)*4//6)])
    return tone

def _generate_guitar() -> np.ndarray:
    rate = 16000
    t = np.linspace(0, 1.0, int(rate * 1.0), endpoint=False)
    tone = (np.sin(2 * np.pi * 330 * t) * 0.3 +
            np.sin(2 * np.pi * 660 * t) * 0.15 +
            np.sin(2 * np.pi * 990 * t) * 0.08).astype(np.float32)
    tone *= np.exp(-np.linspace(0, 4, len(tone)))
    return tone

def _generate_thunder() -> np.ndarray:
    rate = 16000
    n = int(rate * 1.5)
    noise = np.random.randn(n).astype(np.float32) * 0.4
    kernel = np.ones(400) / 400
    rumble = np.convolve(noise, kernel, mode="same").astype(np.float32)
    env = np.concatenate([np.linspace(0, 1, n//6), np.ones(n//3), np.linspace(1, 0, n - n//6 - n//3)])
    return rumble * env

def _generate_rain_drop() -> np.ndarray:
    rate = 16000
    parts = []
    for _ in range(6):
        freq = np.random.uniform(2500, 4500)
        drop = _generate_tone(freq, 0.03, rate) * 0.3
        drop *= np.exp(-np.linspace(0, 5, len(drop)))
        parts.append(drop)
        parts.append(np.zeros(int(rate * np.random.uniform(0.05, 0.15)), dtype=np.float32))
    return np.concatenate(parts)

def _generate_clock() -> np.ndarray:
    rate = 16000
    parts = []
    for _ in range(4):
        tick = _generate_tone(800, 0.03, rate) * 0.4
        parts.append(tick)
        parts.append(np.zeros(int(rate * 0.47), dtype=np.float32))
    return np.concatenate(parts)

def _generate_doorbell() -> np.ndarray:
    rate = 16000
    t1 = _generate_tone(659, 0.3, rate) * 0.4
    t1 *= np.exp(-np.linspace(0, 2, len(t1)))
    gap = np.zeros(int(rate * 0.05), dtype=np.float32)
    t2 = _generate_tone(523, 0.4, rate) * 0.4
    t2 *= np.exp(-np.linspace(0, 2, len(t2)))
    return np.concatenate([t1, gap, t2])


# Game sound categories
GAME_SOUNDS = {
    "animals": {
        "cat": (_generate_cat, "a cat meowing"),
        "dog": (_generate_dog, "a dog barking"),
        "bird": (_generate_bird_call, "a bird singing"),
        "cow": (_generate_cow, "a cow mooing"),
    },
    "instruments": {
        "piano": (_generate_piano, "a piano"),
        "drum": (_generate_drum_hit, "a drum"),
        "trumpet": (_generate_trumpet, "a trumpet"),
        "guitar": (_generate_guitar, "a guitar"),
    },
    "nature": {
        "thunder": (_generate_thunder, "thunder"),
        "rain drops": (_generate_rain_drop, "rain drops"),
    },
    "everyday": {
        "clock": (_generate_clock, "a clock ticking"),
        "doorbell": (_generate_doorbell, "a doorbell"),
    },
}


class SoundGuessingGame:
    """Reachy plays a sound, patient guesses what it is."""

    def __init__(self, sound_effects: SoundEffects):
        self._sfx = sound_effects
        self._active = False
        self._current_answer = ""
        self._current_hint = ""
        self._category = ""
        self._score = 0
        self._rounds = 0
        self._used = []
        import random
        self._rng = random

    def start(self, category: str = "") -> str:
        """Start a new guessing game."""
        self._active = True
        self._score = 0
        self._rounds = 0
        self._used = []
        self._category = category.lower() if category else ""
        return self._next_round()

    def _next_round(self) -> str:
        """Pick a random sound and play it."""
        # Build pool
        pool = []
        for cat, sounds in GAME_SOUNDS.items():
            if self._category and self._category not in cat:
                continue
            for name, (gen, desc) in sounds.items():
                if name not in self._used:
                    pool.append((cat, name, gen, desc))

        if not pool:
            return self.end()

        cat, name, gen, desc = self._rng.choice(pool)
        self._used.append(name)
        self._current_answer = name
        self._current_hint = desc
        self._rounds += 1

        # Generate and play the sound
        path = SOUNDS_DIR / f"game_{name}.wav"
        if not path.exists():
            samples = gen()
            _write_wav(path, samples)
        self._sfx.play_file(str(path))

        return f"ROUND {self._rounds}: I just played a sound. Can you guess what it is?"

    def check_answer(self, text: str) -> str:
        """Check if the patient's guess is correct."""
        if not self._active:
            return ""

        lower = text.lower()
        answer = self._current_answer.lower()

        # Check for correct answer (fuzzy match)
        if answer in lower or any(w in lower for w in answer.split()):
            self._score += 1
            result = f"That's right! It was {self._current_hint}! Score: {self._score}/{self._rounds}."
            # Play ding
            self._sfx.play("ding")
            # Next round or end
            if self._rounds >= 8 or not self._has_more():
                return result + " " + self.end()
            return result + " Ready for the next one? " + self._next_round()

        # Wrong — give a hint
        if "hint" in lower or "i don't know" in lower or "no idea" in lower:
            category = ""
            for cat, sounds in GAME_SOUNDS.items():
                if self._current_answer in sounds:
                    category = cat
                    break
            self._sfx.play("thinking")
            return f"Here's a hint: it's in the '{category}' category. Want to hear it again?"

        # Play again request
        if "again" in lower or "replay" in lower or "one more time" in lower:
            path = SOUNDS_DIR / f"game_{self._current_answer}.wav"
            if path.exists():
                self._sfx.play_file(str(path))
            return "Playing it again — listen carefully!"

        # Wrong guess
        self._sfx.play("buzzer")
        return f"Not quite! Try again, or say 'hint' for a clue."

    def give_up(self) -> str:
        """Patient gives up on current round."""
        if not self._active:
            return ""
        answer = self._current_hint
        result = f"It was {answer}!"
        if self._rounds >= 8 or not self._has_more():
            return result + " " + self.end()
        return result + " Let's try another one. " + self._next_round()

    def end(self) -> str:
        """End the game and show final score."""
        self._active = False
        if self._rounds == 0:
            return "Game over!"
        pct = int(self._score / self._rounds * 100)
        self._sfx.play("tada" if pct >= 60 else "goodbye")
        return f"Game over! You got {self._score} out of {self._rounds} ({pct}%). {'Great job!' if pct >= 60 else 'Nice try!'}"

    def _has_more(self) -> bool:
        all_names = []
        for cat, sounds in GAME_SOUNDS.items():
            if self._category and self._category not in cat:
                continue
            all_names.extend(sounds.keys())
        return len([n for n in all_names if n not in self._used]) > 0

    @property
    def is_active(self) -> bool:
        return self._active


# ── Musical Instrument Mode ───────────────────────────────────────

# Musical scale — C major across 2 octaves
MUSICAL_NOTES = {
    "C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23,
    "G4": 392.00, "A4": 440.00, "B4": 493.88,
    "C5": 523.25, "D5": 587.33, "E5": 659.25, "F5": 698.46,
    "G5": 783.99, "A5": 880.00, "B5": 987.77, "C6": 1046.50,
}

# Map antenna positions to notes (left antenna = low notes, right = high notes)
# Position range: -0.8 (up) to 0.8 (down), mapped to scale indices
SCALE = list(MUSICAL_NOTES.items())  # ordered low to high


class MusicalInstrument:
    """Turns Reachy's antennas into a musical instrument.

    Each antenna position maps to a note. Moving antennas plays notes
    through Reachy's speaker. Patient can conduct by voice.
    """

    def __init__(self, robot=None, sound_effects: SoundEffects = None):
        self._robot = robot
        self._sfx = sound_effects
        self._active = False
        self._thread = None
        self._stop_event = threading.Event()
        self._last_left_note = -1
        self._last_right_note = -1
        self._note_cache: dict[str, Path] = {}
        self._melody_playing = False
        _ensure_dir()

    def start(self) -> str:
        if self._active:
            return "Instrument mode is already on!"
        self._active = True
        self._stop_event.clear()
        logger.info("Musical instrument mode started")
        return ("Instrument mode on! My left antenna plays low notes and my right "
                "plays high notes. Say 'play C' or 'play a melody' or tell me "
                "to move my antennas to make music!")

    def stop(self) -> str:
        if not self._active:
            return "Instrument mode isn't on."
        self._active = False
        self._stop_event.set()
        self._melody_playing = False
        # Reset antennas
        if self._robot and not self._robot._sim_mode:
            try:
                self._robot.mini.goto_target(antennas=[0, 0], duration=0.3)
            except Exception:
                pass
        logger.info("Musical instrument mode stopped")
        return "Instrument mode off. That was fun!"

    @property
    def is_active(self) -> bool:
        return self._active

    def play_note(self, note_name: str) -> str:
        """Play a specific note by name (e.g., 'C4', 'G5')."""
        note_name = note_name.upper().strip()
        freq = MUSICAL_NOTES.get(note_name)
        if not freq:
            # Try without octave — default to octave 4
            for key, f in MUSICAL_NOTES.items():
                if key.startswith(note_name):
                    freq = f
                    note_name = key
                    break
        if not freq:
            return f"I don't know that note. Try: {', '.join(list(MUSICAL_NOTES.keys())[:8])}"

        self._play_freq(freq, note_name)

        # Move antenna to match
        idx = list(MUSICAL_NOTES.keys()).index(note_name)
        pos = -0.7 + (idx / (len(MUSICAL_NOTES) - 1)) * 1.4  # map to -0.7..0.7
        if self._robot and not self._robot._sim_mode:
            try:
                self._robot.mini.goto_target(antennas=[pos, -pos], duration=0.15)
            except Exception:
                pass

        return f"Playing {note_name}!"

    def play_melody(self, name: str = "twinkle") -> str:
        """Play a simple melody."""
        melodies = {
            "twinkle": ["C4", "C4", "G4", "G4", "A4", "A4", "G4",
                        "F4", "F4", "E4", "E4", "D4", "D4", "C4"],
            "scale": ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"],
            "happy": ["C4", "E4", "G4", "C5", "G4", "E4", "C4"],
            "lullaby": ["E4", "D4", "C4", "D4", "E4", "E4", "E4",
                        "D4", "D4", "D4", "E4", "G4", "G4"],
        }
        notes = melodies.get(name.lower(), melodies["twinkle"])
        self._melody_playing = True

        def _play():
            for note in notes:
                if not self._active or self._stop_event.is_set():
                    break
                self.play_note(note)
                time.sleep(0.4)
            self._melody_playing = False

        threading.Thread(target=_play, daemon=True).start()
        return f"Playing {name}! Listen..."

    def _play_freq(self, freq: float, name: str):
        """Generate and play a note at the given frequency."""
        cache_key = f"note_{name}"
        path = SOUNDS_DIR / f"{cache_key}.wav"
        if not path.exists():
            samples = _generate_tone(freq, 0.3, 16000)
            samples *= np.exp(-np.linspace(0, 3, len(samples)))  # piano-like decay
            _write_wav(path, samples)
        if self._sfx:
            self._sfx.play_file(str(path))


# ── Doorbell Detection ────────────────────────────────────────────

class DoorbellDetector:
    """Detects doorbell-like sounds from the microphone audio stream.

    Looks for sudden tonal sounds in the 500-2000 Hz range that stand out
    from the background noise level. Uses a simple energy + frequency approach.
    """

    def __init__(self, sample_rate: int = 16000):
        self._rate = sample_rate
        self._bg_energy = 0.01  # running background noise level
        self._cooldown = 0  # seconds until next detection allowed
        self._last_detection = 0.0
        self._enabled = True
        self._min_interval = 30.0  # don't alert more than once per 30 seconds

    def analyze(self, audio_chunk: np.ndarray) -> bool:
        """Analyze an audio chunk for doorbell-like sounds.

        Args:
            audio_chunk: float32 numpy array of audio samples

        Returns:
            True if a doorbell-like sound was detected
        """
        if not self._enabled:
            return False

        # Cooldown check
        now = time.time()
        if now - self._last_detection < self._min_interval:
            return False

        # Compute energy
        energy = float(np.sqrt(np.mean(audio_chunk ** 2)))

        # Update background noise level (slow adaptation)
        self._bg_energy = self._bg_energy * 0.98 + energy * 0.02

        # Need significant energy spike above background
        if energy < self._bg_energy * 4 or energy < 0.05:
            return False

        # Check for tonal content in doorbell frequency range (500-2000 Hz)
        if len(audio_chunk) < 512:
            return False

        fft = np.abs(np.fft.rfft(audio_chunk[:1024]))
        freqs = np.fft.rfftfreq(1024, 1.0 / self._rate)

        # Find peak frequency
        peak_idx = np.argmax(fft)
        peak_freq = freqs[peak_idx]

        # Doorbell range: 500-2000 Hz with strong tonal peak
        if 400 < peak_freq < 2500:
            # Check tonality — peak should be much stronger than average
            avg_energy = np.mean(fft)
            peak_energy = fft[peak_idx]
            if avg_energy > 0 and peak_energy / avg_energy > 5:
                self._last_detection = now
                logger.info("Doorbell detected! freq=%.0f Hz, energy=%.3f", peak_freq, energy)
                return True

        return False

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False


# ── Ambient Noise Monitor ─────────────────────────────────────────

class AmbientNoiseMonitor:
    """Monitors room noise level and auto-adjusts Reachy's voice volume.

    Tracks a rolling average of background noise. If the room gets loud
    (TV, visitors), Reachy speaks louder. If it's very quiet, Reachy
    speaks softer to match.
    """

    def __init__(self):
        self._samples: list[float] = []
        self._max_samples = 200  # ~20 seconds at 10 Hz
        self._baseline = 0.02  # initial baseline
        self._enabled = True
        self._last_adjustment = 0.0
        self._adjust_interval = 10.0  # only adjust every 10 seconds

    def feed(self, audio_chunk: np.ndarray):
        """Feed an audio chunk to update the noise level estimate."""
        if not self._enabled:
            return
        rms = float(np.sqrt(np.mean(audio_chunk ** 2)))
        self._samples.append(rms)
        if len(self._samples) > self._max_samples:
            self._samples = self._samples[-self._max_samples:]

    def get_recommended_volume(self, current_volume: float) -> float | None:
        """Get recommended volume adjustment based on room noise.

        Returns new volume float, or None if no change needed.
        """
        if not self._enabled or len(self._samples) < 30:
            return None

        now = time.time()
        if now - self._last_adjustment < self._adjust_interval:
            return None

        avg_noise = sum(self._samples[-50:]) / len(self._samples[-50:])

        # Thresholds (RMS values)
        # Very quiet room: < 0.01
        # Normal room: 0.01 - 0.05
        # Noisy room: 0.05 - 0.15
        # Very noisy: > 0.15

        if avg_noise > 0.12 and current_volume < 2.0:
            # Room is loud — speak up
            self._last_adjustment = now
            new_vol = min(2.0, current_volume + 0.2)
            logger.info("Room is noisy (%.3f) — raising volume to %.1f", avg_noise, new_vol)
            return new_vol
        elif avg_noise < 0.008 and current_volume > 0.5:
            # Room is very quiet — speak softer
            self._last_adjustment = now
            new_vol = max(0.5, current_volume - 0.15)
            logger.info("Room is quiet (%.3f) — lowering volume to %.1f", avg_noise, new_vol)
            return new_vol
        elif 0.01 < avg_noise < 0.05 and abs(current_volume - 1.0) > 0.3:
            # Room is normal — drift back toward default
            self._last_adjustment = now
            new_vol = current_volume + (1.0 - current_volume) * 0.3
            logger.info("Room is normal (%.3f) — drifting volume to %.1f", avg_noise, new_vol)
            return new_vol

        return None

    def get_noise_level(self) -> str:
        """Get human-readable noise level."""
        if len(self._samples) < 10:
            return "unknown"
        avg = sum(self._samples[-30:]) / len(self._samples[-30:])
        if avg < 0.008:
            return "very quiet"
        elif avg < 0.03:
            return "quiet"
        elif avg < 0.08:
            return "moderate"
        elif avg < 0.15:
            return "noisy"
        else:
            return "very noisy"

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False


# ── Lullaby Player ────────────────────────────────────────────────

def _generate_lullaby_note(freq: float, duration: float, rate: int = 16000) -> np.ndarray:
    """Generate a soft, warm lullaby note with gentle attack and decay."""
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    # Warm tone — fundamental + soft overtone
    tone = (np.sin(2 * np.pi * freq * t) * 0.25 +
            np.sin(2 * np.pi * freq * 2 * t) * 0.05).astype(np.float32)
    # Gentle envelope
    attack = int(rate * 0.08)
    release = int(rate * 0.15)
    env = np.ones(len(t), dtype=np.float32)
    if attack < len(env):
        env[:attack] = np.linspace(0, 1, attack)
    if release < len(env):
        env[-release:] = np.linspace(1, 0, release)
    return tone * env


# Lullaby melodies — (note_name, duration_beats) pairs
LULLABIES = {
    "twinkle": {
        "name": "Twinkle Twinkle Little Star",
        "tempo": 0.5,  # seconds per beat
        "notes": [
            ("C4", 1), ("C4", 1), ("G4", 1), ("G4", 1),
            ("A4", 1), ("A4", 1), ("G4", 2),
            ("F4", 1), ("F4", 1), ("E4", 1), ("E4", 1),
            ("D4", 1), ("D4", 1), ("C4", 2),
        ],
    },
    "brahms": {
        "name": "Brahms' Lullaby",
        "tempo": 0.55,
        "notes": [
            ("E4", 1), ("E4", 1), ("G4", 2),
            ("E4", 1), ("E4", 1), ("G4", 2),
            ("E4", 1), ("G4", 1), ("C5", 2), ("B4", 1), ("A4", 1),
            ("A4", 1), ("G4", 2), ("REST", 1),
            ("D4", 1), ("D4", 1), ("F4", 2),
            ("D4", 1), ("D4", 1), ("F4", 2),
            ("D4", 1), ("F4", 1), ("B4", 2), ("A4", 1), ("G4", 1),
            ("C4", 1), ("E4", 1), ("C4", 2),
        ],
    },
    "rockabye": {
        "name": "Rock-a-bye Baby",
        "tempo": 0.45,
        "notes": [
            ("E4", 1.5), ("D4", 0.5), ("C4", 1),
            ("E4", 1.5), ("D4", 0.5), ("C4", 1),
            ("G4", 1), ("F4", 1), ("E4", 1),
            ("D4", 3),
            ("F4", 1.5), ("E4", 0.5), ("D4", 1),
            ("F4", 1.5), ("E4", 0.5), ("D4", 1),
            ("A4", 1), ("G4", 1), ("F4", 1),
            ("E4", 3),
        ],
    },
    "moonlight": {
        "name": "Moonlight Melody",
        "tempo": 0.6,
        "notes": [
            ("C4", 2), ("E4", 1), ("G4", 2), ("E4", 1),
            ("A4", 2), ("G4", 1), ("E4", 2), ("C4", 1),
            ("D4", 2), ("F4", 1), ("A4", 2), ("G4", 1),
            ("E4", 2), ("C4", 1), ("D4", 2), ("C4", 2),
        ],
    },
}


def _build_lullaby_wav(lullaby_key: str) -> np.ndarray:
    """Build a complete lullaby WAV from note definitions."""
    lullaby = LULLABIES[lullaby_key]
    tempo = lullaby["tempo"]
    rate = 16000
    parts = []

    for note_name, beats in lullaby["notes"]:
        duration = beats * tempo
        if note_name == "REST":
            parts.append(np.zeros(int(rate * duration), dtype=np.float32))
        else:
            freq = MUSICAL_NOTES.get(note_name, 261.63)
            note = _generate_lullaby_note(freq, duration, rate)
            parts.append(note)

    return np.concatenate(parts)


class LullabyPlayer:
    """Plays gentle lullabies through Reachy's speaker with antenna sway."""

    def __init__(self, robot=None, sound_effects: SoundEffects = None):
        self._robot = robot
        self._sfx = sound_effects
        self._playing = False
        self._current = ""
        self._thread = None
        self._stop_event = threading.Event()
        self._loop_count = 0
        _ensure_dir()

    def play(self, name: str = "twinkle", loops: int = 3) -> str:
        """Start playing a lullaby."""
        name = name.lower().strip()
        if name not in LULLABIES:
            available = ", ".join(LULLABIES.keys())
            return f"I don't know that lullaby. Try: {available}"

        if self._playing:
            self.stop()

        lullaby = LULLABIES[name]
        path = SOUNDS_DIR / f"lullaby_{name}.wav"
        if not path.exists():
            samples = _build_lullaby_wav(name)
            _write_wav(path, samples)

        self._current = name
        self._playing = True
        self._loop_count = 0
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._play_loop, args=(path, loops), daemon=True
        )
        self._thread.start()
        logger.info("Lullaby started: %s", lullaby["name"])
        return f"Playing {lullaby['name']}... Sweet dreams."

    def stop(self) -> str:
        if not self._playing:
            return "No lullaby is playing."
        self._stop_event.set()
        self._playing = False
        name = self._current
        self._current = ""
        # Reset antennas
        if self._robot and not self._robot._sim_mode:
            try:
                self._robot.mini.goto_target(antennas=[0, 0], duration=0.5)
            except Exception:
                pass
        logger.info("Lullaby stopped: %s", name)
        return "Lullaby stopped. Sleep well."

    @property
    def is_playing(self) -> bool:
        return self._playing

    def list_lullabies(self) -> list[str]:
        return [f"{k}: {v['name']}" for k, v in LULLABIES.items()]

    def _play_loop(self, path: Path, max_loops: int):
        """Play the lullaby with gentle antenna sway."""
        sway_thread = None
        if self._robot and not self._robot._sim_mode:
            sway_thread = threading.Thread(target=self._antenna_sway, daemon=True)
            sway_thread.start()

        for i in range(max_loops):
            if self._stop_event.is_set():
                break
            self._loop_count = i + 1
            if self._sfx:
                self._sfx._play_file(path)
            # Pause between loops
            self._stop_event.wait(1.5)

        self._playing = False
        self._current = ""

    def _antenna_sway(self):
        """Gentle antenna sway while lullaby plays — like rocking."""
        import math
        t = 0
        while self._playing and not self._stop_event.is_set():
            # Slow, gentle sway
            left = math.sin(t * 0.8) * 0.3
            right = math.sin(t * 0.8 + math.pi) * 0.3  # opposite phase
            try:
                self._robot.mini.goto_target(
                    antennas=[left, right], duration=0.3
                )
            except Exception:
                pass
            t += 0.4
            self._stop_event.wait(0.4)


# ── Sound Memory Game (Simon-style) ──────────────────────────────

# Use distinct, easily distinguishable tones for the memory game
MEMORY_TONES = {
    "red": 440.0,     # A4
    "blue": 329.63,   # E4
    "green": 523.25,  # C5
    "yellow": 659.25, # E5
}

MEMORY_TONE_NAMES = list(MEMORY_TONES.keys())


class SoundMemoryGame:
    """Simon-style sound memory game.

    Reachy plays a sequence of tones. Patient repeats them back by saying
    the color names. Each round adds one more tone to the sequence.
    """

    def __init__(self, sound_effects: SoundEffects):
        self._sfx = sound_effects
        self._active = False
        self._sequence: list[str] = []
        self._player_pos = 0  # where the player is in repeating
        self._round = 0
        self._score = 0
        self._best = 0
        self._waiting_for_input = False
        self._lock = threading.Lock()
        import random
        self._rng = random
        _ensure_dir()
        # Pre-generate tone files
        for color, freq in MEMORY_TONES.items():
            path = SOUNDS_DIR / f"memory_{color}.wav"
            if not path.exists():
                samples = _generate_tone(freq, 0.5, 16000)
                samples *= np.exp(-np.linspace(0, 2, len(samples)))
                _write_wav(path, samples)

    def start(self) -> str:
        """Start a new game."""
        self._active = True
        self._sequence = []
        self._round = 0
        self._score = 0
        self._player_pos = 0
        self._waiting_for_input = False
        return self._next_round()

    def _next_round(self) -> str:
        """Add a tone and play the full sequence."""
        self._round += 1
        new_color = self._rng.choice(MEMORY_TONE_NAMES)
        self._sequence.append(new_color)
        self._player_pos = 0
        self._waiting_for_input = False

        # Play the sequence
        def _play_seq():
            time.sleep(0.5)
            for color in self._sequence:
                if not self._active:
                    return
                path = SOUNDS_DIR / f"memory_{color}.wav"
                self._sfx._play_file(path)
                time.sleep(0.7)
            with self._lock:
                self._waiting_for_input = True

        threading.Thread(target=_play_seq, daemon=True).start()

        colors = ", ".join(self._sequence)
        return (
            f"Round {self._round}! Listen carefully — I'm playing {len(self._sequence)} "
            f"tones. Remember the order and say the colors back to me. "
            f"The colors are: red (low), blue (lower), green (medium), yellow (high)."
        )

    def check_input(self, text: str) -> str:
        """Check the player's color input."""
        if not self._active:
            return ""

        with self._lock:
            if not self._waiting_for_input:
                return "Wait for me to finish playing the sequence first!"

        lower = text.lower()

        # Check for give up
        if any(p in lower for p in ["give up", "i give up", "quit", "stop game"]):
            return self.end()

        # Check for replay request
        if any(p in lower for p in ["play again", "repeat", "one more time", "replay"]):
            self._player_pos = 0
            self._waiting_for_input = False
            def _replay():
                time.sleep(0.3)
                for color in self._sequence:
                    if not self._active:
                        return
                    path = SOUNDS_DIR / f"memory_{color}.wav"
                    self._sfx._play_file(path)
                    time.sleep(0.7)
                with self._lock:
                    self._waiting_for_input = True
            threading.Thread(target=_replay, daemon=True).start()
            return "Playing the sequence again — listen carefully!"

        # Find which color they said
        said_color = None
        for color in MEMORY_TONE_NAMES:
            if color in lower:
                said_color = color
                break

        if not said_color:
            return (
                "Say a color: red, blue, green, or yellow. "
                "Or say 'replay' to hear the sequence again."
            )

        expected = self._sequence[self._player_pos]

        # Play the tone they said so they can hear it
        path = SOUNDS_DIR / f"memory_{said_color}.wav"
        self._sfx.play_file(str(path))

        if said_color == expected:
            self._player_pos += 1
            if self._player_pos >= len(self._sequence):
                # Completed the round!
                self._score += 1
                self._best = max(self._best, self._score)
                self._sfx.play("ding")
                time.sleep(0.3)
                result = f"Correct! You got all {len(self._sequence)} right!"
                # Next round
                next_msg = self._next_round()
                return result + " " + next_msg
            else:
                remaining = len(self._sequence) - self._player_pos
                return f"Correct! {remaining} more to go."
        else:
            # Wrong!
            self._sfx.play("buzzer")
            return (
                f"Oops! That was {said_color} but I was expecting {expected}. "
                f"You made it to round {self._round} with a sequence of "
                f"{len(self._sequence)} tones. " + self.end()
            )

    def end(self) -> str:
        """End the game."""
        self._active = False
        with self._lock:
            self._waiting_for_input = False
        best = self._best
        rounds = self._round
        self._sfx.play("tada" if best >= 3 else "goodbye")
        return (
            f"Game over! You completed {best} rounds. "
            f"{'Impressive memory!' if best >= 5 else 'Great effort!' if best >= 3 else 'Nice try!'}"
        )

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def waiting_for_input(self) -> bool:
        with self._lock:
            return self._waiting_for_input


# ── Rhythm Game ───────────────────────────────────────────────────

class RhythmGame:
    """Reachy taps a beat, patient claps along. Gets progressively harder.

    Reachy plays a rhythm pattern using antenna taps (tick sounds).
    Patient says "done" after clapping along. Difficulty increases each round.
    """

    def __init__(self, robot=None, sound_effects: SoundEffects = None):
        self._robot = robot
        self._sfx = sound_effects
        self._active = False
        self._round = 0
        self._score = 0
        self._pattern: list[float] = []  # intervals in seconds
        self._playing_pattern = False
        import random
        self._rng = random

    def start(self) -> str:
        self._active = True
        self._round = 0
        self._score = 0
        return self._next_round()

    def _next_round(self) -> str:
        self._round += 1
        # Generate pattern — more beats and trickier timing as rounds increase
        num_beats = min(3 + self._round, 10)
        self._pattern = []
        for _ in range(num_beats):
            if self._round <= 2:
                interval = 0.5  # steady beat
            elif self._round <= 4:
                interval = self._rng.choice([0.4, 0.5, 0.6])  # slight variation
            else:
                interval = self._rng.choice([0.3, 0.4, 0.5, 0.7])  # tricky

        self._pattern = [0.5] * num_beats  # simplified — just count beats
        self._playing_pattern = True

        # Play the pattern
        def _play():
            time.sleep(0.5)
            for i in range(num_beats):
                if not self._active:
                    return
                if self._sfx:
                    self._sfx.play("tick")
                # Antenna tap
                if self._robot and not self._robot._sim_mode:
                    try:
                        pos = -0.5 if i % 2 == 0 else 0.5
                        self._robot.mini.goto_target(antennas=[pos, -pos], duration=0.1)
                    except Exception:
                        pass
                interval = 0.5 if self._round <= 2 else self._rng.choice([0.35, 0.45, 0.55])
                time.sleep(interval)
            # Reset antennas
            if self._robot and not self._robot._sim_mode:
                try:
                    self._robot.mini.goto_target(antennas=[0, 0], duration=0.3)
                except Exception:
                    pass
            self._playing_pattern = False

        threading.Thread(target=_play, daemon=True).start()

        return (
            f"Round {self._round}! I'm tapping {num_beats} beats. "
            f"Listen to the rhythm and clap along! Say 'done' when you've got it."
        )

    def player_done(self) -> str:
        """Player says they clapped along."""
        if not self._active:
            return ""
        if self._playing_pattern:
            return "Wait for me to finish the pattern first!"
        self._score += 1
        if self._sfx:
            self._sfx.play("ding")
        if self._round >= 6:
            return f"Amazing rhythm! " + self.end()
        return f"Great job keeping the beat! " + self._next_round()

    def end(self) -> str:
        self._active = False
        if self._sfx:
            self._sfx.play("tada" if self._score >= 3 else "goodbye")
        return (
            f"Rhythm game over! You kept up for {self._score} rounds. "
            f"{'You've got great rhythm!' if self._score >= 4 else 'Nice effort!'}"
        )

    @property
    def is_active(self) -> bool:
        return self._active
