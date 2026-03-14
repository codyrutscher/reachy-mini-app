"""Music, melodies, and sound effects for Reachy — plays through Mac speakers."""

import math
import os
import struct
import subprocess
import wave

SOUNDS_DIR = os.path.join(os.path.dirname(__file__), "sounds")

# ── Note frequencies ────────────────────────────────────────────────
_NOTES = {
    "C3": 130.81, "D3": 146.83, "E3": 164.81, "F3": 174.61,
    "G3": 196.00, "A3": 220.00, "B3": 246.94,
    "C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23,
    "G4": 392.00, "A4": 440.00, "B4": 493.88,
    "C5": 523.25, "D5": 587.33, "E5": 659.25, "F5": 698.46,
    "G5": 783.99, "A5": 880.00,
    "R": 0,
}

def n(name):
    return _NOTES.get(name, 0)

# ── Melodies (longer, for listening) ────────────────────────────────
MELODIES = {
    "calm": [
        (n("C4"), 1.0, 0.4), (n("E4"), 1.0, 0.4), (n("G4"), 1.5, 0.4),
        (n("R"), 0.3, 0), (n("E4"), 0.8, 0.35), (n("C4"), 1.2, 0.35),
        (n("R"), 0.5, 0),
        (n("F4"), 1.0, 0.4), (n("A4"), 1.0, 0.4), (n("G4"), 2.0, 0.35),
        (n("R"), 0.5, 0),
        (n("E4"), 1.0, 0.3), (n("D4"), 1.0, 0.3), (n("C4"), 2.5, 0.3),
    ],
    "happy": [
        (n("C4"), 0.3, 0.5), (n("E4"), 0.3, 0.5), (n("G4"), 0.3, 0.5),
        (n("C5"), 0.5, 0.5), (n("R"), 0.15, 0),
        (n("G4"), 0.3, 0.5), (n("C5"), 0.5, 0.55), (n("R"), 0.2, 0),
        (n("E4"), 0.3, 0.5), (n("G4"), 0.3, 0.5), (n("C5"), 0.3, 0.5),
        (n("E5"), 0.6, 0.5), (n("D5"), 0.3, 0.45), (n("C5"), 0.8, 0.5),
    ],
    "lullaby": [
        (n("E4"), 0.8, 0.3), (n("D4"), 0.4, 0.3), (n("C4"), 1.0, 0.3),
        (n("R"), 0.3, 0),
        (n("E4"), 0.8, 0.3), (n("D4"), 0.4, 0.3), (n("C4"), 1.0, 0.3),
        (n("R"), 0.3, 0),
        (n("G4"), 0.6, 0.3), (n("F4"), 0.6, 0.3), (n("E4"), 0.6, 0.3),
        (n("D4"), 0.6, 0.3), (n("C4"), 2.0, 0.25),
    ],
    "morning": [
        (n("G4"), 0.4, 0.45), (n("A4"), 0.4, 0.45), (n("B4"), 0.4, 0.45),
        (n("C5"), 0.8, 0.5), (n("R"), 0.2, 0),
        (n("E5"), 0.4, 0.5), (n("D5"), 0.4, 0.5), (n("C5"), 0.8, 0.5),
        (n("R"), 0.3, 0),
        (n("G4"), 0.3, 0.45), (n("C5"), 0.3, 0.5), (n("E5"), 0.5, 0.5),
        (n("G5"), 1.0, 0.45),
    ],
    "celebration": [
        (n("C4"), 0.2, 0.5), (n("C4"), 0.2, 0.5), (n("C4"), 0.2, 0.5),
        (n("E4"), 0.5, 0.55), (n("R"), 0.1, 0),
        (n("D4"), 0.2, 0.5), (n("D4"), 0.2, 0.5), (n("D4"), 0.2, 0.5),
        (n("F4"), 0.5, 0.55), (n("R"), 0.1, 0),
        (n("E4"), 0.3, 0.5), (n("G4"), 0.3, 0.5), (n("C5"), 0.8, 0.6),
    ],
    "thinking": [
        (n("E4"), 0.6, 0.3), (n("R"), 0.3, 0),
        (n("G4"), 0.6, 0.3), (n("R"), 0.3, 0),
        (n("F4"), 0.8, 0.3), (n("E4"), 0.4, 0.3),
        (n("D4"), 1.0, 0.3), (n("R"), 0.5, 0),
        (n("C4"), 0.6, 0.3), (n("E4"), 0.6, 0.3), (n("D4"), 1.5, 0.25),
    ],
    "gentle": [
        (n("C4"), 1.5, 0.25), (n("R"), 0.5, 0),
        (n("E4"), 1.5, 0.25), (n("R"), 0.5, 0),
        (n("G4"), 1.5, 0.25), (n("R"), 0.5, 0),
        (n("E4"), 1.5, 0.2), (n("R"), 0.5, 0), (n("C4"), 2.5, 0.2),
    ],
    "waltz": [
        (n("C4"), 0.5, 0.45), (n("E4"), 0.25, 0.4), (n("E4"), 0.25, 0.4),
        (n("D4"), 0.5, 0.45), (n("F4"), 0.25, 0.4), (n("F4"), 0.25, 0.4),
        (n("E4"), 0.5, 0.45), (n("G4"), 0.25, 0.4), (n("G4"), 0.25, 0.4),
        (n("F4"), 0.5, 0.45), (n("A4"), 0.25, 0.4), (n("A4"), 0.25, 0.4),
        (n("G4"), 0.75, 0.45), (n("R"), 0.25, 0), (n("C5"), 1.0, 0.4),
    ],
    "nostalgic": [
        (n("E4"), 1.0, 0.35), (n("D4"), 0.5, 0.35), (n("C4"), 0.5, 0.35),
        (n("D4"), 1.0, 0.35), (n("R"), 0.3, 0),
        (n("G3"), 0.8, 0.3), (n("C4"), 0.8, 0.35), (n("E4"), 1.2, 0.35),
        (n("R"), 0.3, 0),
        (n("D4"), 0.8, 0.3), (n("C4"), 0.8, 0.3), (n("G3"), 2.0, 0.25),
    ],
    "playful": [
        (n("G4"), 0.2, 0.5), (n("A4"), 0.2, 0.5), (n("G4"), 0.2, 0.5),
        (n("E4"), 0.4, 0.5), (n("R"), 0.1, 0),
        (n("G4"), 0.2, 0.5), (n("A4"), 0.2, 0.5), (n("G4"), 0.2, 0.5),
        (n("E5"), 0.4, 0.5), (n("R"), 0.1, 0),
        (n("D5"), 0.2, 0.5), (n("C5"), 0.2, 0.5), (n("A4"), 0.2, 0.5),
        (n("G4"), 0.6, 0.5),
    ],
    "rain": [
        (n("E5"), 0.3, 0.2), (n("R"), 0.2, 0), (n("D5"), 0.3, 0.2),
        (n("R"), 0.3, 0), (n("C5"), 0.4, 0.2), (n("R"), 0.2, 0),
        (n("B4"), 0.3, 0.2), (n("R"), 0.4, 0), (n("A4"), 0.5, 0.2),
        (n("R"), 0.3, 0), (n("G4"), 0.4, 0.2), (n("R"), 0.2, 0),
        (n("E4"), 0.6, 0.2), (n("R"), 0.5, 0), (n("C4"), 2.0, 0.15),
    ],
    "sunset": [
        (n("G4"), 1.2, 0.3), (n("E4"), 0.8, 0.3), (n("C4"), 1.5, 0.3),
        (n("R"), 0.5, 0),
        (n("A4"), 1.0, 0.3), (n("F4"), 0.8, 0.3), (n("D4"), 1.5, 0.25),
        (n("R"), 0.5, 0),
        (n("G4"), 0.8, 0.25), (n("E4"), 0.8, 0.25), (n("C4"), 3.0, 0.2),
    ],
}

