from __future__ import annotations

"""Conversational AI brain for Reachy -- generates real responses with
mood tracking, safety awareness, and eldercare intelligence."""

import os
import re
import random
from typing import Generator
from brain.followups import get_empathetic_follow_up, handle_short_reply
from core.config import (
    SYSTEM_PROMPT, RESPONSES, SAFETY_KEYWORDS, LONELINESS_KEYWORDS,
    CONFUSION_KEYWORDS, SAFETY_RESPONSE, EMERGENCY_RESPONSE,
)
from core.log_config import get_logger

logger = get_logger("brain")


class Brain:
    """LLM-powered conversation engine with emotional memory, safety awareness,
    topic tracking, and persistent conversation memory that learns about the user over time."""

    # Topic categories for tracking conversation flow
    _TOPIC_KEYWORDS = {
        "family": ["daughter", "son", "wife", "husband", "sister", "brother", "mother",
                    "father", "grandchild", "grandson", "granddaughter", "family", "kids",
                    "children", "nephew", "niece", "aunt", "uncle", "cousin", "spouse"],
        "health": ["pain", "hurt", "doctor", "hospital", "medicine", "medication", "sick",
                    "tired", "sleep", "headache", "dizzy", "blood pressure", "heart",
                    "arthritis", "diabetes", "surgery", "therapy", "exercise"],
        "memories": ["remember", "used to", "back when", "years ago", "childhood",
                     "young", "growing up", "old days", "war", "school", "wedding"],
        "hobbies": ["garden", "cook", "bake", "read", "book", "music", "sing", "dance",
                    "paint", "knit", "sew", "puzzle", "game", "walk", "bird", "fish"],
        "daily_life": ["breakfast", "lunch", "dinner", "eat", "weather", "today",
                       "morning", "afternoon", "evening", "night", "bed", "bath"],
        "emotions": ["happy", "sad", "angry", "scared", "worried", "anxious", "lonely",
                     "bored", "frustrated", "grateful", "thankful", "miss", "love"],
        "pets": ["dog", "cat", "bird", "pet", "fish", "rabbit", "parrot", "puppy", "kitten"],
    }

    def __init__(self, backend: str = "ollama", profile_prompt: str = "") -> None:
        self.backend = backend
        system = SYSTEM_PROMPT
        if profile_prompt:
            system += "\n\n" + profile_prompt
        self.history = [{"role": "system", "content": system}]
        self.client = None

        # Mood tracking -- remembers emotional trajectory
        self.mood_history = []
        self.user_name = None
        self.user_facts = []  # things we've learned about the user
        self.consecutive_sad = 0
        self.session_start = True
        self._interaction_count = 0
        self._topics_discussed = []  # (topic, timestamp) pairs
        self._current_topic = None
        self._topic_depth = 0  # how many turns on current topic
        self._patient_id = "default"
        self._rag_enabled = False
        self._session_start_time = None
        self._last_response = ""  # avoid repetition

        # Initialize RAG memory if available
        try:
            import memory.memory as mem
            mem.init_memory_db()
            self._rag_enabled = True
            logger.info("RAG memory system enabled")
        except Exception as e:
            logger.debug("RAG memory not available: %s", e)

        if backend == "openai":
            from openai import OpenAI
            self.client = OpenAI()
            self.model = os.getenv("OPENAI_MODEL", "gpt-4o")
            logger.info("Using OpenAI (%s)", self.model)
        elif backend == "ollama":
            from openai import OpenAI
            self.client = OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama",
            )
            self.model = os.getenv("OLLAMA_MODEL", "llama3.2")
            logger.info("Using Ollama (%s)", self.model)
        else:
            logger.info("Using enhanced fallback (no LLM)")

        logger.info("Ready")

    def think(self, user_text: str, emotion: str) -> str:
        """Generate a response given user input and detected emotion."""
        import time as _time
        if not self._session_start_time:
            self._session_start_time = _time.time()

        lower = user_text.lower()

        # Safety check first -- always takes priority
        safety_flag = self._check_safety(lower)
        if safety_flag == "crisis":
            self._track_mood(emotion, user_text)
            return SAFETY_RESPONSE
        if safety_flag == "emergency":
            self._track_mood(emotion, user_text)
            return EMERGENCY_RESPONSE

        # Track mood and extract facts
        self._track_mood(emotion, user_text)
        self._track_topic(lower)

        if self.client is None:
            loneliness = self._check_loneliness(lower)
            confusion = self._check_confusion(lower)
            response = self._smart_fallback(emotion, loneliness, confusion, user_text)
            self._store_rag_turn(user_text, response, emotion)
            self._last_response = response
            return response

        # Strip [CONTEXT:...] and [LIVE DATA:...] from user text for display,
        # but keep them in the message to GPT
        clean_text = re.sub(r'\n?\[(?:CONTEXT|LIVE DATA):.*?\]', '', user_text).strip()

        # Build a lean context — just the essentials, not a wall of instructions
        context_parts = []
        if emotion != "neutral":
            context_parts.append(f"emotion: {emotion}")
        if self.user_name:
            context_parts.append(f"name: {self.user_name}")

        # Add key memories only (not everything)
        if self.user_facts:
            context_parts.append(f"known facts: {'; '.join(self.user_facts[-5:])}")

        # RAG memory — past session context
        if self._rag_enabled and clean_text:
            try:
                import memory.memory as mem
                rag_context = mem.build_memory_context(clean_text, self._patient_id)
                if rag_context:
                    context_parts.append(f"past sessions: {rag_context}")
            except Exception:
                pass

        # Vector memory — semantic recall
        try:
            import memory.vector_memory as vmem
            if vmem.is_available() and clean_text:
                vec_context = vmem.build_context(clean_text, self._patient_id)
                if vec_context:
                    context_parts.append(vec_context)
        except Exception:
            pass

        # Knowledge graph
        try:
            import memory.knowledge_graph as kg
            if kg.is_available():
                kg_context = kg.build_context(self._patient_id)
                if kg_context:
                    context_parts.append(kg_context)
        except Exception:
            pass

        # Supabase cross-session data (cached, refreshed every 5 turns)
        self._refresh_supabase_cache()
        supa_ctx = self._get_supabase_context_string()
        if supa_ctx:
            context_parts.append(supa_ctx)

        # Build the message — context as a system message, user text clean
        if context_parts:
            ctx_msg = "Context about this person: " + "; ".join(context_parts)
            # Only inject context system message every 3 turns to keep it clean
            if self._interaction_count % 3 == 0 or self._interaction_count < 3:
                self.history.append({"role": "system", "content": ctx_msg})

        self.history.append({"role": "user", "content": user_text})

        # Session start greeting
        if self.session_start:
            greeting_ctx = self._build_greeting_context()
            self.history.insert(-1, {"role": "system", "content": greeting_ctx})
            self.session_start = False

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                max_tokens=300,
                temperature=0.8,
                presence_penalty=0.5,
                frequency_penalty=0.3,
            )
            reply = resp.choices[0].message.content.strip()

            # Clean up any leaked context markers
            reply = re.sub(r'\[.*?\]\s*', '', reply).strip() if reply.startswith('[') else reply

            self.history.append({"role": "assistant", "content": reply})

            # Keep history manageable (system + last 40 exchanges)
            if len(self.history) > 81:
                self.history = [self.history[0]] + self.history[-80:]

            self._store_rag_turn(clean_text, reply, emotion)
            self._last_response = reply
            return reply
        except Exception as e:
            logger.error("LLM error: %s", e)
            loneliness = self._check_loneliness(lower)
            confusion = self._check_confusion(lower)
            response = self._smart_fallback(emotion, loneliness, confusion, user_text)
            self._store_rag_turn(clean_text, response, emotion)
            self._last_response = response
            return response

    def think_stream(self, user_text: str, emotion: str) -> "Generator[str, None, None]":
        """Stream GPT response, yielding complete sentences as they arrive.
        Falls back to regular think() if streaming isn't available."""
        import time as _time
        if not self._session_start_time:
            self._session_start_time = _time.time()

        lower = user_text.lower()

        # Safety check
        safety_flag = self._check_safety(lower)
        if safety_flag == "crisis":
            self._track_mood(emotion, user_text)
            yield SAFETY_RESPONSE
            return
        if safety_flag == "emergency":
            self._track_mood(emotion, user_text)
            yield EMERGENCY_RESPONSE
            return

        self._track_mood(emotion, user_text)
        self._track_topic(lower)

        if self.client is None:
            loneliness = self._check_loneliness(lower)
            confusion = self._check_confusion(lower)
            response = self._smart_fallback(emotion, loneliness, confusion, user_text)
            self._store_rag_turn(user_text, response, emotion)
            self._last_response = response
            yield response
            return

        clean_text = re.sub(r'\n?\[(?:CONTEXT|LIVE DATA):.*?\]', '', user_text).strip()

        # Build context (same as think())
        context_parts = []
        if emotion != "neutral":
            context_parts.append(f"emotion: {emotion}")
        if self.user_name:
            context_parts.append(f"name: {self.user_name}")
        if self.user_facts:
            context_parts.append(f"known facts: {'; '.join(self.user_facts[-5:])}")
        if self._rag_enabled and clean_text:
            try:
                import memory.memory as mem
                rag_context = mem.build_memory_context(clean_text, self._patient_id)
                if rag_context:
                    context_parts.append(f"past sessions: {rag_context}")
            except Exception:
                pass
        try:
            import memory.vector_memory as vmem
            if vmem.is_available() and clean_text:
                vec_context = vmem.build_context(clean_text, self._patient_id)
                if vec_context:
                    context_parts.append(vec_context)
        except Exception:
            pass
        try:
            import memory.knowledge_graph as kg
            if kg.is_available():
                kg_context = kg.build_context(self._patient_id)
                if kg_context:
                    context_parts.append(kg_context)
        except Exception:
            pass
        self._refresh_supabase_cache()
        supa_ctx = self._get_supabase_context_string()
        if supa_ctx:
            context_parts.append(supa_ctx)

        if context_parts:
            ctx_msg = "Context about this person: " + "; ".join(context_parts)
            if self._interaction_count % 3 == 0 or self._interaction_count < 3:
                self.history.append({"role": "system", "content": ctx_msg})

        self.history.append({"role": "user", "content": user_text})

        if self.session_start:
            greeting_ctx = self._build_greeting_context()
            self.history.insert(-1, {"role": "system", "content": greeting_ctx})
            self.session_start = False

        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                max_tokens=300,
                temperature=0.8,
                presence_penalty=0.5,
                frequency_penalty=0.3,
                stream=True,
            )

            full_reply = ""
            sentence_buffer = ""

            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    token = delta.content
                    full_reply += token
                    sentence_buffer += token

                    # Yield complete sentences as they form
                    # Split on sentence-ending punctuation followed by space or end
                    while True:
                        # Find the earliest sentence boundary
                        best = -1
                        for sep in [". ", "! ", "? ", ".\n", "!\n", "?\n"]:
                            idx = sentence_buffer.find(sep)
                            if idx != -1 and (best == -1 or idx < best):
                                best = idx
                                best_len = len(sep)
                        if best == -1:
                            break
                        sentence = sentence_buffer[:best + best_len].strip()
                        sentence_buffer = sentence_buffer[best + best_len:]
                        if sentence:
                            # Clean context markers
                            sentence = re.sub(r'\[.*?\]\s*', '', sentence).strip()
                            if sentence:
                                yield sentence

            # Yield any remaining text
            remaining = sentence_buffer.strip()
            if remaining:
                remaining = re.sub(r'\[.*?\]\s*', '', remaining).strip()
                if remaining:
                    yield remaining

            # Clean full reply and store
            full_reply = re.sub(r'\[.*?\]\s*', '', full_reply).strip() if full_reply.startswith('[') else full_reply.strip()
            self.history.append({"role": "assistant", "content": full_reply})
            if len(self.history) > 81:
                self.history = [self.history[0]] + self.history[-80:]
            self._store_rag_turn(clean_text, full_reply, emotion)
            self._last_response = full_reply

        except Exception as e:
            logger.error("Stream error: %s", e)
            loneliness = self._check_loneliness(lower)
            confusion = self._check_confusion(lower)
            response = self._smart_fallback(emotion, loneliness, confusion, user_text)
            self._store_rag_turn(clean_text, response, emotion)
            self._last_response = response
            yield response

    def _store_rag_turn(self, user_text: str, response: str, emotion: str) -> None:
        """Store conversation turn in RAG memory (background, non-blocking)."""
        if not self._rag_enabled:
            return
        try:
            import memory.memory as mem
            mem.process_conversation_turn(user_text, response, emotion, self._patient_id)
        except Exception as e:
            logger.error("RAG store error: %s", e)

    def _refresh_supabase_cache(self) -> None:
        """Refresh Supabase context cache every 5 interactions."""
        if not hasattr(self, '_supa_cache'):
            self._supa_cache = {}
            self._supa_cache_turn = -1
        if self._interaction_count - self._supa_cache_turn >= 5 or self._supa_cache_turn < 0:
            self._supa_cache_turn = self._interaction_count
            try:
                import memory.db_supabase as _db
                if _db.is_available():
                    self._supa_cache = {
                        'profile': _db.get_profile(self._patient_id),
                        'facts': _db.get_facts(self._patient_id),
                        'mentions': _db.get_mentions(self._patient_id),
                        'streak': _db.get_streak(self._patient_id),
                        'sessions': _db.get_session_summaries(self._patient_id, limit=1),
                    }
                    # Learn name from profile
                    profile = self._supa_cache.get('profile', {})
                    pname = (profile.get("preferred_name") or profile.get("name", "")).strip()
                    if pname and not self.user_name:
                        self.user_name = pname
                    # Merge saved facts
                    for f in self._supa_cache.get('facts', []):
                        if f.get("fact") and f["fact"] not in self.user_facts:
                            self.user_facts.append(f["fact"])
            except Exception as e:
                logger.warning("Supabase cache error: %s", e)

    def _get_supabase_context_string(self) -> str:
        """Build a concise context string from cached Supabase data."""
        parts = []
        sc = getattr(self, '_supa_cache', {})
        if not sc:
            return ""
        try:
            mentions = sc.get('mentions', {})
            if mentions:
                for cat, items in mentions.items():
                    if items:
                        parts.append(f"{cat}: {', '.join(items[:3])}")
            streak = sc.get('streak', 0)
            if streak >= 2:
                parts.append(f"chatted {streak} days in a row")
            sessions = sc.get('sessions', [])
            if sessions:
                last = sessions[0]
                topics = last.get("topics_discussed", [])
                if topics:
                    parts.append(f"last time talked about: {', '.join(topics[:3])}")
        except Exception:
            pass
        return "; ".join(parts) if parts else ""

    def _build_greeting_context(self) -> str:
        """Build a context-aware greeting prompt for the start of a session."""
        import time as _time
        hour = int(_time.strftime("%H"))
        if hour < 12:
            time_greeting = "It's morning"
        elif hour < 17:
            time_greeting = "It's afternoon"
        else:
            time_greeting = "It's evening"

        ctx = (
            f"This is the start of the conversation. {time_greeting}. "
            "Greet them warmly and naturally -- like a friend who's happy to see them. "
            "Ask how they're doing. Keep it to 1-2 sentences."
        )

        if self.user_name:
            ctx += f" Their name is {self.user_name} -- use it."

        # Pull cross-session context from Supabase
        try:
            import memory.db_supabase as _db
            if _db.is_available():
                profile = _db.get_profile(self._patient_id)
                pname = (profile.get("preferred_name") or profile.get("name", "")).strip()
                if pname:
                    self.user_name = pname
                    ctx += f" Their name is {pname} -- use it."

                streak = _db.get_streak(self._patient_id)
                if streak >= 2:
                    ctx += f" You've chatted {streak} days in a row -- mention it to encourage them."

                mentions = _db.get_mentions(self._patient_id)
                people = mentions.get("people", [])
                if people:
                    ctx += f" They've mentioned: {', '.join(people[:3])}. Reference one naturally."

                sessions = _db.get_session_summaries(self._patient_id, limit=1)
                if sessions:
                    last = sessions[0]
                    topics = last.get("topics_discussed", [])
                    mood = last.get("dominant_mood", "")
                    if topics:
                        ctx += f" Last time you talked about {', '.join(topics[:2])}."
                    if mood == "sadness":
                        ctx += " Last session was a bit tough for them -- check in gently."
                    elif mood == "joy":
                        ctx += " They were in good spirits last time -- keep the energy up."
        except Exception:
            pass

        return ctx

    def _track_topic(self, text: str) -> None:
        """Detect and track the current conversation topic."""
        import time as _time
        detected = None
        max_hits = 0
        for topic, keywords in self._TOPIC_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in text)
            if hits > max_hits:
                max_hits = hits
                detected = topic

        if detected:
            if detected == self._current_topic:
                self._topic_depth += 1
            else:
                self._current_topic = detected
                self._topic_depth = 1
                self._topics_discussed.append((detected, _time.time()))
                # Keep last 20 topic transitions
                if len(self._topics_discussed) > 20:
                    self._topics_discussed = self._topics_discussed[-20:]

    def _check_safety(self, text: str) -> str:
        """Check for crisis or emergency keywords."""
        emergency_words = ["chest pain", "can't breathe", "stroke", "bleeding",
                           "can't get up", "fell down", "fallen", "emergency", "help me"]
        crisis_words = ["don't want to live", "want to die", "kill myself",
                        "end it all", "hurt myself", "suicide", "can't go on"]

        for word in crisis_words:
            if word in text:
                logger.warning("CRISIS keywords detected")
                return "crisis"
        for word in emergency_words:
            if word in text:
                logger.warning("EMERGENCY keywords detected")
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

    def _track_mood(self, emotion: str, text: str) -> None:
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
            # Only match explicit name introductions, not "I'm bored/tired/hungry/etc."
            _not_names = {
                "bored", "tired", "hungry", "thirsty", "scared", "worried",
                "happy", "sad", "angry", "fine", "good", "great", "okay", "ok",
                "sick", "cold", "hot", "lonely", "confused", "lost", "sorry",
                "excited", "nervous", "anxious", "sleepy", "awake", "back",
                "here", "home", "ready", "done", "not", "so", "very", "really",
                "just", "feeling", "doing", "going", "looking", "trying",
            }
            for prefix in ["my name is ", "call me "]:
                if prefix in lower:
                    idx = lower.index(prefix) + len(prefix)
                    name = text[idx:].split()[0].strip(".,!?")
                    if (len(name) > 1 and name.isalpha()
                            and name.lower() not in _not_names):
                        self.user_name = name.capitalize()
                        logger.info("Learned user name: %s", self.user_name)
            # "I'm X" only if followed by nothing or a period (not "I'm bored today")
            if not self.user_name and "i'm " in lower:
                idx = lower.index("i'm ") + 4
                rest = text[idx:].strip()
                name = rest.split()[0].strip(".,!?") if rest else ""
                words_after = rest.split()
                # Only accept as name if it's the only word or followed by punctuation
                if (len(name) > 1 and name.isalpha()
                        and name.lower() not in _not_names
                        and name[0].isupper()
                        and len(words_after) <= 2):
                    self.user_name = name
                    logger.info("Learned user name: %s", self.user_name)

        # Extract personal facts from conversation
        self._extract_facts(text)

    def _extract_facts(self, text: str) -> None:
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
                        logger.info("Learned fact (%s): %s", category, snippet)
                        # Save to Supabase
                        try:
                            import memory.db_supabase as _db
                            if _db.is_available():
                                _db.save_fact(category, snippet)
                        except Exception:
                            pass
                        # Keep max 20 facts
                        if len(self.user_facts) > 20:
                            self.user_facts = self.user_facts[-20:]
                    break  # one fact per category per message

    def _get_adaptive_strategy(self, emotion: str, loneliness: bool, confusion: bool) -> str:
        """Return an emotion-adaptive conversation strategy directive."""
        # Determine dominant recent mood
        recent_moods = self.mood_history[-5:] if len(self.mood_history) >= 5 else self.mood_history
        mood_counts = {}
        for m in recent_moods:
            mood_counts[m] = mood_counts.get(m, 0) + 1
        dominant = max(mood_counts, key=mood_counts.get) if mood_counts else "neutral"

        strategies = {
            "sadness": (
                "STRATEGY: Use shorter, gentler sentences. Ask open-ended questions about feelings. "
                "Don't try to fix -- just be present. Offer comfort activities (music, stories, breathing). "
                "Validate every emotion before suggesting anything."
            ),
            "fear": (
                "STRATEGY: Ground them with calm, steady language. Offer breathing exercises. "
                "Reassure without dismissing. Use phrases like 'you're safe here' and 'let's take it slow'. "
                "Avoid introducing new topics -- stay focused on their concern."
            ),
            "anger": (
                "STRATEGY: Validate their frustration first. Don't argue or minimize. "
                "Use phrases like 'that sounds really frustrating' and 'you have every right to feel that way'. "
                "Only suggest solutions after they feel heard."
            ),
            "joy": (
                "STRATEGY: Match their energy. Ask follow-up questions to let them savor the moment. "
                "Be playful and warm. Suggest activities they enjoy. Celebrate with them."
            ),
            "neutral": (
                "STRATEGY: Be warm and engaging. Suggest activities based on time of day. "
                "Ask about their interests. Keep conversation flowing naturally."
            ),
        }

        strategy = strategies.get(dominant, strategies["neutral"])

        if loneliness:
            strategy += " LONELINESS DETECTED: Be extra warm and engaged. Ask about social connections. Remind them you enjoy talking."
        if confusion:
            strategy += " CONFUSION DETECTED: Use very short sentences. Reorient gently. Don't ask complex questions. Be patient with repetition."
        if self.consecutive_sad >= 3:
            strategy += " SUSTAINED DISTRESS: Gently suggest talking to a caregiver or family member. Offer comfort activities."

        return strategy

    def _build_context(self, emotion: str, loneliness: bool, confusion: bool, user_text: str = "") -> str:
        """Build a rich context string for the LLM, including RAG memories, topic tracking, and adaptive strategy."""
        parts = [f"User seems {emotion}"]

        # Emotion-adaptive strategy
        strategy = self._get_adaptive_strategy(emotion, loneliness, confusion)
        parts.append(strategy)

        if self.user_name:
            parts.append(f"user's name is {self.user_name}")

        # Include learned facts for personalized responses
        if self.user_facts:
            facts_str = "; ".join(self.user_facts[-5:])  # last 5 facts
            parts.append(f"things you remember about them: {facts_str}")

        # Topic tracking -- help the LLM maintain conversation flow
        if self._current_topic:
            if self._topic_depth >= 4:
                parts.append(
                    f"you've been discussing {self._current_topic} for a while -- "
                    "it's okay to gently explore a new direction if the conversation naturally allows it"
                )
            elif self._topic_depth >= 2:
                parts.append(f"current topic: {self._current_topic} -- ask a follow-up question to go deeper")

        # RAG: retrieve relevant memories from past sessions
        if self._rag_enabled and user_text:
            try:
                import memory.memory as mem
                rag_context = mem.build_memory_context(user_text, self._patient_id)
                if rag_context:
                    parts.append(f"from past sessions: {rag_context}")
            except Exception as e:
                logger.error("RAG recall error: %s", e)

        # Vector memory: semantic search across all past conversations
        try:
            import memory.vector_memory as vmem
            if vmem.is_available() and user_text:
                vec_context = vmem.build_context(user_text, self._patient_id)
                if vec_context:
                    parts.append(vec_context)
        except Exception as e:
            logger.error("Vector memory recall error: %s", e)

        # Knowledge graph: structured relationships about the patient's world
        try:
            import memory.knowledge_graph as kg
            if kg.is_available():
                kg_context = kg.build_context(self._patient_id)
                if kg_context:
                    parts.append(kg_context)
        except Exception as e:
            logger.error("Knowledge graph error: %s", e)

        # Temporal patterns: trends detected over time
        try:
            import memory.temporal_patterns as tp
            tp_context = tp.build_context(self._patient_id)
            if tp_context:
                parts.append(tp_context)
        except Exception as e:
            logger.error("Temporal patterns error: %s", e)

        # Supabase: enrich context with persistent cross-session data
        # Use cached data — refreshed in background every 5 interactions
        if not hasattr(self, '_supa_cache'):
            self._supa_cache = {}
            self._supa_cache_turn = 0
        if self._interaction_count == 0 or self._interaction_count - self._supa_cache_turn >= 5:
            self._supa_cache_turn = self._interaction_count
            try:
                import memory.db_supabase as _db
                if _db.is_available():
                    self._supa_cache = {
                        'profile': _db.get_profile(self._patient_id),
                        'facts': _db.get_facts(self._patient_id),
                        'mentions': _db.get_mentions(self._patient_id),
                        'mood_counts': _db.get_mood_counts(self._patient_id, days=3),
                        'streak': _db.get_streak(self._patient_id),
                        'sessions': _db.get_session_summaries(self._patient_id, limit=1),
                        'cog_avg': _db.get_cognitive_avg(self._patient_id, days=7),
                    }
            except Exception as e:
                logger.warning("Supabase cache refresh error: %s", e)

        try:
            sc = self._supa_cache
            profile = sc.get('profile')
            if profile:
                pname = profile.get("preferred_name") or profile.get("name")
                if pname and not self.user_name:
                    self.user_name = pname
                    parts.append(f"patient's name is {pname}")
                fav = profile.get("favorite_topic")
                if fav:
                    parts.append(f"their favorite topic is {fav}")
                notes = profile.get("personality_notes")
                if notes:
                    parts.append(f"personality: {notes}")

            saved_facts = sc.get('facts', [])
            if saved_facts:
                fact_strs = [f["fact"] for f in saved_facts[:8]]
                for fs in fact_strs:
                    if fs not in self.user_facts:
                        self.user_facts.append(fs)

            mentions = sc.get('mentions', {})
            if mentions:
                mention_parts = []
                for cat, items in mentions.items():
                    mention_parts.append(f"{cat}: {', '.join(items[:4])}")
                if mention_parts:
                    parts.append(f"things they've mentioned: {'; '.join(mention_parts)}")

            mood_counts = sc.get('mood_counts', {})
            if mood_counts:
                top_moods = sorted(mood_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                trend = ", ".join(f"{m}({c})" for m, c in top_moods)
                parts.append(f"recent mood trend (3 days): {trend}")

            streak = sc.get('streak', 0)
            if streak >= 3:
                parts.append(f"they've chatted {streak} days in a row -- acknowledge their consistency")

            sessions = sc.get('sessions', [])
            if sessions:
                last = sessions[0]
                last_mood = last.get("dominant_mood", "")
                last_topics = last.get("topics_discussed", [])
                if last_mood or last_topics:
                    parts.append(f"last session: mood was {last_mood}, talked about {', '.join(last_topics[:3])}")

            cog_avg = sc.get('cog_avg', 0)
            if cog_avg > 0:
                parts.append(f"cognitive game avg this week: {cog_avg}%")
        except Exception as e:
            logger.error("Supabase context error: %s", e)

        # Mood trajectory
        if len(self.mood_history) >= 3:
            recent = self.mood_history[-3:]
            if recent[0] in ("sadness", "fear") and recent[-1] == "joy":
                parts.append("mood is improving -- acknowledge the positive shift")
            elif recent[0] == "joy" and recent[-1] in ("sadness", "fear"):
                parts.append("mood is declining -- be extra attentive and gentle")

        # Conversation depth -- adjust style based on how long we've been talking
        if self._interaction_count > 20:
            parts.append("you've been chatting for a while -- be more personal, relaxed, and reference earlier parts of the conversation")
        elif self._interaction_count > 10:
            parts.append("conversation is flowing well -- feel free to be more personal")
        elif self._interaction_count < 3:
            parts.append("conversation just started -- be warm and welcoming, keep it light")

        # Time-of-day awareness
        import time as _time
        hour = int(_time.strftime("%H"))
        if hour >= 21 or hour < 6:
            parts.append("it's late -- be calm and soothing, suggest rest if appropriate")
        elif hour < 9:
            parts.append("it's early morning -- be gentle and encouraging")

        return "; ".join(parts)

    def _smart_fallback(self, emotion: str, loneliness: bool, confusion: bool, user_text: str = "") -> str:
        """Enhanced fallback when no LLM is available -- topic-aware with follow-ups."""
        if loneliness:
            responses = [
                "I'm right here with you. You're not alone -- I enjoy our conversations.",
                "I'm glad we're talking. Tell me about something that made you smile recently?",
                "You know, I always look forward to chatting with you. What's on your mind?",
                "I'm here, and I'm not going anywhere. Want to tell me about your day?",
                "Sometimes just having someone to talk to makes all the difference. I'm here.",
            ]
            return random.choice(responses)

        if confusion:
            responses = [
                "That's okay, no rush at all. I'm Reachy, your robot friend. We're just chatting.",
                "No worries. Take your time. I'm right here whenever you're ready.",
                "It's alright. Let's take it easy. Is there anything I can help you with?",
                "Don't worry about it. We're just having a nice chat together.",
            ]
            return random.choice(responses)

        if self.consecutive_sad >= 3:
            return "I've noticed you've been having a tough time. I really care about how you're feeling. Would it help to talk to someone you trust about this?"

        # Topic-aware responses for more natural conversation
        if self._current_topic and random.random() < 0.4:
            topic_responses = {
                "family": [
                    "Family is so important. Tell me more about them.",
                    "It sounds like your family means a lot to you. What's your favorite memory with them?",
                ],
                "health": [
                    "How have you been feeling overall lately?",
                    "Taking care of yourself is important. Have you been getting enough rest?",
                ],
                "memories": [
                    "I love hearing your stories. What else do you remember from that time?",
                    "Those sound like wonderful memories. Tell me more.",
                ],
                "hobbies": [
                    "That sounds like a great way to spend time. How did you get into that?",
                    "I'd love to hear more about that. What do you enjoy most about it?",
                ],
                "pets": [
                    "Pets are such wonderful companions. Tell me more about yours.",
                    "That's sweet. Animals have a way of making everything better, don't they?",
                ],
                "daily_life": [
                    "Sounds like a good day. What are you looking forward to?",
                    "How has the rest of your day been going?",
                ],
            }
            if self._current_topic in topic_responses:
                return random.choice(topic_responses[self._current_topic])

        # Use learned facts to personalize responses when possible
        if self.user_facts and emotion == "neutral" and random.random() < 0.3:
            fact = random.choice(self.user_facts)
            return f"You know, I was thinking about what you told me -- {fact}. Would you like to tell me more about that?"

        # Try a follow-up question for more natural conversation
        if user_text:
            # Handle short replies like "yes", "no", "yeah"
            short_reply = handle_short_reply(user_text)
            if short_reply:
                return short_reply
            follow_up = get_empathetic_follow_up(user_text)
            if follow_up and random.random() < 0.5:
                return follow_up

        # Regular emotion-based response with variety
        options = RESPONSES.get(emotion, RESPONSES["neutral"])
        return random.choice(options)

    def save_history(self) -> None:
        """Persist conversation history + learned facts to Supabase."""
        try:
            import memory.db_supabase as _db
            if not _db.is_available():
                return
            # Only save user/assistant messages (skip system messages — they're rebuilt)
            saveable = [m for m in self.history if m.get("role") in ("user", "assistant")]
            # Keep last 40 exchanges (80 messages) to avoid bloat
            if len(saveable) > 80:
                saveable = saveable[-80:]
            _db.save_chat_history(
                history=saveable,
                user_name=self.user_name or "",
                user_facts=self.user_facts,
                patient_id=self._patient_id,
            )
            logger.info("Saved %d messages to Supabase", len(saveable))
        except Exception as e:
            logger.error("save_history error: %s", e)

    def restore_history(self) -> None:
        """Restore conversation history from Supabase (call once at startup)."""
        try:
            import memory.db_supabase as _db
            if not _db.is_available():
                return False
            data = _db.get_chat_history(self._patient_id)
            if not data or not data.get("history"):
                logger.info("No previous history found in Supabase")
                return False
            # Restore messages — keep system prompt as-is, append saved user/assistant turns
            saved = data["history"]
            # Filter to only user/assistant (safety check)
            restored = [m for m in saved if m.get("role") in ("user", "assistant")]
            if restored:
                self.history.extend(restored)
                logger.info("Restored %d messages from last session", len(restored))
            # Restore name and facts
            if data.get("user_name") and not self.user_name:
                self.user_name = data["user_name"]
                logger.info("Restored user name: %s", self.user_name)
            if data.get("user_facts"):
                for fact in data["user_facts"]:
                    if fact and fact not in self.user_facts:
                        self.user_facts.append(fact)
                if self.user_facts:
                    logger.info("Restored %d facts", len(self.user_facts))
            return True
        except Exception as e:
            logger.error("restore_history error: %s", e)
            return False

    def get_session_summary(self) -> dict:
        """Generate a summary of the current conversation session."""

        # Persist conversation history to Supabase before summarizing
        self.save_history()

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
            "topics_discussed": list(set(t[0] for t in self._topics_discussed)),
            "duration_minutes": round(duration, 1),
            "consecutive_sad_peak": max(
                (sum(1 for _ in g) for k, g in __import__("itertools").groupby(self.mood_history) if k == "sadness"),
                default=0,
            ),
        }

        # Save to RAG memory for cross-session continuity
        if self._rag_enabled and self._interaction_count > 0:
            try:
                import memory.memory as mem
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
                logger.info("Session summary saved to RAG memory")
            except Exception as e:
                logger.error("Failed to save session summary: %s", e)

        # Save to Supabase
        if self._interaction_count > 0:
            try:
                import memory.db_supabase as _db
                if _db.is_available():
                    _db.save_session_summary(
                        interactions=self._interaction_count,
                        dominant_mood=dominant_mood,
                        mood_distribution=mood_counts,
                        topics_discussed=summary["topics_discussed"],
                        facts_learned=self.user_facts,
                        duration_minutes=summary["duration_minutes"],
                        patient_id=self._patient_id,
                    )
                    logger.info("Session summary saved to Supabase")
            except Exception as e:
                logger.error("Supabase session save failed: %s", e)

        return summary
