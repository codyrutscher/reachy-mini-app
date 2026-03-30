"""Quick automated test — no user input needed."""

import sys
import time
from robot.robot import Robot
from brain.emotion import EmotionDetector


def test_text_emotions():
    """Test text-based emotion detection + robot expressions."""
    print("=== Test: Text Emotion → Robot Expression ===\n")
    emotion = EmotionDetector(backend="keywords")
    robot = Robot()
    robot.connect()

    test_phrases = [
        "I'm so happy to see you!",
        "I feel really scared right now",
        "This makes me so angry",
        "I'm feeling kind of sad today",
        "Wow that's amazing!",
    ]

    for phrase in test_phrases:
        print(f"\nUser says: '{phrase}'")
        detected = emotion.detect(phrase)
        robot.express(detected)
        time.sleep(1.0)
        robot.reset()
        time.sleep(0.5)

    print("\nText emotion test passed!")
    robot.disconnect()


def test_movements():
    """Test all movement patterns."""
    print("=== Test: Movement Patterns ===\n")
    robot = Robot()
    robot.connect()

    moves = [
        "greet", "nod", "shake", "dance", "celebrate",
        "wiggle", "think", "curious", "look around",
        "bow", "stretch", "empathy", "sleepy", "wake up",
        "rock", "goodbye",
    ]

    for move in moves:
        print(f"\n→ {move}")
        robot.perform(move)
        time.sleep(0.5)
        robot.reset()
        time.sleep(0.3)

    print("\nAll movement tests passed!")
    robot.disconnect()


def test_face_emotion():
    """Test webcam face emotion detection (3 readings)."""
    print("=== Test: Face Emotion Detection ===\n")
    from perception.face_emotion import FaceEmotionDetector

    detector = FaceEmotionDetector()
    if not detector.start_camera():
        print("No webcam available, skipping face test.")
        return

    for i in range(3):
        emotion = detector.read_emotion()
        print(f"  Reading {i+1}: {emotion}")
        time.sleep(1.5)

    detector.stop()
    print("\nFace emotion test passed!")


if __name__ == "__main__":
    if "--face" in sys.argv:
        test_face_emotion()
    elif "--moves" in sys.argv:
        test_movements()
    else:
        test_text_emotions()
