"""Personal Translator — real-time translation between languages.

Reachy can translate spoken phrases between French, English, Chinese,
Spanish, and more using GPT.
"""

import logging
import os

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "english": "en", "french": "fr", "chinese": "zh", "spanish": "es",
    "german": "de", "italian": "it", "portuguese": "pt", "japanese": "ja",
    "korean": "ko", "arabic": "ar", "russian": "ru", "hindi": "hi",
    "dutch": "nl", "swedish": "sv", "polish": "pl",
}

# Reverse map: code -> name
CODE_TO_NAME = {v: k for k, v in SUPPORTED_LANGUAGES.items()}


class Translator:
    """Real-time translation assistant."""

    def __init__(self):
        self._target_language = "french"
        self._history = []

    def set_target(self, language: str) -> str:
        """Set the target translation language."""
        language = language.strip().lower()
        if language in SUPPORTED_LANGUAGES:
            self._target_language = language
            return f"Translation target set to {language.title()}"
        # Try matching partial
        for name in SUPPORTED_LANGUAGES:
            if language in name:
                self._target_language = name
                return f"Translation target set to {name.title()}"
        return f"Unknown language. Supported: {', '.join(SUPPORTED_LANGUAGES.keys())}"

    def translate(self, text: str, target: str = "") -> str:
        """Translate text to the target language."""
        target = target.strip().lower() if target else self._target_language
        if target not in SUPPORTED_LANGUAGES:
            # Try partial match
            for name in SUPPORTED_LANGUAGES:
                if target in name:
                    target = name
                    break

        try:
            import openai
            client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": (
                        f"You are a translator. Translate the following text to {target.title()}. "
                        f"Return ONLY the translation, nothing else. "
                        f"If the text is already in {target.title()}, translate it to English instead."
                    ),
                }, {
                    "role": "user",
                    "content": text,
                }],
                max_tokens=300,
                temperature=0.2,
            )
            translation = resp.choices[0].message.content.strip()
            self._history.append({
                "original": text,
                "translated": translation,
                "target": target,
            })
            return translation
        except Exception as e:
            logger.error("Translation failed: %s", e)
            return f"Sorry, translation failed: {e}"

    def get_status(self) -> dict:
        return {
            "target_language": self._target_language,
            "supported": list(SUPPORTED_LANGUAGES.keys()),
            "history_count": len(self._history),
        }

    def get_history(self) -> list[dict]:
        return list(reversed(self._history[-20:]))


# Voice trigger detection
TRANSLATE_TRIGGERS = [
    "translate", "how do you say", "say in french", "say in spanish",
    "say in chinese", "say in german", "say in italian", "say in japanese",
    "say in korean", "say in arabic", "say in russian", "say in portuguese",
    "what is .* in french", "what is .* in spanish",
    "in french", "in spanish", "in chinese", "in german",
    "in italian", "in japanese", "in korean",
]


def detect_translate_request(text: str) -> tuple[str, str] | None:
    """Detect a translation request. Returns (phrase_to_translate, target_language) or None."""
    lower = text.lower()

    # "how do you say X in Y"
    if "how do you say" in lower:
        parts = lower.split("how do you say", 1)[1].strip()
        for lang in SUPPORTED_LANGUAGES:
            if f"in {lang}" in parts:
                phrase = parts.split(f"in {lang}")[0].strip().strip("'\"")
                return (phrase, lang)
        # No language specified, use default
        return (parts.strip().strip("'\""), "")

    # "translate X to Y"
    if "translate" in lower:
        parts = lower.split("translate", 1)[1].strip()
        for lang in SUPPORTED_LANGUAGES:
            if f"to {lang}" in parts:
                phrase = parts.split(f"to {lang}")[0].strip().strip("'\"")
                return (phrase, lang)
            if f"into {lang}" in parts:
                phrase = parts.split(f"into {lang}")[0].strip().strip("'\"")
                return (phrase, lang)
        return (parts.strip().strip("'\""), "")

    # "say X in Y"
    for lang in SUPPORTED_LANGUAGES:
        if f"in {lang}" in lower and any(p in lower for p in ["say", "what is"]):
            idx = lower.find(f"in {lang}")
            phrase = lower[:idx].strip()
            for prefix in ["say", "what is", "how do you say"]:
                if phrase.startswith(prefix):
                    phrase = phrase[len(prefix):].strip()
            return (phrase.strip("'\""), lang)

    return None
