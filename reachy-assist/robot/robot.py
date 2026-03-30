"""Robot control layer — works with both simulation and real hardware.
Falls back to simulation mode when no Reachy Mini is connected.
Includes camera streaming and frame capture."""

import threading
import time
from typing import Optional
from core.config import EXPRESSIONS
from core.log_config import get_logger

logger = get_logger("robot")

# Try to import Reachy Mini SDK
try:
    from reachy_mini import ReachyMini
    from reachy_mini.utils import create_head_pose
    _HAS_REACHY = True
except ImportError:
    _HAS_REACHY = False

from robot.movements import Movements


class Robot:
    def __init__(self) -> None:
        self.mini: Optional[object] = None
        self.moves: Optional["Movements"] = None
        self._sim_mode: bool = False
        self._camera: Optional[object] = None
        self._camera_thread: Optional[threading.Thread] = None
        self._camera_running: bool = False
        self._stream_server: Optional[object] = None

    def connect(self) -> None:
        if _HAS_REACHY:
            try:
                self.mini = ReachyMini()
                self.mini.__enter__()
                self.moves = Movements(self.mini)
                logger.info("Connected to Reachy Mini")
                return
            except (ConnectionError, Exception) as e:
                logger.warning("Could not connect to Reachy Mini: %s", e)

        # Simulation fallback
        self._sim_mode = True
        logger.info("Running in SIMULATION mode (no hardware)")
        logger.info("All movements and expressions will be logged to console")

        # Start visual simulator window
        try:
            from robot.robot_sim import start_sim
            start_sim()
            self._sim_visual = True
        except Exception as e:
            logger.debug("Visual sim not available: %s", e)
            self._sim_visual = False

    def start_camera_stream(self, port: int = 5556) -> bool:
        """Start camera capture and MJPEG stream server."""
        try:
            from perception.camera_stream import start_stream_server, update_frame
            self._stream_server = start_stream_server(port)
            self._camera_running = True
            self._camera_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._camera_thread.start()
            return True
        except Exception as e:
            logger.error("Camera failed to start: %s", e)
            return False

    def _capture_loop(self) -> None:
        """Background thread that captures frames from Reachy's camera."""
        from perception.camera_stream import update_frame
        import cv2
        # In sim mode, use the computer's webcam
        if self._sim_mode:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                logger.warning("Could not open webcam for simulation")
                return
            while self._camera_running:
                ret, frame = cap.read()
                if ret:
                    update_frame(frame)
                time.sleep(0.1)
            cap.release()
        else:
            while self._camera_running:
                try:
                    if self.mini and hasattr(self.mini, 'media') and self.mini.media:
                        cam = self.mini.media.camera
                        if cam:
                            frame = cam.read()
                            if frame is not None:
                                update_frame(frame)
                except Exception:
                    pass
                time.sleep(0.1)

    def stop_camera_stream(self) -> None:
        self._camera_running = False
        if self._stream_server:
            from perception.camera_stream import stop_stream_server
            stop_stream_server(self._stream_server)

    def disconnect(self) -> None:
        self.stop_camera_stream()
        if self.mini and not self._sim_mode:
            self.mini.__exit__(None, None, None)
            logger.info("Disconnected")
        elif self._sim_mode:
            logger.info("Simulation ended")

    def express(self, emotion: str, duration: float = 0.8) -> None:
        if self._sim_mode:
            logger.debug("SIM Express: %s", emotion)
            if self._sim_visual:
                from robot.robot_sim import send_expression
                send_expression(emotion)
            return

        emotion_moves = {
            "joy": self.moves.happy_wiggle,
            "sadness": self.moves.sad_droop,
            "anger": self.moves.angry_huff,
            "fear": self.moves.scared_startle,
            "surprise": self.moves.surprised,
            "disgust": self.moves.confused_tilt,
        }
        mover = emotion_moves.get(emotion)
        if mover:
            mover()
        else:
            expr = EXPRESSIONS.get(emotion, EXPRESSIONS["neutral"])
            self.mini.goto_target(
                head=create_head_pose(
                    roll=expr["head_roll"], mm=True, degrees=True
                ),
                antennas=expr["antennas"],
                duration=duration,
            )
        logger.info("Expressing: %s", emotion)

    def perform(self, action: str) -> bool:
        if self._sim_mode:
            logger.debug("SIM Perform: %s", action)
            if self._sim_visual:
                from robot.robot_sim import send_action
                send_action(action)
            return True

        if not self.moves:
            return False
        actions = {
            "nod": self.moves.nod_yes,
            "yes": self.moves.nod_yes,
            "shake": self.moves.shake_no,
            "no": self.moves.shake_no,
            "greet": self.moves.greeting,
            "hello": self.moves.greeting,
            "goodbye": self.moves.goodbye,
            "bye": self.moves.goodbye,
            "dance": self.moves.dance,
            "wiggle": self.moves.silly_wiggle,
            "celebrate": self.moves.celebrate,
            "think": self.moves.thinking,
            "listen": self.moves.listening,
            "curious": self.moves.curious_look,
            "look around": self.moves.look_around,
            "bow": self.moves.bow,
            "breathe": self.moves.breathing_guide,
            "rock": self.moves.gentle_rock,
            "stretch": self.moves.stretch,
            "sleepy": self.moves.sleepy,
            "wake up": self.moves.wake_up_stretch,
            "sleep": self.moves.sleep,
            "empathy": self.moves.empathy_lean,
            "excited": self.moves.excited_bounce,
            "excited bounce": self.moves.excited_bounce,
            "comfort": self.moves.comfort_pat,
            "comfort pat": self.moves.comfort_pat,
            "storytelling": self.moves.storytelling,
            "exercise demo": self.moves.exercise_demo,
            "music sway": self.moves.music_sway,
            "attention": self.moves.attention_grab,
            "attention grab": self.moves.attention_grab,
            "proud": self.moves.proud,
            "worried": self.moves.worried,
            "peek": self.moves.playful_peek,
            "peekaboo": self.moves.playful_peek,
            "meditation": self.moves.meditation_guide,
            "meditation guide": self.moves.meditation_guide,
        }
        mover = actions.get(action.lower())
        if mover:
            logger.info("Performing: %s", action)
            mover()
            return True
        return False

    def reset(self, duration: float = 0.6) -> None:
        if self._sim_mode:
            return
        if self.moves:
            self.moves.reset(duration)
        elif self.mini:
            self.mini.goto_target(
                head=create_head_pose(),
                antennas=[0, 0],
                duration=duration,
            )

    def nod(self) -> None:
        if self._sim_mode:
            logger.debug("SIM Nod")
            return
        if self.moves:
            self.moves.nod_yes()
        elif self.mini:
            self.mini.goto_target(
                head=create_head_pose(z=-8, mm=True, degrees=True),
                duration=0.3,
            )
            self.mini.goto_target(
                head=create_head_pose(z=8, mm=True, degrees=True),
                duration=0.3,
            )
            self.mini.goto_target(
                head=create_head_pose(), duration=0.3,
            )
