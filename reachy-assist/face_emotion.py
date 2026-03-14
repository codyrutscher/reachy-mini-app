"""Facial emotion detection using webcam + HSEmotion (ONNX) + MTCNN."""

import threading
import time
import cv2
import numpy as np
from facenet_pytorch import MTCNN
from hsemotion_onnx.facial_emotions import HSEmotionRecognizer

# Map HSEmotion labels → our emotion set
_FACE_MAP = {
    "Anger": "anger",
    "Contempt": "disgust",
    "Disgust": "disgust",
    "Fear": "fear",
    "Happiness": "joy",
    "Neutral": "neutral",
    "Sadness": "sadness",
    "Surprise": "surprise",
}


class FaceEmotionDetector:
    def __init__(self):
        print("[FACE] Initializing face emotion detector...")
        self.face_detector = MTCNN(keep_all=False, post_process=False, device="cpu")
        self.emotion_model = HSEmotionRecognizer(model_name="enet_b0_8_best_afew")
        self.cap = None
        self._current_emotion = "neutral"
        self._running = False
        self._thread = None
        print("[FACE] Ready (MTCNN + HSEmotion ONNX)")

    def start_camera(self) -> bool:
        """Open the webcam."""
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("[FACE] WARNING: Could not open webcam")
            return False
        print("[FACE] Camera opened")
        return True

    def read_emotion(self) -> str:
        """Capture one frame and detect the dominant facial emotion."""
        if self.cap is None or not self.cap.isOpened():
            return "neutral"

        ret, frame = self.cap.read()
        if not ret:
            return "neutral"

        try:
            # Detect face bounding box with MTCNN
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            boxes, probs = self.face_detector.detect(rgb)

            if boxes is None or len(boxes) == 0:
                return "neutral"

            # Crop the first face
            x1, y1, x2, y2 = [int(b) for b in boxes[0]]
            h, w = frame.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            face_img = rgb[y1:y2, x1:x2]

            if face_img.size == 0:
                return "neutral"

            # Classify emotion
            emotion_label, scores = self.emotion_model.predict_emotions(face_img, logits=False)
            mapped = _FACE_MAP.get(emotion_label, "neutral")
            confidence = max(scores)
            print(f"[FACE] Detected: {emotion_label} → {mapped} ({confidence:.2f})")

            if confidence < 0.3:
                return "neutral"
            return mapped

        except Exception as e:
            print(f"[FACE] Detection error: {e}")
            return "neutral"

    def start_continuous(self):
        """Run face detection in a background thread."""
        if not self.start_camera():
            return False
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def _loop(self):
        """Background loop: read emotion every ~2 seconds."""
        while self._running:
            self._current_emotion = self.read_emotion()
            time.sleep(2.0)

    @property
    def current_emotion(self) -> str:
        return self._current_emotion

    def stop(self):
        """Stop background thread and release webcam."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        if self.cap:
            self.cap.release()
            print("[FACE] Camera released")
