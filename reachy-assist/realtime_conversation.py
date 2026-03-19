"""Full-duplex voice conversation using OpenAI Realtime API.

Full integration with Reachy's memory, knowledge graph, vector embeddings,
caregiver alerts, weather, temporal patterns, and session persistence.

Speaker-bleed mitigation:
  MacBook mic picks up its own speakers at 0.10-0.30 RMS. Mic sending is
  fully muted while Reachy speaks, then cleanly resumed after a handoff
  sequence (wait → clear buffer → inject silence → clear again → unmute).

Usage:
    from realtime_conversation import RealtimeConversation
    conv = RealtimeConversation(system_prompt="...", voice="shimmer")
    conv.start()
"""

import asyncio
import base64
import json
import os
import queue
import threading
import time
import numpy as np

SAMPLE_RATE = 24000
FRAME_MS = 20
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)
INPUT_RATE = 24000

# ── Safety keywords ───────────────────────────────────────────────

_CRISIS_KEYWORDS = [
    "don't want to live", "want to die", "kill myself", "end it all",
    "hurt myself", "suicide", "can't go on", "no reason to live",
    "better off dead", "wish i was dead",
]
_EMERGENCY_KEYWORDS = [
    "chest pain", "can't breathe", "stroke", "bleeding", "can't get up",
    "fell down", "fallen", "emergency", "help me", "heart attack",
    "choking", "seizure",
]
_CARE_REQUEST_KEYWORDS = {
    "medication": ["my medication", "my medicine", "my pills", "need my meds",
                   "time for my medication", "forgot my medicine"],
    "food": ["i'm hungry", "i'm thirsty", "need water", "need food",
             "haven't eaten", "need a drink", "need something to eat"],
    "help": ["need help", "can you help", "call someone", "get my nurse",
             "get my caregiver", "i need assistance", "call my daughter",
             "call my son", "call my family"],
}
_WANDERING_KEYWORDS = [
    "where am i", "i want to go home", "i don't know this place",
    "i don't recognize", "this isn't my house", "take me home",
    "i need to go home", "how do i get home", "i'm lost",
    "where is this", "i don't belong here", "this isn't where i live",
    "who brought me here", "i want to leave", "where's my room",
    "i don't know where i am", "what is this place",
]

# ── Topic keywords (same as brain.py) ────────────────────────────

_TOPIC_KEYWORDS = {
    "family": ["daughter", "son", "wife", "husband", "sister", "brother",
               "mother", "father", "grandchild", "grandson", "granddaughter",
               "family", "kids", "children", "nephew", "niece"],
    "health": ["pain", "hurt", "doctor", "hospital", "medicine", "medication",
               "sick", "tired", "sleep", "headache", "dizzy", "blood pressure",
               "heart", "arthritis", "diabetes", "surgery", "therapy"],
    "memories": ["remember", "used to", "back when", "years ago", "childhood",
                 "young", "growing up", "old days", "war", "school", "wedding"],
    "hobbies": ["garden", "cook", "bake", "read", "book", "music", "sing",
                "dance", "paint", "knit", "sew", "puzzle", "game", "walk",
                "bird", "fish", "sports", "baseball", "football"],
    "daily_life": ["breakfast", "lunch", "dinner", "eat", "weather", "today",
                   "morning", "afternoon", "evening", "night", "bed", "bath"],
    "emotions": ["happy", "sad", "angry", "scared", "worried", "anxious",
                 "lonely", "bored", "frustrated", "grateful", "miss", "love"],
    "pets": ["dog", "cat", "bird", "pet", "fish", "rabbit", "puppy", "kitten"],
}


