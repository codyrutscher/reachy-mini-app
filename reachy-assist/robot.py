"""Robot control layer — works with both simulation and real hardware.
Falls back to simulation mode when no Reachy Mini is connected.
Includes camera streaming and frame capture."""

import threading
import time
from config import EXPRESSIONS

# Try to import Reachy Mini SDK
try:
    from reachy_mini import ReachyMini
    from reachy_mini.utils import create_head_pose
    _HAS_REACHY = True
except ImportError:
    _HAS_REACHY = False

from movements import Movements


class Robot:
    def __init__(self):
        self.mini = None
        self.moves = None
        self._sim_mode = False
        self._camera = None
        self._camera_thread = None
        self._camera_running = False
        self._stream_server = None

    def connect(self):
        if _HAS_REACHY:
            try:
                self.mini = ReachyMini()
                self.mini.__enter__()
                self.moves = Movements(self.mini)
                print("[ROBOT] Connected to Reachy Mini")
                return
            except (ConnectionError, Exception) as e:
                print(f"[ROBOT] Could not connect to Reachy Mini: {e}")

        # Simulation fallback
        self._sim_mode = True
        print("[ROBOT] Running in SIMULATION mode (no hardware)")
        print("[ROBOT] All movements and expressions will be logged to console")

    def start_camera_stream(self, port=5556):
        """Start camera capture and MJPEG stream server."""
        try:
            from camera_stream import start_stream_server, update_frame
            self._stream_server = start_stream_server(port)
            self._camera_running = True
            self._camera_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._camera_thread.start()
            return True
        except Exception as e:
            print(f"[CAMERA] Failed to start: {e}")
            return False

    def _capture_loop(self):
        """Background thread that captures frames from Reachy's camera."""
        from camera_stream import update_frame
        import cv2
        # In sim mode, use the computer's webcam
        if self._sim_mode:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                print("[CAMERA] Could not open webcam for simulation")
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

    def stop_camera_stream(self):
        self._camera_running = False
        if self._stream_server:
            from camera_stream import stop_stream_server
            stop_stream_server(self._stream_server)

    def disconnect(self):
        self.stop_camera_stream()
        if self.mini and not self._sim_mode:
            self.mini.__exit__(None, None, None)
            print("[ROBOT] Disconnected")
        elif self._sim_mode:
            print("[ROBOT] Simulation ended")

    def express(self, emotion, duration=0.8):
        if self._sim_mode:
            print(f"[SIM] Express: {emotion}")
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
        print(f"[ROBOT] Expressing: {emotion}")

    def perform(self, action):
        if self._sim_mode:
            print(f"[SIM] Perform: {action}")
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
        }
        mover = actions.get(action.lower())
        if mover:
            print(f"[ROBOT] Performing: {action}")
            mover()
            return True
        return False

    def reset(self, duration=0.6):
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

    def nod(self):
        if self._sim_mode:
            print("[SIM] Nod")
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
