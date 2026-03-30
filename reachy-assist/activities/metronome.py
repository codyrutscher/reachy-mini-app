"""Metronome — Reachy's antennas tick as a visual and auditory metronome.

Uses antenna movements for visual beat and optional audio clicks.
Supports adjustable BPM and time signatures.
"""

import logging
import threading
import time

logger = logging.getLogger(__name__)

# Common tempo presets
TEMPO_PRESETS = {
    "largo": 50,
    "adagio": 70,
    "andante": 90,
    "moderato": 110,
    "allegro": 130,
    "vivace": 155,
    "presto": 180,
}


class Metronome:
    """Visual and auditory metronome using Reachy's antennas."""

    def __init__(self, robot=None):
        self._robot = robot
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()
        self._bpm = 100
        self._beats_per_measure = 4
        self._current_beat = 0
        self._total_beats = 0
        self._speak_fn = None

    def set_speak_fn(self, fn):
        self._speak_fn = fn

    def set_bpm(self, bpm: int) -> str:
        """Set beats per minute (30-240)."""
        bpm = max(30, min(240, bpm))
        self._bpm = bpm
        return f"Tempo set to {bpm} BPM"

    def set_tempo(self, name: str) -> str:
        """Set tempo by name (largo, adagio, andante, etc.)."""
        name = name.lower().strip()
        if name in TEMPO_PRESETS:
            self._bpm = TEMPO_PRESETS[name]
            return f"Tempo set to {name} ({self._bpm} BPM)"
        return f"Unknown tempo. Try: {', '.join(TEMPO_PRESETS.keys())}"

    def set_time_signature(self, beats: int) -> str:
        """Set beats per measure (2-8)."""
        beats = max(2, min(8, beats))
        self._beats_per_measure = beats
        return f"Time signature set to {beats}/4"

    def start(self) -> str:
        """Start the metronome."""
        if self._running:
            return f"Metronome already running at {self._bpm} BPM"
        self._running = True
        self._stop_event.clear()
        self._current_beat = 0
        self._total_beats = 0
        self._thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._thread.start()
        logger.info("Metronome started at %d BPM", self._bpm)
        return f"Metronome started at {self._bpm} BPM, {self._beats_per_measure}/4 time"

    def stop(self) -> str:
        """Stop the metronome."""
        if not self._running:
            return "Metronome is not running"
        self._stop_event.set()
        self._running = False
        # Reset antennas
        if self._robot:
            try:
                self._robot.mini.head.l_antenna.goal_position = 0.0
                self._robot.mini.head.r_antenna.goal_position = 0.0
            except Exception:
                pass
        logger.info("Metronome stopped after %d beats", self._total_beats)
        return f"Metronome stopped ({self._total_beats} beats played)"

    def _tick_loop(self):
        """Main metronome loop — moves antennas on each beat."""
        interval = 60.0 / self._bpm
        try:
            while not self._stop_event.is_set():
                self._current_beat = (self._current_beat % self._beats_per_measure) + 1
                self._total_beats += 1
                is_downbeat = self._current_beat == 1

                # Antenna movement — bigger on downbeat
                if self._robot:
                    try:
                        if is_downbeat:
                            # Strong downbeat — both antennas swing wide
                            self._robot.mini.head.l_antenna.goal_position = -0.7
                            self._robot.mini.head.r_antenna.goal_position = -0.7
                        elif self._current_beat % 2 == 0:
                            # Even beats — left antenna
                            self._robot.mini.head.l_antenna.goal_position = -0.4
                            self._robot.mini.head.r_antenna.goal_position = 0.0
                        else:
                            # Odd beats — right antenna
                            self._robot.mini.head.l_antenna.goal_position = 0.0
                            self._robot.mini.head.r_antenna.goal_position = -0.4
                    except Exception:
                        pass

                # Wait half the interval, then reset antennas
                half = interval / 2
                self._stop_event.wait(half)
                if self._stop_event.is_set():
                    break

                if self._robot:
                    try:
                        self._robot.mini.head.l_antenna.goal_position = 0.0
                        self._robot.mini.head.r_antenna.goal_position = 0.0
                    except Exception:
                        pass

                self._stop_event.wait(half)
        except Exception as e:
            logger.error("Metronome error: %s", e)
        finally:
            self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "bpm": self._bpm,
            "beats_per_measure": self._beats_per_measure,
            "current_beat": self._current_beat,
            "total_beats": self._total_beats,
            "tempo_presets": TEMPO_PRESETS,
        }
