"""Dance & Emote — choreographed dance routines for Reachy.

Queue up complex dance routines where Reachy bobs its head, waves antennas,
and rotates body in sync with music.
"""

import logging
import random
import threading
import time

logger = logging.getLogger(__name__)

# Dance move primitives — each is (description, function_name, duration)
# These map to methods on the Movements class
DANCE_MOVES = {
    "head_bob": {"desc": "Head bob", "dur": 0.8},
    "antenna_wave": {"desc": "Antenna wave", "dur": 0.6},
    "happy_wiggle": {"desc": "Happy wiggle", "dur": 1.2},
    "side_tilt": {"desc": "Side tilt", "dur": 0.7},
    "look_around": {"desc": "Look around", "dur": 1.5},
    "excited_bounce": {"desc": "Excited bounce", "dur": 1.0},
    "silly_wiggle": {"desc": "Silly wiggle", "dur": 1.2},
    "music_sway": {"desc": "Music sway", "dur": 1.5},
}

# Pre-built dance routines
ROUTINES = {
    "disco": {
        "name": "Disco Fever",
        "moves": ["head_bob", "antenna_wave", "happy_wiggle", "side_tilt",
                  "head_bob", "excited_bounce", "antenna_wave", "happy_wiggle"],
        "bpm": 120,
    },
    "slow_dance": {
        "name": "Slow Dance",
        "moves": ["music_sway", "side_tilt", "music_sway", "antenna_wave",
                  "music_sway", "side_tilt"],
        "bpm": 70,
    },
    "robot_dance": {
        "name": "Robot Dance",
        "moves": ["head_bob", "side_tilt", "head_bob", "side_tilt",
                  "antenna_wave", "head_bob", "antenna_wave", "head_bob"],
        "bpm": 100,
    },
    "party": {
        "name": "Party Mode",
        "moves": ["excited_bounce", "happy_wiggle", "silly_wiggle", "look_around",
                  "excited_bounce", "antenna_wave", "happy_wiggle", "silly_wiggle"],
        "bpm": 140,
    },
    "chill": {
        "name": "Chill Vibes",
        "moves": ["music_sway", "antenna_wave", "music_sway", "side_tilt",
                  "music_sway"],
        "bpm": 80,
    },
}


class DanceChoreographer:
    """Manages dance routines for Reachy."""

    def __init__(self, robot=None):
        self._robot = robot
        self._movements = None
        self._dancing = False
        self._thread = None
        self._stop_event = threading.Event()
        self._current_routine = ""
        self._dance_count = 0

        if robot:
            try:
                from robot.movements import Movements
                self._movements = Movements(robot.mini)
            except Exception:
                pass

    def dance(self, routine_name: str = "") -> str:
        """Start a dance routine."""
        if self._dancing:
            return "Already dancing! Say 'stop dancing' first."
        if not self._movements:
            return "No robot connected — can't dance without a body!"

        routine_name = routine_name.strip().lower()
        if routine_name and routine_name in ROUTINES:
            routine = ROUTINES[routine_name]
        elif routine_name:
            # Try to match partial name
            for key, r in ROUTINES.items():
                if routine_name in key or routine_name in r["name"].lower():
                    routine = r
                    routine_name = key
                    break
            else:
                routine = random.choice(list(ROUTINES.values()))
                routine_name = "random"
        else:
            routine = random.choice(list(ROUTINES.values()))
            routine_name = "random"

        self._dancing = True
        self._current_routine = routine["name"]
        self._dance_count += 1
        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._perform_routine, args=(routine,), daemon=True
        )
        self._thread.start()

        logger.info("Dancing: %s", routine["name"])
        return f"Let's dance! Performing: {routine['name']} 💃"

    def stop(self) -> str:
        """Stop dancing."""
        if not self._dancing:
            return "I'm not dancing right now."
        self._stop_event.set()
        self._dancing = False
        if self._movements:
            try:
                self._movements.reset()
            except Exception:
                pass
        return "Dance over! That was fun 🎉"

    def _perform_routine(self, routine: dict):
        """Execute a dance routine — sequence of moves."""
        moves = routine["moves"]
        bpm = routine.get("bpm", 100)
        beat_dur = 60.0 / bpm

        try:
            for move_name in moves:
                if self._stop_event.is_set():
                    break
                self._execute_move(move_name)
                # Wait for the beat
                self._stop_event.wait(beat_dur)

            # Finish with a bow if we completed the routine
            if not self._stop_event.is_set() and self._movements:
                try:
                    self._movements.bow()
                except Exception:
                    pass
        except Exception as e:
            logger.error("Dance routine error: %s", e)
        finally:
            self._dancing = False
            if self._movements:
                try:
                    self._movements.reset()
                except Exception:
                    pass

    def _execute_move(self, move_name: str):
        """Execute a single dance move."""
        if not self._movements:
            return
        try:
            move_map = {
                "head_bob": lambda: self._head_bob(),
                "antenna_wave": lambda: self._antenna_wave(),
                "happy_wiggle": self._movements.happy_wiggle,
                "side_tilt": lambda: self._side_tilt(),
                "look_around": self._movements.look_around,
                "excited_bounce": self._movements.excited_bounce,
                "silly_wiggle": self._movements.silly_wiggle,
                "music_sway": self._movements.music_sway,
            }
            fn = move_map.get(move_name)
            if fn:
                fn()
        except Exception as e:
            logger.debug("Move %s failed: %s", move_name, e)

    def _head_bob(self):
        """Quick head bob."""
        if not self._robot:
            return
        try:
            self._robot.mini.head.pitch.goal_position = -15
            time.sleep(0.2)
            self._robot.mini.head.pitch.goal_position = 5
            time.sleep(0.2)
            self._robot.mini.head.pitch.goal_position = 0
        except Exception:
            pass

    def _antenna_wave(self):
        """Wave antennas alternately."""
        if not self._robot:
            return
        try:
            self._robot.mini.head.l_antenna.goal_position = -0.6
            self._robot.mini.head.r_antenna.goal_position = 0.2
            time.sleep(0.15)
            self._robot.mini.head.l_antenna.goal_position = 0.2
            self._robot.mini.head.r_antenna.goal_position = -0.6
            time.sleep(0.15)
            self._robot.mini.head.l_antenna.goal_position = 0.0
            self._robot.mini.head.r_antenna.goal_position = 0.0
        except Exception:
            pass

    def _side_tilt(self):
        """Tilt head side to side."""
        if not self._robot:
            return
        try:
            self._robot.mini.head.roll.goal_position = 15
            time.sleep(0.25)
            self._robot.mini.head.roll.goal_position = -15
            time.sleep(0.25)
            self._robot.mini.head.roll.goal_position = 0
        except Exception:
            pass

    def list_routines(self) -> list[dict]:
        return [
            {"id": k, "name": v["name"], "moves": len(v["moves"]), "bpm": v["bpm"]}
            for k, v in ROUTINES.items()
        ]

    @property
    def is_dancing(self) -> bool:
        return self._dancing

    def get_status(self) -> dict:
        return {
            "dancing": self._dancing,
            "current_routine": self._current_routine if self._dancing else "",
            "total_dances": self._dance_count,
            "available_routines": self.list_routines(),
        }
