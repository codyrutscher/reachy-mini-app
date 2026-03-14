"""Entry point for the Reachy accessibility assistant."""

import argparse
from interaction import InteractionLoop


def main():
    parser = argparse.ArgumentParser(description="Reachy Accessibility Assistant")
    parser.add_argument(
        "--text", action="store_true",
        help="Use text input/output instead of mic/speaker",
    )
    parser.add_argument(
        "--emotion-backend", choices=["keywords", "model"], default="keywords",
        help="Text emotion backend: 'keywords' (fast) or 'model' (ML)",
    )
    parser.add_argument(
        "--face", action="store_true",
        help="Enable webcam-based facial emotion detection",
    )
    parser.add_argument(
        "--brain", choices=["ollama", "openai", "none"], default="none",
        help="LLM backend: 'ollama' (local), 'openai' (API key needed), or 'none'",
    )
    parser.add_argument(
        "--language", default="en",
        choices=["en", "es", "fr", "de", "it", "pt", "zh", "ja", "ko"],
        help="Language for speech recognition and TTS",
    )
    args = parser.parse_args()

    brain_backend = args.brain if args.brain != "none" else None

    loop = InteractionLoop(
        text_mode=args.text,
        emotion_backend=args.emotion_backend,
        use_face=args.face,
        brain_backend=brain_backend,
        language=args.language,
    )
    loop.start()


if __name__ == "__main__":
    main()
