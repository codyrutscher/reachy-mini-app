"""Conversational AI brain for Reachy — generates real responses with
mood tracking, safety awareness, and eldercare intelligence."""

import os
import random
from config import (
    SYSTEM_PROMPT, RESPONSES, SAFETY_KEYWORDS, LONELINESS_KEYWORDS,
    CONFUSION_KEYWORDS, SAFETY_RESPONSE, EMERGENCY_RESPONSE,
)


class Brain:
    """LLM-powered conversation engine with emotional memory and safety awareness."""

    def __init__(self, backend: str = "ollama", profile_prompt: str = ""):
        self.backend = backend
        system = SYSTEM_PROMPT
        if profile_prompt:
            system += "\n\n" + profile_prompt
        self.history = [{"role": "system", "content": system}]
        self.client = None

        # Mood tracking — remembers emotional trajectory
        self.mood_history = []
        self.user_name = None
        self.user_facts = []  # things we've learned about the user
        self.consecutive_sad = 0
        self.session_start = True

        if backend == "openai":
            from openai import OpenAI
            self.client = OpenAI()
            self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            print(f"[BRAIN] Using OpenAI ({self.model})")
        elif backend == "ollama":
            from openai import OpenAI
            self.client = OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama",
            )
            self.model = os.getenv("OLLAMA_MODEL", "llama3.2")
            print(f"[BRAIN] Using Ollama ({self.model})")
        else:
            print("[BRAIN] Using enhanced fallback (no LLM)")

        print("[BRAIN] Ready")

    def think(self, user_text: str, emotion: str) -> str:
        """Generate a response given user input and detected emotion."""
        lower = user_text.lower()

        # Safety check first — always takes priority
        safety_flag = self._check_safety(lower)
        if safety_flag == "crisis":
            self._track_mood(emotion, user_text)
            return SAFETY_RESPONSE
        if safety_flag == "emergency":
            self._track_mood(emotion, user_text)
            return EMERGENCY_RESPONSE

        # Track mood over time
        self._track_mood(emotion, user_text)

        # Check for loneliness patterns
        loneliness = self._check_loneliness(lower)

        # Check for confusion patterns
        confusion = self._check_confusion(lower)

        # Build context for the LLM
        context = self._build_context(emotion, loneliness, confusion)

        if self.client is None:
            return self._smart_fallback(emotion, loneliness, confusion)

        # Augment the user message with emotional + situational context
        augmented = f"[{context}] {user_text}"
        self.history.append({"role": "user", "content": augmented})

        # Add a greeting nudge for the first message
        if self.session_start:
            self.history.append({
                "role": "system",
                "content": "This is the start of the conversation. Greet them warmly and ask how they're doing today.",
            })
            self.session_start = False

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                max_tokens=200,
                temperature=0.75,
            )
            reply = resp.choices[0].message.content.strip()
            self.history.append({"role": "assistant", "content": reply})

            # Keep history manageable (system + last 30 exchanges)
            if len(self.history) > 61:
                self.history = [self.history[0]] + self.history[-60:]

            return reply
        except Exception as e:
            print(f"[BRAIN] LLM error: {e}")
            return self._smart_fallback(emotion, loneliness, confusion)

    def _check_safety(self, text: str) -> str:
        """Check for crisis or emergency keywords."""
        emergency_words = ["chest pain", "can't breathe", "stroke", "bleeding",
                           "can't get up", "fell down", "fallen", "emergency", "help me"]
        crisis_words = ["don't want to live", "want to die", "kill myself",
                        "end it all", "hurt myself", "suicide", "can't go on"]

        for word in crisis_words:
            if word in text:
                print("[BRAIN] ⚠️  CRISIS keywords detected")
                return "crisis"
        for word in emergency_words:
            if word in text:
                print("[BRAIN] ⚠️  EMERGENCY keywords detected")
                return "emergency"
        return ""

    def _check_loneliness(self, text: str) -> bool:
        for word in LONELINESS_KEYWORDS:
            if word in text:
                return True
        return False

    def _check_confusion(self, text: str) -> bool:
        for word in CONFUSION_KEYWORDS:
            if word in text:
                return True
        return False

    def _track_mood(self, emotion: str, text: str):
        """Track emotional trajectory over the conversation."""
        self.mood_history.append(emotion)

        if emotion == "sadness":
            self.consecutive_sad += 1
        else:
            self.consecutive_sad = 0

        # Try to learn the user's name
        lower = text.lower()
        if not self.user_name:
            for prefix in ["my name is ", "i'm ", "i am ", "call me "]:
                if prefix in lower:
                    idx = lower.index(prefix) + len(prefix)
                    name = text[idx:].split()[0].strip(".,!?")
                    if len(name) > 1 and name.isalpha():
                        self.user_name = name.capitalize()
                        print(f"[BRAIN] Learned user name: {self.user_name}")

    def _build_context(self, emotion: str, loneliness: bool, confusion: bool) -> str:
        """Build a rich context string for the LLM."""
        parts = [f"User seems {emotion}"]

        if loneliness:
            parts.append("showing signs of loneliness")
        if confusion:
            parts.append("may be confused or disoriented — be extra gentle and patient")
        if self.consecutive_sad >= 3:
            parts.append("has been sad for several messages — check in on them more deeply")
        if self.user_name:
            parts.append(f"user's name is {self.user_name}")

        # Mood trajectory
        if len(self.mood_history) >= 3:
            recent = self.mood_history[-3:]
            if recent[0] in ("sadness", "fear") and recent[-1] == "joy":
                parts.append("mood is improving — acknowledge the positive shift")
            elif recent[0] == "joy" and recent[-1] in ("sadness", "fear"):
                parts.append("mood is declining — be extra attentive")

        return "; ".join(parts)

    def _smart_fallback(self, emotion: str, loneliness: bool, confusion: bool) -> str:
        """Enhanced fallback when no LLM is available."""
        if loneliness:
            responses = [
                "I'm right here with you. You're not alone — I enjoy our conversations.",
                "I'm glad we're talking. Tell me about something that made you smile recently?",
                "You know, I always look forward to chatting with you. What's on your mind?",
            ]
            return random.choice(responses)

        if confusion:
            responses = [
                "That's okay, no rush at all. I'm Reachy, your robot friend. We're just chatting.",
                "No worries. Take your time. I'm right here whenever you're ready.",
                "It's alright. Let's take it easy. Is there anything I can help you with?",
            ]
            return random.choice(responses)

        if self.consecutive_sad >= 3:
            return "I've noticed you've been having a tough time. I really care about how you're feeling. Would it help to talk to someone you trust about this?"

        # Regular emotion-based response with variety
        options = RESPONSES.get(emotion, RESPONSES["neutral"])
        return random.choice(options)
