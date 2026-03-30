"""Move Recorder — Patient teaches Reachy custom moves by physically posing it.

Enables gravity compensation (compliant mode) so the head can be moved by hand,
records the movement using the SDK's start_recording()/stop_recording(), and
plays it back with play_move(). Saved moves can be replayed by name.

Usage:
    recorder = MoveRecorder(robot)
    recorder.start_teaching("happy dance")  # enables compliant mode
    # ... patient moves Reachy's head ...
    recorder.stop_teaching()                # saves the recording
    recorder.play("happy dance")            # plays it back
"""

import json
import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

MOVES_DIR = Path(__file__).parent / "custom_moves"


class MoveRecorder:
    """Records and plays back custom moves taught by the patient."""

    def __init__(self, robot=None):
        self._robot = robot
        self._recording = False
        self._current_name = ""
        self._saved_moves: dict[str, dict] = {}  # name → move data
        MOVES_DIR.mkdir(exist_ok=True)
        self._load_saved()

    def start_teaching(self, name: str) -> str:
        """Enable compliant mode and start recording."""
        if not self._robot or self._robot._sim_mode or not self._robot.mini:
            return "I need to be connected to the real robot for this."
        if self._recording:
            return f"I'm already learning a move called '{self._current_name}'. Say 'done' when you're finished."

        name = name.strip().lower()
        if not name:
            name = f"move_{len(self._saved_moves) + 1}"

        self._current_name = name

        try:
            # Enable gravity compensation — head becomes loose/compliant
            self._robot.mini.enable_gravity_compensation()
            time.sleep(0.3)
            # Start recording
            self._robot.mini.start_recording()
            self._recording = True
            logger.info("Teaching mode started: %s", name)
            return (
                f"Okay, I'm in learning mode! My head is loose now — "
                f"gently move it however you want. I'm recording a move called '{name}'. "
                f"Say 'done' or 'stop teaching' when you're finished."
            )
        except Exception as e:
            logger.error("Failed to start teaching: %s", e)
            return f"Something went wrong: {e}"

    def stop_teaching(self) -> str:
        """Stop recording and save the move."""
        if not self._recording:
            return "I'm not learning a move right now."

        try:
            # Stop recording — returns the recorded data
            move_data = self._robot.mini.stop_recording()
            # Disable gravity compensation — back to normal
            self._robot.mini.disable_gravity_compensation()
            self._recording = False

            if not move_data or len(move_data) < 3:
                self._current_name = ""
                return "That was too short — I didn't catch enough movement. Try again?"

            # Save the move
            name = self._current_name
            self._saved_moves[name] = move_data

            # Persist to disk
            path = MOVES_DIR / f"{name.replace(' ', '_')}.json"
            try:
                with open(path, "w") as f:
                    json.dump(move_data, f)
                logger.info("Saved move '%s' (%d frames) to %s", name, len(move_data), path)
            except Exception as e:
                logger.warning("Could not save move to disk: %s", e)

            self._current_name = ""
            return (
                f"Got it! I learned '{name}' — {len(move_data)} frames recorded. "
                f"Say 'do {name}' or 'play {name}' to see me do it!"
            )
        except Exception as e:
            self._recording = False
            self._current_name = ""
            logger.error("Failed to stop teaching: %s", e)
            try:
                self._robot.mini.disable_gravity_compensation()
            except Exception:
                pass
            return f"Something went wrong saving the move: {e}"

    def play(self, name: str) -> str:
        """Play back a saved move."""
        if not self._robot or self._robot._sim_mode or not self._robot.mini:
            return "I need the real robot to do moves."

        name = name.strip().lower()
        if name not in self._saved_moves:
            if self._saved_moves:
                available = ", ".join(self._saved_moves.keys())
                return f"I don't know a move called '{name}'. I know: {available}"
            return "I haven't learned any moves yet. Teach me one!"

        move_data = self._saved_moves[name]

        def _do_play():
            try:
                from reachy_mini.motion.recorded_move import RecordedMove
                move = RecordedMove({"description": name, "time": [i * 0.01 for i in range(len(move_data))], "set_target_data": move_data})
                self._robot.mini.play_move(move)
                logger.info("Played move: %s", name)
            except Exception as e:
                logger.error("Failed to play move '%s': %s", name, e)

        threading.Thread(target=_do_play, daemon=True).start()
        return f"Doing '{name}'!"

    def list_moves(self) -> list[str]:
        """List all saved move names."""
        return list(self._saved_moves.keys())

    def delete_move(self, name: str) -> str:
        """Delete a saved move."""
        name = name.strip().lower()
        if name in self._saved_moves:
            del self._saved_moves[name]
            path = MOVES_DIR / f"{name.replace(' ', '_')}.json"
            if path.exists():
                path.unlink()
            return f"Deleted move '{name}'."
        return f"I don't have a move called '{name}'."

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def current_move_name(self) -> str:
        return self._current_name

    def _load_saved(self):
        """Load previously saved moves from disk."""
        for path in MOVES_DIR.glob("*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
                name = path.stem.replace("_", " ")
                self._saved_moves[name] = data
                logger.info("Loaded custom move: %s", name)
            except Exception as e:
                logger.warning("Failed to load move %s: %s", path, e)