# ── Sound effects (short cues) ──────────────────────────────────────
SOUND_EFFECTS = {
    "reminder_chime": [
        (n("E5"), 0.15, 0.5), (n("G5"), 0.15, 0.5), (n("E5"), 0.15, 0.5),
        (n("R"), 0.05, 0), (n("G5"), 0.3, 0.5),
    ],
    "alert": [
        (n("A4"), 0.2, 0.6), (n("R"), 0.1, 0),
        (n("A4"), 0.2, 0.6), (n("R"), 0.1, 0), (n("A4"), 0.3, 0.6),
    ],
    "success": [
        (n("C4"), 0.15, 0.5), (n("E4"), 0.15, 0.5), (n("G4"), 0.15, 0.5),
        (n("C5"), 0.4, 0.55),
    ],
    "error": [(n("E3"), 0.3, 0.4), (n("R"), 0.05, 0), (n("E3"), 0.5, 0.4)],
    "happy_ding": [(n("C5"), 0.1, 0.45), (n("E5"), 0.1, 0.45), (n("G5"), 0.25, 0.5)],
    "sad_tone": [(n("E4"), 0.4, 0.3), (n("D4"), 0.4, 0.3), (n("C4"), 0.8, 0.25)],
    "surprise_pop": [(n("R"), 0.05, 0), (n("C5"), 0.08, 0.6), (n("G5"), 0.2, 0.5)],
    "thinking_hum": [(n("D4"), 0.5, 0.2), (n("E4"), 0.5, 0.2), (n("D4"), 0.8, 0.15)],
    "comfort_tone": [(n("C4"), 0.6, 0.25), (n("E4"), 0.6, 0.25), (n("G4"), 1.0, 0.2)],
    "game_start": [(n("G4"), 0.15, 0.5), (n("C5"), 0.15, 0.5), (n("E5"), 0.3, 0.55)],
    "game_correct": [(n("E4"), 0.1, 0.5), (n("G4"), 0.1, 0.5), (n("C5"), 0.3, 0.55)],
    "game_wrong": [(n("E3"), 0.2, 0.35), (n("C3"), 0.4, 0.3)],
    "game_over": [
        (n("C5"), 0.2, 0.5), (n("G4"), 0.2, 0.5), (n("E4"), 0.2, 0.5),
        (n("C4"), 0.5, 0.45),
    ],
    "checkin_start": [(n("C4"), 0.2, 0.4), (n("E4"), 0.2, 0.4), (n("G4"), 0.3, 0.45)],
    "checkin_done": [
        (n("G4"), 0.15, 0.45), (n("A4"), 0.15, 0.45), (n("B4"), 0.15, 0.45),
        (n("C5"), 0.4, 0.5),
    ],
    "hello": [
        (n("C4"), 0.15, 0.45), (n("E4"), 0.15, 0.45), (n("G4"), 0.15, 0.45),
        (n("C5"), 0.3, 0.5),
    ],
    "goodbye": [
        (n("C5"), 0.2, 0.4), (n("G4"), 0.2, 0.4), (n("E4"), 0.2, 0.4),
        (n("C4"), 0.6, 0.35),
    ],
    "wake_up": [
        (n("G4"), 0.2, 0.4), (n("A4"), 0.2, 0.4), (n("B4"), 0.2, 0.4),
        (n("C5"), 0.15, 0.45), (n("E5"), 0.3, 0.5),
    ],
    "goodnight": [
        (n("E4"), 0.4, 0.3), (n("D4"), 0.4, 0.3), (n("C4"), 0.4, 0.25),
        (n("G3"), 1.0, 0.2),
    ],
    "breathe_in": [(n("C4"), 2.0, 0.15), (n("E4"), 2.0, 0.18)],
    "breathe_out": [(n("E4"), 2.0, 0.18), (n("C4"), 2.5, 0.12)],
}


