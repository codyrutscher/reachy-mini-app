"""Entry point for the Reachy accessibility assistant."""

import argparse
import os
import warnings

# Suppress noisy protobuf deprecation warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.protobuf")


def _load_env():
    """Load .env file from the script's directory."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())


_load_env()

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
    parser.add_argument(
        "--profile", choices=["elderly", "disabled"], default="elderly",
        help="Patient profile: 'elderly' or 'disabled' — adapts behavior, exercises, and conversation style",
    )
    parser.add_argument(
        "--realtime", action="store_true",
        help="Use OpenAI Realtime API for full-duplex voice conversation (fastest, most natural)",
    )
    args = parser.parse_args()

    # Realtime mode — full-duplex voice via WebSocket, bypasses the normal pipeline
    if args.realtime:
        from core.config import SYSTEM_PROMPT
        from integration.realtime_conversation import RealtimeConversation

        voice = os.environ.get("REACHY_VOICE", "shimmer")
        # Realtime API supports: alloy, echo, shimmer (standard) + ash, ballad, coral, sage, verse
        # nova is NOT supported in realtime — use shimmer as default
        if voice == "nova":
            voice = "shimmer"

        print(f"[REALTIME] Starting full-duplex conversation (voice={voice})")

        conv = RealtimeConversation(
            system_prompt=SYSTEM_PROMPT,
            voice=voice,
            patient_id="default",
        )
        conv.start()
        return

    brain_backend = args.brain if args.brain != "none" else None

    loop = InteractionLoop(
        text_mode=args.text,
        emotion_backend=args.emotion_backend,
        use_face=args.face,
        brain_backend=brain_backend,
        language=args.language,
        profile=args.profile,
    )
    loop.start()


if __name__ == "__main__":
    main()
