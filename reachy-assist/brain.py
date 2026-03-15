"""Conversational AI brain for Reachy — generates real responses with
mood tracking, safety awareness, and eldercare intelligence."""

import os
import re
import random
from config import (
    SYSTEM_PROMPT, RESPONSES, SAFETY_KEYWORDS, LONELINESS_KEYWORDS,
    CONFUSION_KEYWORDS, SAFETY_RESPONSE, EMERGENCY_RESPONSE,
)


class Brain:
    """LLM-powered conversation engine with emotional memory, safety awareness,
    and persistent conversation memory that learns about the user over time."""

    # Patterns for extracting personal facts from conversation
    _FACT_PATTERNS = [
        # Family
        (r"my (daughter|son|wife|husband|sister|brother|mother|father|grandchild|grandson|granddaughter|nephew|niece|aunt|uncle|cousin)\b.*?(?:is |named |called |'s name is )(\w+)", "family"),
        (r"my (daughter|son|wife|husband|sister|brother|mother|father|grandchild|grandson|granddaughter)\b.*?(visits?|comes?|calls?|lives?)", "family"),
        (r"my (dog|cat|bird|pet|fish|rabbit|parrot)\b.*?(?:is |named |called |'s name is )(\w+)", "pet"),
        (r"i have a (dog|cat|bird|pet|fish|rabbit|parrot)\b.*?(?:named |called )(\w+)", "pet"),
        # Personal history
        (r"i (?:used to be|was|worked as|retired from being) (?:a |an )?([\w\s]+?)(?:\.|,|!|\?|$)", "career"),
        (r"i (?:love|enjoy|like|adore) ([\w\s]+?)(?:\.|,|!|\?|$)", "interest"),
        (r"my favorite ([\w\s]+?) is ([\w\s]+?)(?:\.|,|!|\?|$)", "preference"),
        (r"i (?:live|lived|grew up) (?:in|at|near) ([\w\s]+?)(?:\.|,|!|\?|$)", "location"),
        (r"i'm (\d+) years old", "age"),
    ]

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
        self._interaction_count = 0
        self._topics_discussed = []
        self._patient_id = "default"
        self._rag_enabled = False
        self._session_start_time = None

        # Initialize RAG memory if available
        try:
            import memory as mem
            mem.init_memory_db()
            self._rag_enabled = True
            print("[BRAIN] RAG memory system enabled")
        except Exception as e:
            print(f"[BRAIN] RAG memory not available: {e}")

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
        import time as _time
        if not self._session_start_time:
            self._session_start_time = _time.time()

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

        # Build context for the LLM (includes RAG memories)
        context = self._build_context(emotion, loneliness, confusion, user_text)

        if self.client is None:
            response = self._smart_fallback(emotion, loneliness, confusion)
            self._store_rag_turn(user_text, response, emotion)
            return response

        # Augment the user message with emotional + situational context
        augmented = f"[{context}] {user_text}"
        self.history.append({"role": "user", "content": augmented})

        # Add a greeting nudge for the first message
        if self.session_start:
            # Include past session context if available
            greeting_ctx = "This is the start of the conversation. Greet them warmly and ask how they're doing today."
            if self._rag_enabled:
                try:
                    import memory as mem
                    summaries = mem.get_recent_summaries(self._patient_id, limit=1)
                    if summaries:
                        last = summaries[0]
                        greeting_ctx += f" In your last session, the dominant mood was {last.get('mood_distribution', '{}')}. Reference something from before if relevant."
                except Exception:
                    pass
            self.history.append({"role": "system", "content": greeting_ctx})
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

            # Store this turn in RAG memory
            self._store_rag_turn(user_text, reply, emotion)

            return reply
        except Exception as e:
            print(f"[BRAIN] LLM error: {e}")
            response = self._smart_fallback(emotion, loneliness, confusion)
            self._store_rag_turn(user_text, response, emotion)
            return response

    def _store_rag_turn(self, user_text: str, response: str, emotion: str):
        """Store conversation turn in RAG memory (background, non-blocking)."""
        if not self._rag_enabled:
            return
        try:
            import memory as mem
            mem.process_conversation_turn(user_text, response, emotion, self._patient_id)
        except Exception as e:
            print(f"[BRAIN] RAG store error: {e}")

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
        """Track emotional trajectory and extract personal facts."""
        self.mood_history.append(emotion)
        self._interaction_count += 1

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

        # Extract personal facts from conversation
        self._extract_facts(text)

    def _extract_facts(self, text: str):
        """Extract personal facts from user's speech using pattern matching."""
        lower = text.lower()

        # Simple keyword-based fact extraction (works without LLM)
        fact_triggers = {
            "family": ["my daughter", "my son", "my wife", "my husband",
                        "my sister", "my brother", "my mother", "my father",
                        "my grandchild", "my grandson", "my granddaughter"],
            "pet": ["my dog", "my cat", "my bird", "my pet", "my rabbit",
                    "i have a dog", "i have a cat", "i have a bird", "i have a pet"],
            "career": ["i used to be", "i was a", "i worked as", "i retired from",
                        "i used to work"],
            "interest": ["i love", "i enjoy", "i like", "my hobby is",
                          "i'm passionate about"],
            "preference": ["my favorite", "i prefer", "i always liked"],
            "location": ["i live in", "i lived in", "i grew up in",
                          "i'm from", "i am from"],
            "health": ["i have diabetes", "i have arthritis", "my back hurts",
                        "i take medication for", "i was diagnosed with"],
        }

        for category, triggers in fact_triggers.items():
            for trigger in triggers:
                if trigger in lower:
                    # Extract the relevant sentence fragment
                    idx = lower.index(trigger)
                    # Get up to 80 chars from the trigger point
                    snippet = text[idx:idx + 80].split(".")[0].split("!")[0].split("?")[0].strip()
                    if snippet and snippet not in self.user_facts:
                        self.user_facts.append(snippet)
                        print(f"[BRAIN] Learned fact ({category}): {snippet}")
                        # Keep max 20 facts
                        if len(self.user_facts) > 20:
                            self.user_facts = self.user_facts[-20:]
                    break  # one fact per category per message

    def _build_context(self, emotion: str, loneliness: bool, confusion: bool, user_text: str = "") -> str:
        """Build a rich context string for the LLM, including RAG memories."""
        parts = [f"User seems {emotion}"]

        if loneliness:
            parts.append("showing signs of loneliness")
        if confusion:
            parts.append("may be confused or disoriented — be extra gentle and patient")
        if self.consecutive_sad >= 3:
            parts.append("has been sad for several messages — check in on them more deeply")
        if self.user_name:
            parts.append(f"user's name is {self.user_name}")

        # Include learned facts for personalized responses
        if self.user_facts:
            facts_str = "; ".join(self.user_facts[-5:])  # last 5 facts
            parts.append(f"things you remember about them: {facts_str}")

        # RAG: retrieve relevant memories from past sessions
        if self._rag_enabled and user_text:
            try:
                import memory as mem
                rag_context = mem.build_memory_context(user_text, self._patient_id)
                if rag_context:
                    parts.append(f"from past sessions: {rag_context}")
            except Exception as e:
                print(f"[BRAIN] RAG recall error: {e}")

        # Mood trajectory
        if len(self.mood_history) >= 3:
            recent = self.mood_history[-3:]
            if recent[0] in ("sadness", "fear") and recent[-1] == "joy":
                parts.append("mood is improving — acknowledge the positive shift")
            elif recent[0] == "joy" and recent[-1] in ("sadness", "fear"):
                parts.append("mood is declining — be extra attentive")

        # Conversation depth — adjust style based on how long we've been talking
        if self._interaction_count > 15:
            parts.append("you've been chatting for a while — feel free to be more personal and relaxed")
        elif self._interaction_count < 3:
            parts.append("conversation just started — be warm and welcoming")

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

        # Use learned facts to personalize responses when possible
        if self.user_facts and emotion == "neutral" and random.random() < 0.3:
            fact = random.choice(self.user_facts)
            return f"You know, I was thinking about what you told me — {fact}. Would you like to tell me more about that?"

        # Regular emotion-based response with variety
        options = RESPONSES.get(emotion, RESPONSES["neutral"])
        return random.choice(options)

    def get_session_summary(self) -> dict:
        """Generate a summary of the current conversation session."""
        import time as _time
        mood_counts = {}
        for m in self.mood_history:
            mood_counts[m] = mood_counts.get(m, 0) + 1
        dominant_mood = max(mood_counts, key=mood_counts.get) if mood_counts else "unknown"

        duration = 0
        if self._session_start_time:
            duration = (_time.time() - self._session_start_time) / 60

        summary = {
            "interactions": self._interaction_count,
            "dominant_mood": dominant_mood,
            "mood_distribution": mood_counts,
            "user_name": self.user_name,
            "facts_learned": len(self.user_facts),
            "user_facts": self.user_facts[:],
            "duration_minutes": round(duration, 1),
            "consecutive_sad_peak": max(
                (sum(1 for _ in g) for k, g in __import__("itertools").groupby(self.mood_history) if k == "sadness"),
                default=0,
            ),
        }

        # Save to RAG memory for cross-session continuity
        if self._rag_enabled and self._interaction_count > 0:
            try:
                import memory as mem
                summary_text = (
                    f"{self._interaction_count} interactions, "
                    f"dominant mood: {dominant_mood}, "
                    f"duration: {summary['duration_minutes']}min"
                )
                if self.user_name:
                    summary_text += f", patient: {self.user_name}"
                if self.user_facts:
                    summary_text += f", learned: {'; '.join(self.user_facts[:3])}"

                mem.save_session_summary(
                    summary=summary_text,
                    mood_distribution=mood_counts,
                    facts_learned=self.user_facts,
                    duration_minutes=summary["duration_minutes"],
                    patient_id=self._patient_id,
                )
                print("[BRAIN] Session summary saved to RAG memory")
            except Exception as e:
                print(f"[BRAIN] Failed to save session summary: {e}")

        return summary