class MusicPlayer:
    def __init__(self):
        self._process = None
        self._cache = {}
        os.makedirs(SOUNDS_DIR, exist_ok=True)
        print("[MUSIC] Ready")

    @property
    def is_playing(self):
        if self._process and self._process.poll() is None:
            return True
        return False

    def stop(self):
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self._process = None

    def play_file(self, path):
        if not os.path.exists(path):
            print(f"[MUSIC] File not found: {path}")
            return
        self.stop()
        self._process = subprocess.Popen(
            ["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print(f"[MUSIC] Playing: {os.path.basename(path)}")

    def play_melody(self, name):
        notes = MELODIES.get(name)
        if not notes:
            print(f"[MUSIC] Unknown melody: {name}")
            return
        self._play_notes(f"melody_{name}", notes)

    def play_sound(self, name):
        notes = SOUND_EFFECTS.get(name)
        if not notes:
            print(f"[MUSIC] Unknown sound: {name}")
            return
        self._play_notes(f"sfx_{name}", notes)

    def list_melodies(self):
        return list(MELODIES.keys())

    def list_sounds(self):
        return list(SOUND_EFFECTS.keys())

    def _play_notes(self, cache_key, notes):
        if cache_key not in self._cache:
            path = os.path.join(SOUNDS_DIR, f"{cache_key}.wav")
            if not os.path.exists(path):
                _write_wav(path, notes)
            self._cache[cache_key] = path
        self.play_file(self._cache[cache_key])


def _write_wav(path, notes, sample_rate=44100):
    samples = []
    for freq, dur, vol in notes:
        n_samples = int(sample_rate * dur)
        fade = int(sample_rate * 0.02)
        for i in range(n_samples):
            t = i / sample_rate
            envelope = 1.0
            if i < fade:
                envelope = i / fade
            elif i > n_samples - fade:
                envelope = (n_samples - i) / fade
            if freq > 0:
                val = (
                    math.sin(2 * math.pi * freq * t) * 0.7
                    + math.sin(2 * math.pi * freq * 2 * t) * 0.2
                    + math.sin(2 * math.pi * freq * 3 * t) * 0.1
                )
                samples.append(val * vol * envelope)
            else:
                samples.append(0.0)
    peak = max(abs(s) for s in samples) if samples else 1.0
    if peak > 0:
        samples = [s / peak * 0.8 for s in samples]
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for s in samples:
            wf.writeframes(struct.pack("<h", int(s * 32767)))
    print(f"[MUSIC] Generated: {os.path.basename(path)}")
