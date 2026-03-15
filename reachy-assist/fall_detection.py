"""Fall detection using MediaPipe pose estimation.

Analyzes camera frames for sudden posture changes that indicate a fall.
Triggers caregiver alerts when a fall is detected."""

import threading
import time

_detector = None
_running = False
_callback = None
_fall_cooldown = 30  # seconds between fall alerts


class FallDetector:
    """Pose-based fall detection using MediaPipe."""

    def __init__(self, on_fall=None):
        self._on_fall = on_fall
        self._running = False
        self._thread = None
        self._last_alert = 0
        self._pose = None
        self._prev_hip_y = None
        self._fall_threshold = 0.15  # normalized Y drop threshold
        self._lying_threshold = 0.08  # hip-shoulder Y diff for lying down
        self._consecutive_fall_frames = 0
        self._required_fall_frames = 3  # need 3 consecutive frames

        try:
            import mediapipe as mp
            self._mp_pose = mp.solutions.pose
            self._pose = self._mp_pose.Pose(
                static_image_mode=False,
                model_complexity=0,  # fastest
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            print("[FALL] MediaPipe pose estimator ready")
        except ImportError:
            print("[FALL] MediaPipe not installed — fall detection disabled")
            print("[FALL] Install with: pip install mediapipe")

    @property
    def available(self):
        return self._pose is not None

    def analyze_frame(self, frame):
        """Analyze a single camera frame for fall indicators.
        Returns dict with detection results."""
        if not self._pose:
            return {"fall_detected": False, "reason": "no_pose_model"}

        import cv2
        import numpy as np

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._pose.process(rgb)

        if not results.pose_landmarks:
            return {"fall_detected": False, "reason": "no_person"}

        landmarks = results.pose_landmarks.landmark

        # Key landmarks (normalized 0-1 coordinates, Y increases downward)
        left_hip = landmarks[23]
        right_hip = landmarks[24]
        left_shoulder = landmarks[11]
        right_shoulder = landmarks[12]
        nose = landmarks[0]

        hip_y = (left_hip.y + right_hip.y) / 2
        shoulder_y = (left_shoulder.y + right_shoulder.y) / 2

        # Check 1: Sudden downward movement of hips
        sudden_drop = False
        if self._prev_hip_y is not None:
            y_change = hip_y - self._prev_hip_y
            if y_change > self._fall_threshold:
                sudden_drop = True
        self._prev_hip_y = hip_y

        # Check 2: Person is lying down (hips and shoulders at similar Y)
        lying_down = abs(hip_y - shoulder_y) < self._lying_threshold

        # Check 3: Head below hips (inverted posture)
        head_below_hips = nose.y > hip_y + 0.05

        # Combine signals
        fall_indicators = sum([sudden_drop, lying_down, head_below_hips])

        if fall_indicators >= 2:
            self._consecutive_fall_frames += 1
        else:
            self._consecutive_fall_frames = max(0, self._consecutive_fall_frames - 1)

        fall_detected = self._consecutive_fall_frames >= self._required_fall_frames

        if fall_detected:
            now = time.time()
            if now - self._last_alert > _fall_cooldown:
                self._last_alert = now
                self._consecutive_fall_frames = 0
                if self._on_fall:
                    self._on_fall({
                        "type": "fall",
                        "confidence": min(fall_indicators / 3.0, 1.0),
                        "indicators": {
                            "sudden_drop": sudden_drop,
                            "lying_down": lying_down,
                            "head_below_hips": head_below_hips,
                        },
                    })
                return {
                    "fall_detected": True,
                    "confidence": min(fall_indicators / 3.0, 1.0),
                    "indicators": {
                        "sudden_drop": sudden_drop,
                        "lying_down": lying_down,
                        "head_below_hips": head_below_hips,
                    },
                }

        return {
            "fall_detected": False,
            "posture": "lying" if lying_down else "upright",
            "hip_y": round(hip_y, 3),
            "shoulder_y": round(shoulder_y, 3),
        }

    def start_monitoring(self, frame_source=None):
        """Start continuous fall monitoring in background thread."""
        if not self._pose:
            return False
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, args=(frame_source,), daemon=True)
        self._thread.start()
        print("[FALL] Continuous monitoring started")
        return True

    def _monitor_loop(self, frame_source):
        """Background monitoring loop."""
        while self._running:
            try:
                if frame_source:
                    frame = frame_source()
                    if frame is not None:
                        self.analyze_frame(frame)
            except Exception as e:
                print(f"[FALL] Monitor error: {e}")
            time.sleep(0.5)  # 2 fps for fall detection

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._pose:
            self._pose.close()
        print("[FALL] Monitoring stopped")
