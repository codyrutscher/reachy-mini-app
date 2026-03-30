"""Emotion detection from text.

Supports two backends:
  - "keywords" (default): zero-download keyword matching — great for testing
  - "model": HuggingFace transformer model — better accuracy, requires download
"""

from core.config import EMOTION_MODEL
from core.log_config import get_logger

logger = get_logger("emotion")

# Keyword lists tuned for elderly and disability care conversations
_KEYWORDS = {
    "joy": ["happy", "glad", "great", "wonderful", "love", "amazing", "awesome",
            "excited", "fantastic", "good", "yay", "smile", "laugh", "fun",
            "thankful", "grateful", "blessed", "enjoyed", "lovely", "nice",
            "beautiful", "delightful", "pleased", "cheerful", "proud",
            "grandchild", "grandson", "granddaughter", "birthday", "celebrate"],
    "sadness": ["sad", "unhappy", "depressed", "cry", "miss", "lonely", "sorry",
                "hurt", "pain", "lost", "grief", "terrible", "awful",
                "alone", "nobody", "tired of", "exhausted", "hopeless",
                "passed away", "died", "gone", "funeral", "mourning",
                "can't do", "used to be able", "wish i could", "getting old",
                "burden", "useless", "worthless", "forgotten", "invisible"],
    "anger": ["angry", "mad", "furious", "hate", "annoyed", "frustrated",
              "irritated", "rage", "stupid", "unfair", "worst",
              "ignored", "disrespected", "rude", "incompetent", "fed up",
              "sick of", "tired of waiting", "nobody listens", "don't care"],
    "fear": ["scared", "afraid", "terrified", "anxious", "worried", "nervous",
             "panic", "horror", "creepy", "danger", "frightened",
             "falling", "fall", "dizzy", "confused", "dark", "night",
             "surgery", "hospital", "doctor", "diagnosis", "test results",
             "what if", "something wrong", "getting worse"],
    "surprise": ["wow", "surprised", "shocked", "unexpected", "unbelievable",
                 "omg", "whoa", "really", "no way", "incredible",
                 "can't believe", "never expected", "out of nowhere"],
    "disgust": ["disgusting", "gross", "nasty", "eww", "yuck", "horrible",
                "revolting", "sick", "vile", "unpleasant", "dreadful"],
}


class EmotionDetector:
    def __init__(self, backend: str = "keywords"):
        self.backend = backend
        self.classifier = None

        if backend == "model":
            from transformers import pipeline
            logger.info("Loading model (this may download ~300MB)...")
            self.classifier = pipeline(
                "text-classification",
                model=EMOTION_MODEL,
                top_k=1,
            )
        logger.info("Ready (backend=%s)", backend)

    def detect(self, text: str) -> str:
        """Detect the primary emotion in a text string."""
        if not text:
            return "neutral"

        if self.backend == "model" and self.classifier:
            return self._detect_model(text)
        return self._detect_keywords(text)

    def _detect_model(self, text: str) -> str:
        results = self.classifier(text)
        emotion = results[0][0]["label"]
        score = results[0][0]["score"]
        logger.info("Detected: %s (%.2f)", emotion, score)
        return emotion

    def _detect_keywords(self, text: str) -> str:
        lower = text.lower()
        scores = {e: 0 for e in _KEYWORDS}
        for emotion, words in _KEYWORDS.items():
            for w in words:
                if w in lower:
                    scores[emotion] += 1
        best = max(scores, key=scores.get)
        if scores[best] == 0:
            best = "neutral"
        logger.info("Detected: %s (keyword match)", best)
        return best

def get_keywords_for(emotion: str) -> list[str]:
    return _KEYWORDS.get(emotion, [])