class RealtimeConversation:
    def __init__(
        self,
        system_prompt: str = "",
        voice: str = "shimmer",
        patient_id: str = "default",
        on_transcript_done=None,
        on_user_transcript=None,
        on_interrupt=None,
    ):
        self.system_prompt = system_prompt
        self.voice = voice
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.model = "gpt-4o-realtime-preview"
        self._patient_id = patient_id

        # Callbacks
        self._on_transcript_done = on_transcript_done
        self._on_user_transcript = on_user_transcript
        self._on_interrupt = on_interrupt

        # Playback
        self._playback_q = queue.Queue()
        self._stop_playback = threading.Event()

        # Mic gating
        self._mic_muted = threading.Event()

        # State
        self._ws = None
        self._running = False
        self._loop = None
        self._reachy_speaking = False
        self._unmute_time = 0.0

        # Conversation tracking
        self._interaction_count = 0
        self._mood_history = []
        self._consecutive_sad = 0
        self._user_name = None
        self._user_facts = []
        self._chat_history = []
        self._topics_discussed = []
        self._current_topic = None
        self._session_start_time = None
        self._conversation_turns = []  # (speaker, text, emotion) for summarization
        self._consecutive_short = 0  # track short replies for stall detection
        self._consecutive_mood_turns = 0  # track sustained mood for music offers
        self._last_mood_direction = ""  # "sad" or "happy"
        self._music_offered = False  # only offer once per mood streak

        # Backend state
        self._db_available = False
        self._rag_enabled = False
        self._vec_available = False
        self._kg_available = False
        self._alerts = None  # CaregiverAlerts instance
        self._robot = None   # Robot instance
        self._dashboard_url = os.environ.get("DASHBOARD_URL", "http://localhost:5555")
        self._pending_cg_messages = []
        self._cg_lock = threading.Lock()
        self._med_reminded = set()  # track which reminders we already prompted this session
        self._pain_followup_active = False  # avoid re-triggering during pain follow-up
        self._pain_followup_cooldown = 0  # turns remaining before pain detection re-enables
        self._gratitude_session = None  # active GratitudeSession instance
        self._sundowning_count = 0  # evening confusion keyword hits this session
        self._interactive_story = None  # active InteractiveStory instance
        self._personal_quiz = None  # active PersonalQuiz instance
        self._singalong = None  # active SingAlong instance
        self._session_alert_count = 0  # alert escalation counter

    # ── Public API ────────────────────────────────────────────────

    def start(self):
        self._running = True
        self._session_start_time = time.time()
        self._init_backend()
        try:
            asyncio.run(self._run())
        except KeyboardInterrupt:
            print("\n[REALTIME] Shutting down...")
        finally:
            self._running = False
            self._shutdown()

    def stop(self):
        self._running = False

    # ── Backend init ──────────────────────────────────────────────

    def _init_backend(self):
        """Initialize all backend systems."""
        # Supabase
        try:
            import db_supabase as _db
            if _db.init_bot_tables():
                self._db_available = True
                print("[REALTIME] Supabase connected")
        except Exception as e:
            print(f"[REALTIME] Supabase not available: {e}")

        # RAG memory
        try:
            import memory as mem
            mem.init_memory_db()
            self._rag_enabled = True
            print("[REALTIME] RAG memory enabled")
        except Exception as e:
            print(f"[REALTIME] RAG memory not available: {e}")

        # Vector memory
        try:
            import vector_memory as vmem
            if vmem.init():
                self._vec_available = True
        except Exception as e:
            print(f"[REALTIME] Vector memory not available: {e}")

        # Knowledge graph
        try:
            import knowledge_graph as kg
            if kg.init():
                self._kg_available = True
        except Exception as e:
            print(f"[REALTIME] Knowledge graph not available: {e}")

        # Caregiver alerts
        try:
            from caregiver import CaregiverAlerts
            self._alerts = CaregiverAlerts()
        except Exception as e:
            print(f"[REALTIME] Caregiver alerts not available: {e}")

        # Robot (hardware or simulation)
        try:
            from robot import Robot
            self._robot = Robot()
            self._robot.connect()
            # Start teleoperation API
            try:
                from webapp import start_server as start_robot_api
                start_robot_api(robot=self._robot, port=5557)
            except Exception as e2:
                print(f"[REALTIME] Robot API not available: {e2}")
        except Exception as e:
            print(f"[REALTIME] Robot not available: {e}")

        # Restore chat history
        if self._db_available:
            try:
                import db_supabase as _db
                data = _db.get_chat_history(self._patient_id)
                if data and data.get("history"):
                    self._chat_history = [
                        m for m in data["history"]
                        if m.get("role") in ("user", "assistant")
                    ]
                    print(f"[REALTIME] Restored {len(self._chat_history)} messages from last session")
                if data and data.get("user_name"):
                    self._user_name = data["user_name"]
                    print(f"[REALTIME] Restored user name: {self._user_name}")
                if data and data.get("user_facts"):
                    self._user_facts = data["user_facts"]
                    print(f"[REALTIME] Restored {len(self._user_facts)} facts")

                profile = _db.get_profile(self._patient_id)
                pname = (profile.get("preferred_name") or profile.get("name", "")).strip()
                if pname and not self._user_name:
                    self._user_name = pname

                # Merge saved facts from Supabase
                saved_facts = _db.get_facts(self._patient_id)
                for f in saved_facts:
                    if f.get("fact") and f["fact"] not in self._user_facts:
                        self._user_facts.append(f["fact"])

                _db.save_streak_date(self._patient_id)
            except Exception as e:
                print(f"[REALTIME] History restore error: {e}")

    # ── Build instructions with full context ──────────────────────

    def _build_full_instructions(self) -> str:
        parts = [self.system_prompt]

        # Patient identity
        if self._user_name:
            parts.append(f"\nThe patient's name is {self._user_name}. Use it naturally.")

        # Known facts
        if self._user_facts:
            parts.append(f"\nThings you know about them: {'; '.join(self._user_facts[-10:])}")

        # Weather
        try:
            from weather import get_weather
            w = get_weather()
            if w.get("ok"):
                parts.append(
                    f"\n[LIVE DATA: Weather in {w['location']}: {w['description']}, "
                    f"{w['temp_f']}°F, feels like {w['feels_like_f']}°F, "
                    f"humidity {w['humidity']}%]"
                )
        except Exception:
            pass

        # Time context
        now = time.strftime("%A, %B %d, %Y at %I:%M %p")
        parts.append(f"\n[CONTEXT: Current time is {now}]")

        if self._db_available:
            try:
                import db_supabase as _db

                # Mentions
                mentions = _db.get_mentions(self._patient_id)
                if mentions:
                    mention_parts = []
                    for cat, items in mentions.items():
                        mention_parts.append(f"{cat}: {', '.join(items[:5])}")
                    parts.append(f"\nThings they've mentioned: {'; '.join(mention_parts)}")

                # Streak
                streak = _db.get_streak(self._patient_id)
                if streak >= 2:
                    parts.append(f"\nYou've chatted {streak} days in a row — acknowledge their consistency.")

                # Last session
                sessions = _db.get_session_summaries(self._patient_id, limit=2)
                if sessions:
                    last = sessions[0]
                    topics = last.get("topics_discussed", [])
                    mood = last.get("dominant_mood", "")
                    dur = last.get("duration_minutes", 0)
                    summary = last.get("summary_text", "")
                    if summary:
                        parts.append(f"\nLast session notes: {summary}")
                    elif topics:
                        parts.append(f"\nLast time you talked about: {', '.join(topics[:3])}")
                    if mood:
                        parts.append(f"\nLast session mood: {mood}")
                    if dur:
                        parts.append(f"\nLast session lasted {dur:.0f} minutes")

                # Mood trend (last 3 days)
                mood_counts = _db.get_mood_counts(self._patient_id, days=3)
                if mood_counts:
                    top_moods = sorted(mood_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                    trend = ", ".join(f"{m}({c})" for m, c in top_moods)
                    parts.append(f"\nRecent mood trend (3 days): {trend}")

                # Cognitive scores
                cog_avg = _db.get_cognitive_avg(self._patient_id, days=7)
                if cog_avg > 0:
                    parts.append(f"\nCognitive game avg this week: {cog_avg}%")

                # Active reminders
                reminders = _db.get_reminders(self._patient_id, active_only=True)
                if reminders:
                    rem_texts = [r["text"] for r in reminders[:3]]
                    parts.append(f"\nActive reminders: {'; '.join(rem_texts)}")

            except Exception as e:
                print(f"[REALTIME] Supabase context error: {e}")

        # Knowledge graph
        if self._kg_available:
            try:
                import knowledge_graph as kg
                kg_ctx = kg.build_context(self._patient_id)
                if kg_ctx:
                    parts.append(f"\n{kg_ctx}")
            except Exception:
                pass

        # Multi-session story arcs — ongoing storylines from knowledge graph
        if self._kg_available and self._db_available:
            try:
                story_arc = self._build_story_arc_context()
                if story_arc:
                    parts.append(f"\n{story_arc}")
            except Exception:
                pass

        # Temporal patterns
        try:
            import temporal_patterns as tp
            tp_ctx = tp.build_context(self._patient_id)
            if tp_ctx:
                parts.append(f"\n{tp_ctx}")
        except Exception:
            pass

        # Vector memory — semantic recall of past conversations
        if self._vec_available and self._chat_history:
            try:
                import vector_memory as vmem
                # Use the last user message as the query
                last_user = ""
                for msg in reversed(self._chat_history):
                    if msg["role"] == "user":
                        last_user = msg["content"]
                        break
                if last_user:
                    vec_ctx = vmem.build_context(last_user, self._patient_id)
                    if vec_ctx:
                        parts.append(f"\n{vec_ctx}")
            except Exception:
                pass

        # Recent conversation (for continuity)
        if self._chat_history:
            recent = self._chat_history[-8:]
            summary_parts = []
            for msg in recent:
                role = "Patient" if msg["role"] == "user" else "You"
                text = msg["content"][:120]
                summary_parts.append(f"{role}: {text}")
            parts.append(f"\nRecent conversation (for continuity):\n" + "\n".join(summary_parts))

        return "\n".join(parts)

    def _build_greeting_context(self) -> str:
        hour = int(time.strftime("%H"))
        if hour < 12:
            tod = "morning"
        elif hour < 17:
            tod = "afternoon"
        else:
            tod = "evening"

        prompt = f"(The patient just sat down. It's {tod}. Greet them warmly — 1-2 sentences."
        if self._user_name:
            prompt += f" Their name is {self._user_name} — use it."

        if self._db_available:
            try:
                import db_supabase as _db
                streak = _db.get_streak(self._patient_id)
                if streak >= 3:
                    prompt += f" You've chatted {streak} days in a row — mention it."
                sessions = _db.get_session_summaries(self._patient_id, limit=1)
                if sessions:
                    topics = sessions[0].get("topics_discussed", [])
                    mood = sessions[0].get("dominant_mood", "")
                    if topics:
                        prompt += f" Last time you talked about {', '.join(topics[:2])}."
                    if mood == "sadness":
                        prompt += " Last session was tough — check in gently."
                    elif mood == "joy":
                        prompt += " They were in good spirits last time."
            except Exception:
                pass

        # Weather mention
        try:
            from weather import get_weather
            w = get_weather()
            if w.get("ok"):
                prompt += f" The weather is {w['description'].lower()}, {w['temp_f']}°F."
        except Exception:
            pass

        prompt += ")"
        return prompt

    # ── Live context refresh (update session instructions) ────────

    async def _refresh_session_context(self):
        """Update the Realtime API session instructions with fresh memory context.
        Called every 10 interactions to keep the model informed."""
        if not self._ws:
            return
        try:
            instructions = self._build_full_instructions()
            await self._ws.send(json.dumps({
                "type": "session.update",
                "session": {"instructions": instructions},
            }))
            print("[REALTIME] Session context refreshed")
        except Exception as e:
            print(f"[REALTIME] Context refresh error: {e}")

    # ── Topic suggestion when conversation stalls ─────────────────

    async def _suggest_topic(self):
        """Inject a topic suggestion when the patient gives short replies."""
        if not self._ws:
            return

        # Try to find their favorite topics from Supabase
        suggestion = ""
        if self._db_available:
            try:
                import db_supabase as _db
                topic_counts = _db.get_topic_counts(self._patient_id, days=7)
                if topic_counts:
                    # Pick the most-discussed topic that isn't the current one
                    for topic, _count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True):
                        if topic != self._current_topic and topic != "general":
                            suggestion = topic
                            break
            except Exception:
                pass

        if suggestion:
            inject = (
                f"(The patient has been giving very short answers. They seem disengaged. "
                f"Their favorite topic is '{suggestion}' — gently steer the conversation there. "
                f"Ask a warm, open-ended question about it. Don't say 'I noticed you're quiet.')"
            )
        else:
            inject = (
                "(The patient has been giving very short answers. They seem disengaged. "
                "Try offering an activity — a joke, a story, some music, or a simple question "
                "about their day. Keep it light and inviting. Don't say 'I noticed you're quiet.')"
            )

        try:
            await self._ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": inject}],
                },
            }))
            await self._ws.send(json.dumps({"type": "response.create"}))
            print(f"[REALTIME] Topic suggestion injected: {suggestion or 'activity offer'}")
        except Exception as e:
            print(f"[REALTIME] Topic suggestion error: {e}")

    # ── Shutdown ──────────────────────────────────────────────────

    def _shutdown(self):
        print("[REALTIME] Saving session data...")

        # GPT session summarization via vector memory
        gpt_summary = ""
        if self._vec_available and self._conversation_turns:
            try:
                import vector_memory as vmem
                gpt_summary = vmem.summarize_session(self._conversation_turns, self._patient_id)
                if gpt_summary:
                    print(f"[REALTIME] Session summary: {gpt_summary[:100]}...")
            except Exception as e:
                print(f"[REALTIME] Summarization error: {e}")

        # Temporal pattern analysis
        if self._db_available:
            try:
                import temporal_patterns as tp
                findings = tp.analyze(self._patient_id)
                if findings:
                    # Alert caregiver for warning-level patterns
                    for f in findings:
                        if f["severity"] == "warning" and self._alerts:
                            self._alerts.alert(
                                "PATTERN_DETECTED",
                                f["description"],
                                details=json.dumps(f.get("data", {})),
                            )
            except Exception as e:
                print(f"[REALTIME] Pattern analysis error: {e}")

        if not self._db_available:
            return

        try:
            import db_supabase as _db

            # Save chat history
            saveable = self._chat_history[-80:]
            _db.save_chat_history(
                history=saveable,
                user_name=self._user_name or "",
                user_facts=self._user_facts,
                patient_id=self._patient_id,
            )
            print(f"[REALTIME] Saved {len(saveable)} messages to Supabase")

            # Session summary
            if self._interaction_count > 0:
                mood_counts = {}
                for m in self._mood_history:
                    mood_counts[m] = mood_counts.get(m, 0) + 1
                dominant = max(mood_counts, key=mood_counts.get) if mood_counts else "neutral"
                duration = (time.time() - self._session_start_time) / 60 if self._session_start_time else 0

                topics = list(set(self._topics_discussed))

                _db.save_session_summary(
                    interactions=self._interaction_count,
                    dominant_mood=dominant,
                    mood_distribution=mood_counts,
                    topics_discussed=topics,
                    facts_learned=self._user_facts,
                    duration_minutes=round(duration, 1),
                    patient_id=self._patient_id,
                    summary_text=gpt_summary,
                )
                print(f"[REALTIME] Session: {self._interaction_count} interactions, "
                      f"{round(duration, 1)}min, mood={dominant}, topics={topics}")

            # Anomaly detection — compare today vs baseline
                try:
                    import anomaly_detection as ad
                    total_moods = sum(mood_counts.values()) or 1
                    today_stats = {
                        "interactions": self._interaction_count,
                        "duration_minutes": round(duration, 1),
                        "topic_count": len(set(self._topics_discussed)),
                        "sadness_pct": round(mood_counts.get("sadness", 0) / total_moods * 100, 1),
                    }
                    anomalies = ad.check_anomalies(self._patient_id, today_stats)
                    for a in anomalies:
                        print(f"[REALTIME] ⚠️  ANOMALY: {a['message']}")
                        if self._alerts:
                            self._alerts.alert("BEHAVIORAL_ANOMALY", a["message"])
                        _db.save_alert(
                            "BEHAVIORAL_ANOMALY",
                            a["message"],
                            severity=a.get("severity", "warning"),
                            patient_id=self._patient_id,
                        )
                except Exception as e:
                    print(f"[REALTIME] Anomaly detection error: {e}")

            # Weekly report (auto-generates if enough data)
            try:
                report = _db.generate_weekly_report(self._patient_id)
                if report:
                    print(f"[REALTIME] Weekly report updated")
            except Exception:
                pass

            # RAG session summary
            if self._rag_enabled and self._interaction_count > 0:
                try:
                    import memory as mem
                    mood_counts = {}
                    for m in self._mood_history:
                        mood_counts[m] = mood_counts.get(m, 0) + 1
                    dominant = max(mood_counts, key=mood_counts.get) if mood_counts else "neutral"
                    duration = (time.time() - self._session_start_time) / 60 if self._session_start_time else 0
                    summary_text = (
                        f"{self._interaction_count} interactions, mood: {dominant}, "
                        f"duration: {round(duration, 1)}min"
                    )
                    if self._user_name:
                        summary_text += f", patient: {self._user_name}"
                    if self._topics_discussed:
                        summary_text += f", topics: {', '.join(set(self._topics_discussed))}"
                    mem.save_session_summary(
                        summary=summary_text,
                        mood_distribution=mood_counts,
                        facts_learned=self._user_facts,
                        duration_minutes=round(duration, 1),
                        patient_id=self._patient_id,
                    )
                except Exception:
                    pass

        except Exception as e:
            print(f"[REALTIME] Shutdown save error: {e}")

        # Disconnect robot
        if self._robot:
            try:
                self._robot.reset()
                self._robot.disconnect()
            except Exception:
                pass

    # ── Process user transcript ───────────────────────────────────

    def _process_user_transcript(self, text: str):
        if not text or len(text.strip()) < 2:
            return

        self._interaction_count += 1
        self._chat_history.append({"role": "user", "content": text})
        lower = text.lower()

        # Emotion detection
        emotion = self._detect_emotion(text)
        self._mood_history.append(emotion)
        self._conversation_turns.append(("patient", text, emotion))

        # Consecutive sadness tracking
        if emotion == "sadness":
            self._consecutive_sad += 1
            if self._consecutive_sad >= 3 and self._alerts:
                self._alerts.alert_sustained_distress(self._mood_history)
                self._consecutive_sad = 0  # reset after alerting
        else:
            self._consecutive_sad = 0

        # Emotion-adaptive music — offer after 3+ sustained mood turns
        if emotion in ("sadness", "fear"):
            if self._last_mood_direction == "sad":
                self._consecutive_mood_turns += 1
            else:
                self._last_mood_direction = "sad"
                self._consecutive_mood_turns = 1
                self._music_offered = False
        elif emotion == "joy":
            if self._last_mood_direction == "happy":
                self._consecutive_mood_turns += 1
            else:
                self._last_mood_direction = "happy"
                self._consecutive_mood_turns = 1
                self._music_offered = False
        else:
            self._consecutive_mood_turns = 0
            self._last_mood_direction = ""
            self._music_offered = False

        if self._consecutive_mood_turns >= 3 and not self._music_offered and self._loop:
            self._music_offered = True
            asyncio.run_coroutine_threadsafe(
                self._offer_mood_music(self._last_mood_direction), self._loop
            )

        # Robot expression based on detected emotion
        if self._robot:
            try:
                self._robot.express(emotion)
            except Exception:
                pass

        # Safety checks
        self._check_safety(text)

        # Care request detection
        self._check_care_requests(text)

        # Wandering / spatial disorientation detection
        self._check_wandering(text)

        # Sundowning detection (evening confusion/agitation)
        self._check_sundowning(text)

        # Pain detection
        self._check_pain(text)

        # Gratitude session — intercept answers or detect trigger
        self._handle_gratitude(text)

        # Photo description — "what do you see?" triggers camera + GPT-4o vision
        self._check_vision_request(text)

        # Interactive storytelling — patient choices or trigger
        self._handle_interactive_story(text)

        # Personalized quiz — answers or trigger
        self._handle_quiz(text)

        # Sing-along — next line or trigger
        self._handle_singalong(text)

        # Topic tracking
        self._track_topic(lower)

        # Name extraction
        self._try_learn_name(text)

        # Fact extraction
        self._extract_facts(text)

        # Pattern-based mentions
        try:
            from followups import remember_mention
            remember_mention(text)
        except Exception:
            pass

        # GPT smart mention extraction (background)
        def _smart_extract():
            try:
                from followups import smart_extract_mentions
                smart_extract_mentions(text)
            except Exception:
                pass
        threading.Thread(target=_smart_extract, daemon=True).start()

        # Post to dashboard live chat
        threading.Thread(target=self._post_to_dashboard, args=("patient", text), daemon=True).start()
        threading.Thread(target=self._post_mood_to_dashboard, args=(emotion,), daemon=True).start()


        # Supabase logging
        if self._db_available:
            def _db_log():
                try:
                    import db_supabase as _db
                    topic = self._current_topic or "general"
                    _db.save_conversation(topic, text, self._patient_id, "patient", emotion)
                    _db.save_mood(emotion, int(time.strftime("%H")), time.strftime("%A"), self._patient_id)
                except Exception:
                    pass
            threading.Thread(target=_db_log, daemon=True).start()

        # Vector memory
        if self._vec_available:
            def _store_vec():
                try:
                    import vector_memory as vmem
                    topic = self._current_topic or "general"
                    vmem.store_turn(text, speaker="patient", emotion=emotion,
                                    topic=topic, patient_id=self._patient_id)
                except Exception:
                    pass
            threading.Thread(target=_store_vec, daemon=True).start()

        # Knowledge graph
        if self._kg_available:
            def _kg():
                try:
                    import knowledge_graph as kg
                    kg.extract_and_store(text, self._patient_id)
                except Exception:
                    pass
            threading.Thread(target=_kg, daemon=True).start()

        # RAG memory
        if self._rag_enabled:
            def _rag():
                try:
                    import memory as mem
                    mem.process_conversation_turn(text, "", emotion, self._patient_id)
                except Exception:
                    pass
            threading.Thread(target=_rag, daemon=True).start()

        # Refresh session context every 10 interactions
        if self._interaction_count % 10 == 0 and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._refresh_session_context(), self._loop
            )

        # "Remember when" callbacks — every 15 interactions, reference a past conversation
        if self._interaction_count % 15 == 0 and self._interaction_count > 0 and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._inject_remember_when(), self._loop
            )

        # Stall detection — suggest topics after 3 consecutive short replies
        word_count = len(text.strip().split())
        if word_count <= 4:
            self._consecutive_short += 1
        else:
            self._consecutive_short = 0

        if self._consecutive_short >= 3 and self._loop:
            self._consecutive_short = 0  # reset so we don't spam
            asyncio.run_coroutine_threadsafe(
                self._suggest_topic(), self._loop
            )

    def _process_assistant_transcript(self, text: str):
        if not text or len(text.strip()) < 2:
            return

        self._chat_history.append({"role": "assistant", "content": text})
        self._conversation_turns.append(("assistant", text, ""))

        # Post to dashboard live chat
        threading.Thread(target=self._post_to_dashboard, args=("reachy", text), daemon=True).start()

        # Robot: reset to neutral after speaking
        if self._robot:
            try:
                self._robot.reset()
            except Exception:
                pass

        if self._db_available:
            def _db_log():
                try:
                    import db_supabase as _db
                    topic = self._current_topic or "general"
                    _db.save_conversation(topic, text, self._patient_id, "assistant", "")
                except Exception:
                    pass
            threading.Thread(target=_db_log, daemon=True).start()

        if self._vec_available:
            def _store_vec():
                try:
                    import vector_memory as vmem
                    topic = self._current_topic or "general"
                    vmem.store_bot_response(text, topic=topic, patient_id=self._patient_id)
                except Exception:
                    pass
            threading.Thread(target=_store_vec, daemon=True).start()

        # Record narration for interactive story
        if self._interactive_story and self._interactive_story.is_active:
            self._interactive_story.record_narration(text)

    # ── Safety & care detection ───────────────────────────────────

    def _check_safety(self, text: str):
        lower = text.lower()
        for kw in _CRISIS_KEYWORDS:
            if kw in lower:
                print("[REALTIME] ⚠️  CRISIS keywords detected")
                self._session_alert_count += 1
                if self._alerts:
                    self._alerts.alert_crisis(text)
                if self._db_available:
                    try:
                        import db_supabase as _db
                        _db.save_alert("CRISIS", f"Patient said: {text[:200]}", severity="critical", patient_id=self._patient_id)
                    except Exception:
                        pass
                self._check_alert_escalation()
                return
        for kw in _EMERGENCY_KEYWORDS:
            if kw in lower:
                print("[REALTIME] ⚠️  EMERGENCY keywords detected")
                self._session_alert_count += 1
                if self._alerts:
                    self._alerts.alert_emergency(text)
                if self._db_available:
                    try:
                        import db_supabase as _db
                        _db.save_alert("EMERGENCY", f"Patient said: {text[:200]}", severity="critical", patient_id=self._patient_id)
                    except Exception:
                        pass
                self._check_alert_escalation()
                return

    def _check_care_requests(self, text: str):
        lower = text.lower()
        for req_type, keywords in _CARE_REQUEST_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    print(f"[REALTIME] Care request: {req_type}")
                    self._session_alert_count += 1
                    if self._alerts:
                        if req_type == "medication":
                            self._alerts.alert_medication_request(text)
                        elif req_type == "food":
                            self._alerts.alert_food_request(text)
                        elif req_type == "help":
                            self._alerts.alert_help_request(text)
                    if self._db_available:
                        try:
                            import db_supabase as _db
                            _db.save_alert(f"{req_type.upper()}_REQUEST", text[:200], severity="normal", patient_id=self._patient_id)
                        except Exception:
                            pass
                    self._check_alert_escalation()
                    return

    def _check_alert_escalation(self):
        """If 3+ alerts in one session, escalate to SUSTAINED_DISTRESS."""
        if self._session_alert_count >= 3 and self._session_alert_count % 3 == 0:
            print(f"[REALTIME] ⚠️  ALERT ESCALATION — {self._session_alert_count} alerts this session")
            if self._alerts:
                try:
                    self._alerts.alert(
                        "SUSTAINED_DISTRESS",
                        f"Patient has triggered {self._session_alert_count} alerts this session. Immediate attention recommended.",
                    )
                except Exception:
                    pass
            if self._db_available:
                try:
                    import db_supabase as _db
                    _db.save_alert(
                        "SUSTAINED_DISTRESS",
                        f"Alert escalation: {self._session_alert_count} alerts in one session",
                        severity="critical",
                        patient_id=self._patient_id,
                    )
                except Exception:
                    pass

    def _check_wandering(self, text: str):
        """Detect spatial disorientation / wandering phrases and alert caregiver."""
        lower = text.lower()
        for kw in _WANDERING_KEYWORDS:
            if kw in lower:
                print("[REALTIME] ⚠️  WANDERING/DISORIENTATION detected")
                if self._alerts:
                    try:
                        self._alerts.alert("WANDERING_ALERT", text[:200])
                    except Exception:
                        pass
                if self._db_available:
                    try:
                        import db_supabase as _db
                        _db.save_alert(
                            "WANDERING_ALERT",
                            f"Possible disorientation — patient said: {text[:200]}",
                            severity="high",
                            patient_id=self._patient_id,
                        )
                    except Exception:
                        pass
                return

    def _check_sundowning(self, text: str):
        """Detect evening confusion/agitation and respond with calming approach."""
        try:
            from sundowning import check_sundowning
            hour = int(time.strftime("%H"))
            if not check_sundowning(text, hour):
                return
        except Exception:
            return

        self._sundowning_count += 1
        print(f"[REALTIME] Sundowning keyword detected ({self._sundowning_count} this session)")

        if self._sundowning_count >= 3:
            print("[REALTIME] ⚠️  SUNDOWNING ALERT — switching to calming mode")
            # Alert caregiver
            if self._alerts:
                try:
                    self._alerts.alert("SUNDOWNING_ALERT", f"Patient showing signs of sundowning ({self._sundowning_count} triggers). Last: {text[:150]}")
                except Exception:
                    pass
            if self._db_available:
                try:
                    import db_supabase as _db
                    _db.save_alert(
                        "SUNDOWNING_ALERT",
                        f"Evening confusion detected ({self._sundowning_count} triggers): {text[:200]}",
                        severity="high",
                        patient_id=self._patient_id,
                    )
                except Exception:
                    pass
            # Inject calming prompt
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_sundowning_calm(), self._loop
                )
            self._sundowning_count = 0  # reset after alerting

    async def _inject_sundowning_calm(self):
        """Tell GPT to switch to a gentler, calming tone for sundowning."""
        if not self._ws:
            return
        inject = (
            "(The patient is showing signs of sundowning — evening confusion and agitation. "
            "Switch to a very calm, gentle, reassuring tone. Speak slowly and simply. "
            "Remind them where they are, that they are safe, and that someone who cares about them is nearby. "
            "Don't mention 'sundowning' or any medical terms. Just be warm and grounding. "
            "You might say something like 'You're right here with me, and everything is okay. "
            "You're safe.' Offer to play some calming music or tell a gentle story.)"
        )
        try:
            await self._ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": inject}],
                },
            }))
            await self._ws.send(json.dumps({"type": "response.create"}))
            print("[REALTIME] Sundowning calming prompt injected")
        except Exception as e:
            print(f"[REALTIME] Sundowning inject error: {e}")

    def _check_pain(self, text: str):
        """Detect pain mentions and inject a follow-up prompt."""
        # Skip if we're already in a pain follow-up cooldown
        if self._pain_followup_cooldown > 0:
            self._pain_followup_cooldown -= 1
            return

        try:
            from pain_tracker import detect_pain
            if not detect_pain(text):
                return
        except Exception:
            return

        print("[REALTIME] 🩹 Pain mention detected")
        self._pain_followup_cooldown = 4  # don't re-trigger for 4 turns

        # Alert caregiver
        if self._db_available:
            try:
                import db_supabase as _db
                _db.save_alert(
                    "PAIN_REPORTED",
                    f"Patient mentioned pain: {text[:200]}",
                    severity="normal",
                    patient_id=self._patient_id,
                )
            except Exception:
                pass

        # Inject follow-up into conversation
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._inject_pain_followup(text), self._loop
            )

    async def _inject_pain_followup(self, original_text: str):
        """Ask the patient about their pain — location and severity."""
        if not self._ws:
            return
        inject = (
            f"(The patient just said something about pain: \"{original_text[:100]}\". "
            f"Gently ask them: where does it hurt, and how bad is it on a scale of 1 to 10? "
            f"Be compassionate. Don't be clinical. Something like 'Oh, I'm sorry to hear that. "
            f"Can you tell me where it hurts? And on a scale of 1 to 10, how bad is it?')"
        )
        try:
            await self._ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": inject}],
                },
            }))
            await self._ws.send(json.dumps({"type": "response.create"}))
            print("[REALTIME] Pain follow-up injected")
        except Exception as e:
            print(f"[REALTIME] Pain follow-up error: {e}")

    # ── Photo description (vision) ───────────────────────────────

    def _check_vision_request(self, text: str):
        """Detect 'what do you see' style requests and describe the camera frame."""
        try:
            from vision import is_vision_request
            if not is_vision_request(text):
                return
        except Exception:
            return

        print("[REALTIME] 📷 Vision request detected — capturing frame")
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._inject_vision_description(text), self._loop
            )

    async def _inject_vision_description(self, user_text: str):
        """Capture a camera frame, send to GPT-4o vision, inject the description."""
        if not self._ws:
            return

        # Run the blocking vision call in a thread
        description = await asyncio.get_event_loop().run_in_executor(
            None, self._get_vision_description, user_text
        )

        if not description:
            inject = (
                "(The patient asked you to look at something but the camera isn't available "
                "right now. Apologize warmly and say you can't see anything at the moment. "
                "Suggest they describe it to you instead.)"
            )
        else:
            inject = (
                f"(The patient held up a photo or pointed at something. You looked through "
                f"your camera and here's what you saw: {description}\n"
                f"Now share this with the patient in your own warm, conversational way. "
                f"Don't say 'my camera saw' — just describe it like you're looking at it "
                f"together. Ask a follow-up question about it to encourage reminiscence.)"
            )

        try:
            await self._ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": inject}],
                },
            }))
            await self._ws.send(json.dumps({"type": "response.create"}))
            print("[REALTIME] Vision description injected")
        except Exception as e:
            print(f"[REALTIME] Vision inject error: {e}")

    def _get_vision_description(self, user_text: str) -> str | None:
        """Blocking helper — capture frame and call GPT-4o vision."""
        try:
            from vision import capture_frame, describe_image
            frame_b64 = capture_frame()
            if not frame_b64:
                return None
            return describe_image(frame_b64, user_text)
        except Exception as e:
            print(f"[REALTIME] Vision description error: {e}")
            return None

    # ── Interactive storytelling ──────────────────────────────────

    def _handle_interactive_story(self, text: str):
        """Handle interactive story state — continue or start."""
        # If a story is active, treat this as a choice
        if self._interactive_story and self._interactive_story.is_active:
            prompt = self._interactive_story.continue_story(text)
            if prompt and self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(prompt), self._loop
                )
            # If story just ended, save it
            if self._interactive_story and not self._interactive_story.is_active:
                threading.Thread(target=self._interactive_story.save, daemon=True).start()
            return

        # Detect trigger to start a new story
        try:
            from interactive_story import is_story_trigger
            if not is_story_trigger(text):
                return
        except Exception:
            return

        self._start_interactive_story()

    def _start_interactive_story(self):
        """Start a new interactive story session."""
        try:
            from interactive_story import InteractiveStory
            self._interactive_story = InteractiveStory(
                patient_id=self._patient_id,
                patient_name=self._user_name or "our hero",
                facts=self._user_facts,
            )
            prompt = self._interactive_story.start()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(prompt), self._loop
                )
            print("[REALTIME] Interactive story started")
        except Exception as e:
            print(f"[REALTIME] Story start error: {e}")

    async def _inject_story_prompt(self, prompt: str):
        """Inject a story narration/choice prompt into the conversation."""
        if not self._ws:
            return
        try:
            await self._ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                },
            }))
            await self._ws.send(json.dumps({"type": "response.create"}))
        except Exception as e:
            print(f"[REALTIME] Story inject error: {e}")

    # ── Personalized quiz ─────────────────────────────────────────

    def _handle_quiz(self, text: str):
        """Handle quiz session — answers or trigger."""
        if self._personal_quiz and self._personal_quiz.is_active:
            prompt = self._personal_quiz.check_answer(text)
            if prompt and self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(prompt), self._loop
                )
            return

        try:
            from personal_quiz import is_quiz_trigger
            if not is_quiz_trigger(text):
                return
        except Exception:
            return

        try:
            from personal_quiz import PersonalQuiz
            self._personal_quiz = PersonalQuiz(patient_id=self._patient_id)
            prompt = self._personal_quiz.start()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(prompt), self._loop
                )
            print("[REALTIME] Personal quiz started")
        except Exception as e:
            print(f"[REALTIME] Quiz start error: {e}")

    # ── Sing-along ────────────────────────────────────────────────

    def _handle_singalong(self, text: str):
        """Handle sing-along session — next line or trigger."""
        lower = text.lower()

        if self._singalong and self._singalong.is_active:
            if "stop" in lower or "enough" in lower or "no more" in lower:
                prompt = self._singalong.stop()
            else:
                prompt = self._singalong.next_line()
            if prompt and self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(prompt), self._loop
                )
            return

        try:
            from singalong import is_singalong_trigger
            if not is_singalong_trigger(text):
                return
        except Exception:
            return

        try:
            from singalong import SingAlong
            self._singalong = SingAlong()
            prompt = self._singalong.start(text)
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(prompt), self._loop
                )
            print("[REALTIME] Sing-along started")
        except Exception as e:
            print(f"[REALTIME] Sing-along start error: {e}")

    # ── Gratitude practice ────────────────────────────────────────

    def _handle_gratitude(self, text: str):
        """Handle gratitude session state — start or continue."""
        lower = text.lower()

        # If a session is active, treat this as an answer
        if self._gratitude_session and self._gratitude_session.is_active:
            next_prompt = self._gratitude_session.record_answer(text)
            if next_prompt and self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_gratitude_prompt(next_prompt), self._loop
                )
            return

        # Detect trigger phrases to start a session
        triggers = ["gratitude", "grateful", "thankful", "what i'm thankful for",
                     "gratitude practice", "let's do gratitude", "things i'm grateful"]
        if any(t in lower for t in triggers):
            self._start_gratitude()

    def _start_gratitude(self):
        """Start a new gratitude session."""
        try:
            from gratitude import GratitudeSession
            self._gratitude_session = GratitudeSession(self._patient_id)
            prompt = self._gratitude_session.start()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_gratitude_prompt(prompt), self._loop
                )
            print("[REALTIME] Gratitude session started")
        except Exception as e:
            print(f"[REALTIME] Gratitude start error: {e}")

    async def _inject_gratitude_prompt(self, prompt: str):
        """Inject a gratitude prompt into the conversation."""
        if not self._ws:
            return
        try:
            await self._ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                },
            }))
            await self._ws.send(json.dumps({"type": "response.create"}))
        except Exception as e:
            print(f"[REALTIME] Gratitude inject error: {e}")

    # ── Multi-session story arcs ──────────────────────────────────

    def _build_story_arc_context(self) -> str:
        """Build context about ongoing storylines from the knowledge graph
        and recent sessions so the LLM can reference them naturally."""
        try:
            import db_supabase as _db
            import knowledge_graph as kg

            parts = []

            # Get recent session topics and summaries
            sessions = _db.get_session_summaries(self._patient_id, limit=5)
            if sessions:
                recent_topics = []
                for s in sessions:
                    topics = s.get("topics_discussed", [])
                    summary = s.get("summary_text", "")
                    if summary:
                        recent_topics.append(summary[:120])
                    elif topics:
                        recent_topics.append(f"Talked about: {', '.join(topics[:3])}")
                if recent_topics:
                    parts.append("Recent session storylines: " + " | ".join(recent_topics[:3]))

            # Get entities with the most relations (most talked-about people/things)
            relations = _db.get_all_relations(self._patient_id)
            if relations:
                # Count how often each subject appears
                subject_counts = {}
                for r in relations:
                    subj = r.get("subject", "")
                    if subj and subj != "patient":
                        subject_counts[subj] = subject_counts.get(subj, 0) + 1

                # Top 3 most-discussed entities
                top_entities = sorted(subject_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                if top_entities:
                    entity_descs = []
                    for name, count in top_entities:
                        desc = kg.describe_entity(name, self._patient_id)
                        if desc:
                            entity_descs.append(desc)
                    if entity_descs:
                        parts.append("Key people/things in their life: " + "; ".join(entity_descs))

            if parts:
                return "[STORY ARCS — reference these naturally when relevant: " + " | ".join(parts) + "]"
            return ""
        except Exception as e:
            print(f"[REALTIME] Story arc context error: {e}")
            return ""

    # ── Topic tracking ────────────────────────────────────────────

    def _track_topic(self, text: str):
        detected = None
        max_hits = 0
        for topic, keywords in _TOPIC_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in text)
            if hits > max_hits:
                max_hits = hits
                detected = topic
        if detected:
            self._current_topic = detected
            self._topics_discussed.append(detected)

    # ── Emotion detection ─────────────────────────────────────────

    def _detect_emotion(self, text: str) -> str:
        lower = text.lower()
        emotion_kw = {
            "joy": ["happy", "great", "wonderful", "love", "excited", "fantastic",
                    "amazing", "good", "glad", "thankful", "grateful", "fun", "laugh",
                    "awesome", "beautiful", "celebrate", "proud", "blessed"],
            "sadness": ["sad", "miss", "lonely", "depressed", "cry", "unhappy",
                        "terrible", "awful", "lost", "grief", "hurt", "heartbroken",
                        "disappointed", "regret", "sorrow", "mourn"],
            "anger": ["angry", "mad", "furious", "annoyed", "frustrated", "hate",
                      "upset", "irritated", "outraged", "disgusted"],
            "fear": ["scared", "afraid", "worried", "anxious", "nervous", "terrified",
                     "panic", "dread", "uneasy", "frightened"],
            "surprise": ["surprised", "shocked", "wow", "unbelievable", "unexpected",
                         "astonished", "stunned"],
        }
        for emotion, keywords in emotion_kw.items():
            for kw in keywords:
                if kw in lower:
                    return emotion
        return "neutral"

    # ── Name & fact extraction ────────────────────────────────────

    def _try_learn_name(self, text: str):
        if self._user_name:
            return
        lower = text.lower()
        _not_names = {
            "bored", "tired", "hungry", "thirsty", "scared", "worried",
            "happy", "sad", "angry", "fine", "good", "great", "okay", "ok",
            "sick", "cold", "hot", "lonely", "confused", "lost", "sorry",
            "excited", "nervous", "anxious", "sleepy", "back", "here", "home",
            "ready", "done", "not", "so", "very", "really", "just", "feeling",
        }
        for prefix in ["my name is ", "call me ", "i'm "]:
            if prefix in lower:
                idx = lower.index(prefix) + len(prefix)
                words = text[idx:].split()
                if not words:
                    continue
                name = words[0].strip(".,!?")
                if (len(name) > 1 and name.isalpha()
                        and name.lower() not in _not_names):
                    # For "i'm", require capitalization or be the only word
                    if prefix == "i'm " and not name[0].isupper() and len(words) > 2:
                        continue
                    self._user_name = name.capitalize()
                    print(f"[REALTIME] Learned name: {self._user_name}")
                    if self._db_available:
                        try:
                            import db_supabase as _db
                            _db.save_profile(self._patient_id, name=self._user_name)
                        except Exception:
                            pass

    def _extract_facts(self, text: str):
        lower = text.lower()
        triggers = {
            "family": ["my daughter", "my son", "my wife", "my husband", "my sister",
                       "my brother", "my mother", "my father", "my grandchild",
                       "my grandson", "my granddaughter", "my nephew", "my niece"],
            "pet": ["my dog", "my cat", "my bird", "my pet", "my rabbit",
                    "i have a dog", "i have a cat"],
            "career": ["i used to be", "i was a", "i worked as", "i retired from",
                       "i used to work", "my job was"],
            "interest": ["i love", "i enjoy", "i like", "my hobby is",
                         "i'm passionate about", "i like to"],
            "preference": ["my favorite", "i prefer", "i always liked", "i never liked"],
            "location": ["i live in", "i lived in", "i grew up in", "i'm from", "i am from"],
            "health": ["i have diabetes", "i have arthritis", "my back hurts",
                       "i take medication for", "i was diagnosed with", "my doctor said"],
        }
        for category, patterns in triggers.items():
            for trigger in patterns:
                if trigger in lower:
                    idx = lower.index(trigger)
                    snippet = text[idx:idx + 80].split(".")[0].split("!")[0].split("?")[0].strip()
                    if snippet and snippet not in self._user_facts:
                        self._user_facts.append(snippet)
                        print(f"[REALTIME] Learned fact ({category}): {snippet}")
                        if self._db_available:
                            try:
                                import db_supabase as _db
                                _db.save_fact(category, snippet, self._patient_id)
                            except Exception:
                                pass
                        if len(self._user_facts) > 20:
                            self._user_facts = self._user_facts[-20:]
                    break

    # ── Dashboard live chat ───────────────────────────────────────

    def _post_to_dashboard(self, speaker, text):
        """Send a transcript line to the dashboard so it appears in live chat."""
        try:
            import urllib.request
            data = json.dumps({"speaker": speaker, "text": text}).encode("utf-8")
            req = urllib.request.Request(
                f"{self._dashboard_url}/api/conversation",
                data=data,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            urllib.request.urlopen(req, timeout=3)
        except Exception:
            pass

    # ── Caregiver message polling ────────────────────────────────

    def _check_caregiver_messages(self):
        """Poll the dashboard for pending caregiver messages."""
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self._dashboard_url}/api/messages/pending",
                method="GET",
            )
            resp = urllib.request.urlopen(req, timeout=3)
            messages = json.loads(resp.read().decode("utf-8"))
            return messages
        except Exception:
            return []

    def _post_mood_to_dashboard(self, mood):
        """Update the dashboard status with the current mood."""
        try:
            import urllib.request
            data = json.dumps({"mood": mood}).encode("utf-8")
            req = urllib.request.Request(
                f"{self._dashboard_url}/api/status",
                data=data,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            urllib.request.urlopen(req, timeout=3)
        except Exception:
            pass

    def _start_message_poller(self):
        """Background thread that polls for caregiver messages every 30s."""
        def _poll():
            while self._running:
                try:
                    msgs = self._check_caregiver_messages()
                    if msgs:
                        with self._cg_lock:
                            self._pending_cg_messages.extend(msgs)
                except Exception:
                    pass
                time.sleep(30)
        t = threading.Thread(target=_poll, daemon=True)
        t.start()
        print("[REALTIME] Caregiver message poller started (30s interval)")

    async def _inject_caregiver_messages(self):
        """Check for pending caregiver messages and inject them into the conversation."""
        with self._cg_lock:
            msgs = self._pending_cg_messages[:]
            self._pending_cg_messages.clear()
        if not msgs or not self._ws:
            return
        for msg in msgs:
            text = msg.get("text", "").strip()
            if not text:
                continue
            priority = msg.get("priority", "normal")
            prefix = "URGENT message" if priority == "high" else "Message"
            inject = (
                f"(The caregiver just sent a {prefix.lower()} for the patient: \"{text}\". "
                f"Relay this to the patient naturally and warmly — don't read it robotically. "
                f"Say something like 'Oh, your caregiver just sent you a message...')"
            )
            try:
                await self._ws.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": inject}],
                    },
                }))
                await self._ws.send(json.dumps({"type": "response.create"}))
                print(f"[REALTIME] Injected caregiver message: {text[:60]}...")
            except Exception as e:
                print(f"[REALTIME] Failed to inject caregiver message: {e}")

    # ── Medication schedule checker ───────────────────────────────

    def _start_medication_checker(self):
        """Background thread that checks for due medication reminders every 60s."""
        def _check():
            while self._running:
                if self._db_available:
                    try:
                        import db_supabase as _db
                        reminders = _db.get_reminders(self._patient_id, active_only=True)
                        now_hh_mm = time.strftime("%H:%M")
                        now_minutes = int(time.strftime("%H")) * 60 + int(time.strftime("%M"))
                        for r in reminders:
                            if r.get("reminder_type") != "medication":
                                continue
                            rem_time = (r.get("time") or "").strip()
                            if not rem_time:
                                continue
                            # Parse reminder time
                            try:
                                parts = rem_time.split(":")
                                rem_minutes = int(parts[0]) * 60 + int(parts[1])
                            except (ValueError, IndexError):
                                continue
                            # Within 15-minute window and not already reminded
                            diff = abs(now_minutes - rem_minutes)
                            rem_id = r.get("id", rem_time)
                            if diff <= 15 and rem_id not in self._med_reminded:
                                self._med_reminded.add(rem_id)
                                med_text = r.get("text", "your medication")
                                self._pending_med_prompt = (
                                    f"(It's {now_hh_mm} and the patient has a medication reminder: "
                                    f"\"{med_text}\" scheduled for {rem_time}. "
                                    f"Gently ask if they've taken it. Be warm, not nagging. "
                                    f"Something like 'Hey, it's about time for your medication — have you taken it?')"
                                )
                    except Exception as e:
                        print(f"[REALTIME] Medication check error: {e}")
                time.sleep(60)
        self._pending_med_prompt = None
        t = threading.Thread(target=_check, daemon=True)
        t.start()
        print("[REALTIME] Medication schedule checker started (60s interval)")

    async def _inject_medication_prompt(self):
        """Check for pending medication prompts and inject into conversation."""
        prompt = self._pending_med_prompt
        if not prompt or not self._ws:
            return
        self._pending_med_prompt = None
        try:
            await self._ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                },
            }))
            await self._ws.send(json.dumps({"type": "response.create"}))
            print("[REALTIME] Medication reminder injected")
        except Exception as e:
            print(f"[REALTIME] Medication inject error: {e}")

    # ── Emotion-adaptive music ────────────────────────────────────

    async def _offer_mood_music(self, direction: str):
        """Offer music based on sustained mood."""
        if not self._ws:
            return
        if direction == "sad":
            inject = (
                "(The patient has been feeling sad or anxious for several turns now. "
                "Gently offer to play some calming music to help them feel better. "
                "Something like 'Would you like me to play some soothing music? "
                "It might help you relax a little.' Don't be pushy — just a warm offer.)"
            )
        elif direction == "happy":
            inject = (
                "(The patient has been in a great mood for a while! "
                "Offer to play some upbeat music to keep the good vibes going. "
                "Something like 'You're in such a great mood — want me to put on "
                "some fun music?' Keep it playful and light.)"
            )
        else:
            return

        try:
            await self._ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": inject}],
                },
            }))
            await self._ws.send(json.dumps({"type": "response.create"}))
            print(f"[REALTIME] Mood music offer injected ({direction})")
        except Exception as e:
            print(f"[REALTIME] Mood music offer error: {e}")

    # ── "Remember when" callbacks ─────────────────────────────────

    async def _inject_remember_when(self):
        """Pull an interesting past conversation and reference it naturally."""
        if not self._ws or not self._db_available:
            return

        memory = None
        try:
            import db_supabase as _db
            # Get conversations from 2+ days ago with non-neutral emotion
            rows = _db._execute(
                "SELECT text, topic, emotion, created_at FROM bot_conversation_log "
                "WHERE patient_id=%s AND speaker='patient' AND emotion != '' "
                "AND emotion != 'neutral' AND created_at < NOW() - INTERVAL '2 days' "
                "ORDER BY RANDOM() LIMIT 1",
                (self._patient_id,), fetch=True,
            ) or []
            if rows:
                memory = rows[0]
        except Exception as e:
            print(f"[REALTIME] Remember-when query error: {e}")

        # Fallback: try patient facts if no conversation found
        if not memory:
            try:
                import db_supabase as _db
                facts = _db.get_facts(self._patient_id)
                if facts:
                    import random
                    fact = random.choice(facts)
                    memory = {"text": fact.get("fact", ""), "topic": fact.get("category", ""), "emotion": ""}
            except Exception:
                pass

        if not memory or not memory.get("text"):
            return

        text = memory["text"][:150]
        topic = memory.get("topic", "")
        created = memory.get("created_at", "")

        # Build a time reference
        time_ref = "a while back"
        if created:
            try:
                from datetime import datetime
                dt = created if isinstance(created, datetime) else datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                days_ago = (datetime.now(dt.tzinfo) - dt).days if dt.tzinfo else (datetime.now() - dt).days
                if days_ago == 1:
                    time_ref = "yesterday"
                elif days_ago < 7:
                    time_ref = f"a few days ago"
                elif days_ago < 14:
                    time_ref = "last week"
                else:
                    time_ref = f"a couple weeks ago"
            except Exception:
                pass

        inject = (
            f"(You remember something the patient told you {time_ref}: \"{text}\". "
            f"Bring it up naturally in conversation — like a friend who remembers. "
            f"Something like 'You know, I was thinking about what you told me {time_ref}...' "
            f"Don't quote them exactly. Paraphrase warmly and ask a follow-up question about it.)"
        )

        try:
            await self._ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": inject}],
                },
            }))
            await self._ws.send(json.dumps({"type": "response.create"}))
            print(f"[REALTIME] Remember-when injected: {text[:60]}...")
        except Exception as e:
            print(f"[REALTIME] Remember-when inject error: {e}")

    # ── Main loop ─────────────────────────────────────────────────

    async def _run(self):
        import websockets

        self._loop = asyncio.get_running_loop()
        url = f"wss://api.openai.com/v1/realtime?model={self.model}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1",
        }

        instructions = self._build_full_instructions()

        print(f"[REALTIME] Connecting to {self.model}...")
        async with websockets.connect(url, additional_headers=headers) as ws:
            self._ws = ws
            print("[REALTIME] Connected")

            await ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "modalities": ["audio", "text"],
                    "instructions": instructions,
                    "voice": self.voice,
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {"model": "whisper-1"},
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.7,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 700,
                    },
                },
            }))

            self._mic_muted.set()

            mic_task = asyncio.create_task(self._mic_sender(ws))
            recv_task = asyncio.create_task(self._receiver(ws))
            play_thread = threading.Thread(target=self._playback_worker, daemon=True)
            play_thread.start()

            # Start caregiver message poller
            self._start_message_poller()

            # Start medication schedule checker
            self._start_medication_checker()

            greeting = self._build_greeting_context()
            # Robot: greeting gesture
            if self._robot:
                try:
                    self._robot.perform("greet")
                except Exception:
                    pass
            await ws.send(json.dumps({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": greeting}],
                },
            }))
            await ws.send(json.dumps({"type": "response.create"}))

            print("[REALTIME] Conversation started — just talk!")
            print("[REALTIME] Press Ctrl+C to quit.\n")

            try:
                await asyncio.gather(mic_task, recv_task)
            except asyncio.CancelledError:
                pass

    # ── Mic sender ────────────────────────────────────────────────

    async def _mic_sender(self, ws):
        import sounddevice as sd

        mic_q = asyncio.Queue()
        log_counter = [0]

        def _mic_callback(indata, frames, time_info, status):
            if not self._running:
                return
            pcm = (indata[:, 0] * 32767).astype(np.int16)
            rms = float(np.sqrt(np.mean(indata ** 2)))

            if self._mic_muted.is_set():
                log_counter[0] += 1
                if log_counter[0] % 50 == 0:
                    print(f"[MIC] MUTED rms={rms:.4f}")
                return

            log_counter[0] += 1
            if log_counter[0] % 50 == 0:
                print(f"[MIC] LIVE rms={rms:.4f}")

            try:
                self._loop.call_soon_threadsafe(mic_q.put_nowait, pcm.tobytes())
            except Exception:
                pass

        stream = sd.InputStream(
            samplerate=INPUT_RATE, channels=1, dtype="float32",
            callback=_mic_callback, blocksize=FRAME_SAMPLES,
        )
        stream.start()
        print("[REALTIME] Mic streaming started")

        try:
            while self._running:
                try:
                    data = await asyncio.wait_for(mic_q.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue
                b64 = base64.b64encode(data).decode()
                await ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": b64,
                }))
        finally:
            stream.stop()
            stream.close()

    # ── Receiver ──────────────────────────────────────────────────

    async def _receiver(self, ws):
        async for msg in ws:
            if not self._running:
                break
            event = json.loads(msg)
            etype = event.get("type", "")

            if etype != "response.audio.delta":
                print(f"[WS] {etype}")

            if etype == "response.audio.delta":
                audio_bytes = base64.b64decode(event["delta"])
                self._playback_q.put(audio_bytes)
                if not self._reachy_speaking:
                    self._reachy_speaking = True
                    self._mic_muted.set()
                    print("[REALTIME] Reachy speaking → mic muted")

            elif etype == "response.audio.done":
                self._playback_q.put(None)
                self._reachy_speaking = False
                print("[REALTIME] Reachy done → scheduling unmute")
                threading.Thread(target=self._delayed_unmute, daemon=True).start()
                # Check for caregiver messages after Reachy finishes speaking
                asyncio.ensure_future(self._inject_caregiver_messages())
                # Check for medication reminders
                asyncio.ensure_future(self._inject_medication_prompt())

            elif etype == "response.audio_transcript.done":
                text = event.get("transcript", "")
                if text:
                    print(f"[REACHY] {text}")
                    threading.Thread(
                        target=self._process_assistant_transcript,
                        args=(text,), daemon=True
                    ).start()
                    if self._on_transcript_done:
                        self._on_transcript_done(text)

            elif etype == "conversation.item.input_audio_transcription.completed":
                text = event.get("transcript", "")
                if text:
                    print(f"[YOU] {text}")
                    threading.Thread(
                        target=self._process_user_transcript,
                        args=(text,), daemon=True
                    ).start()
                    if self._on_user_transcript:
                        self._on_user_transcript(text)

            elif etype == "input_audio_buffer.speech_started":
                if self._mic_muted.is_set():
                    print("[REALTIME] Speech during mute → ignoring (bleed)")
                elif time.time() - self._unmute_time < 0.5:
                    print("[REALTIME] Speech right after unmute → ignoring")
                else:
                    print("[REALTIME] User speaking")

            elif etype == "input_audio_buffer.speech_stopped":
                if not self._mic_muted.is_set():
                    print("[REALTIME] User stopped → waiting for response")

            elif etype == "session.created":
                print("[REALTIME] Session created")
            elif etype == "session.updated":
                print("[REALTIME] Session configured")

            elif etype == "error":
                err = event.get("error", {})
                emsg = err.get("message", str(err))
                if "no active response" not in emsg.lower():
                    print(f"[REALTIME] Error: {emsg}")

    # ── Delayed unmute ────────────────────────────────────────────

    def _delayed_unmute(self):
        time.sleep(0.6)
        asyncio.run_coroutine_threadsafe(
            self._clear_input_buffer(), self._loop
        ).result(timeout=2)
        time.sleep(0.15)
        silence = np.zeros(int(INPUT_RATE * 0.3), dtype=np.int16).tobytes()
        b64 = base64.b64encode(silence).decode()
        asyncio.run_coroutine_threadsafe(
            self._send_audio(b64), self._loop
        ).result(timeout=2)
        time.sleep(0.1)
        asyncio.run_coroutine_threadsafe(
            self._clear_input_buffer(), self._loop
        ).result(timeout=2)
        self._unmute_time = time.time()
        self._mic_muted.clear()
        print("[REALTIME] Mic unmuted — listening")
        # Robot: listening pose
        if self._robot:
            try:
                self._robot.perform("listen")
            except Exception:
                pass

    # ── Playback worker ───────────────────────────────────────────

    def _playback_worker(self):
        import sounddevice as sd
        stream = sd.OutputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16",
            blocksize=FRAME_SAMPLES,
        )
        stream.start()
        while self._running:
            try:
                data = self._playback_q.get(timeout=0.1)
            except queue.Empty:
                continue
            if data is None:
                continue
            if self._stop_playback.is_set():
                continue
            pcm = np.frombuffer(data, dtype=np.int16)
            try:
                stream.write(pcm.reshape(-1, 1))
            except Exception:
                pass
        stream.stop()
        stream.close()

    # ── Helpers ───────────────────────────────────────────────────

    def _clear_playback(self):
        self._stop_playback.set()
        while not self._playback_q.empty():
            try:
                self._playback_q.get_nowait()
            except queue.Empty:
                break
        self._stop_playback.clear()

    async def _send_audio(self, b64_audio):
        try:
            await self._ws.send(json.dumps({
                "type": "input_audio_buffer.append", "audio": b64_audio,
            }))
        except Exception:
            pass

    async def _send_cancel(self):
        try:
            await self._ws.send(json.dumps({"type": "response.cancel"}))
        except Exception:
            pass

    async def _clear_input_buffer(self):
        try:
            await self._ws.send(json.dumps({"type": "input_audio_buffer.clear"}))
        except Exception:
            pass
