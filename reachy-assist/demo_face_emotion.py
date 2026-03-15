"""Live face emotion demo — opens webcam, detects your expression,
shows it on screen, and speaks what it sees.

Usage:
    python demo_face_emotion.py

Press 'q' to quit.
"""

import subprocess
import threading
import time

import cv2
import numpy as np
from facenet_pytorch import MTCNN
from hsemotion_onnx.facial_emotions import HSEmotionRecognizer

# Map HSEmotion labels to friendly descriptions
EMOTION_MAP = {
    "Anger": ("angry", "You look a bit angry. Everything okay?"),
    "Contempt": ("contempt", "Hmm, I sense some contempt there."),
    "Disgust": ("disgusted", "Something bothering you? You look disgusted."),
    "Fear": ("afraid", "You look a little scared. I'm here with you."),
    "Happiness": ("happy", "You look happy! That makes me happy too."),
    "Neutral": ("neutral", "You seem calm and relaxed."),
    "Sadness": ("sad", "You look a bit sad. Want to talk about it?"),
    "Surprise": ("surprised", "Oh! You look surprised!"),
}

# Colors for each emotion (BGR)
EMOTION_COLORS = {
    "angry": (0, 0, 255),
    "contempt": (0, 100, 200),
    "disgusted": (0, 140, 0),
    "afraid": (200, 0, 200),
    "happy": (0, 220, 0),
    "neutral": (200, 200, 200),
    "sad": (255, 150, 0),
    "surprised": (0, 220, 220),
}


def speak(text):
    """Speak text using macOS say command (non-blocking)."""
    threading.Thread(
        target=lambda: subprocess.run(
            ["say", "-v", "Samantha", "-r", "160", text],
            capture_output=True,
        ),
        daemon=True,
    ).start()


def main():
    print("Initializing face detector...")
    face_detector = MTCNN(keep_all=False, post_process=False, device="cpu")
    print("Initializing emotion model...")
    emotion_model = HSEmotionRecognizer(model_name="enet_b0_8_best_afew")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not open webcam")
        return

    print("\n=== Face Emotion Demo ===")
    print("Look at the camera. I'll tell you what I see.")
    print("Press 'q' to quit.\n")

    speak("Hello! Look at the camera and I'll tell you what emotion I see on your face.")

    last_spoken_emotion = None
    last_speak_time = 0
    speak_cooldown = 4  # seconds between spoken updates
    frame_count = 0
    detect_every = 5  # run detection every N frames for performance

    current_label = "neutral"
    current_phrase = "You seem calm and relaxed."
    current_confidence = 0.0
    current_box = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        display = frame.copy()

        # Run detection every N frames
        if frame_count % detect_every == 0:
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                boxes, probs = face_detector.detect(rgb)

                if boxes is not None and len(boxes) > 0:
                    x1, y1, x2, y2 = [int(b) for b in boxes[0]]
                    h, w = frame.shape[:2]
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w, x2), min(h, y2)
                    current_box = (x1, y1, x2, y2)

                    face_img = rgb[y1:y2, x1:x2]
                    if face_img.size > 0:
                        raw_label, scores = emotion_model.predict_emotions(
                            face_img, logits=False
                        )
                        conf = max(scores)
                        current_confidence = conf

                        if conf >= 0.3:
                            mapped = EMOTION_MAP.get(raw_label, ("neutral", "Hmm, interesting."))
                            current_label = mapped[0]
                            current_phrase = mapped[1]
                        else:
                            current_label = "neutral"
                            current_phrase = "You seem calm and relaxed."
                else:
                    current_box = None
                    current_label = "neutral"
                    current_confidence = 0.0

            except Exception as e:
                print(f"Detection error: {e}")

        # Draw face box and emotion label
        color = EMOTION_COLORS.get(current_label, (200, 200, 200))

        if current_box:
            x1, y1, x2, y2 = current_box
            cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)

            # Emotion label above the box
            label_text = f"{current_label} ({current_confidence:.0%})"
            (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
            cv2.rectangle(display, (x1, y1 - th - 12), (x1 + tw + 8, y1), color, -1)
            cv2.putText(display, label_text, (x1 + 4, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

        # Status bar at bottom
        bar_h = 50
        cv2.rectangle(display, (0, display.shape[0] - bar_h),
                       (display.shape[1], display.shape[0]), (30, 30, 40), -1)
        cv2.putText(display, f"Emotion: {current_label}  |  Press 'q' to quit",
                    (12, display.shape[0] - 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        cv2.imshow("Reachy Face Emotion Demo", display)

        # Speak the emotion when it changes (with cooldown)
        now = time.time()
        if (current_label != last_spoken_emotion
                and current_label != "neutral"
                and now - last_speak_time > speak_cooldown
                and current_confidence >= 0.4):
            speak(current_phrase)
            last_spoken_emotion = current_label
            last_speak_time = now
            print(f"  >> {current_label}: \"{current_phrase}\"")

        # Also speak neutral if they've been neutral for a while after an emotion
        if (current_label == "neutral"
                and last_spoken_emotion is not None
                and last_spoken_emotion != "neutral"
                and now - last_speak_time > speak_cooldown * 2):
            speak("You seem calm now.")
            last_spoken_emotion = "neutral"
            last_speak_time = now

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("\nDemo ended. Bye!")


if __name__ == "__main__":
    main()
