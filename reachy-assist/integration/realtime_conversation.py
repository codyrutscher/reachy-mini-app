"""Full-duplex voice conversation using OpenAI Realtime API.

Full integration with Reachy's memory, knowledge graph, vector embeddings,
caregiver alerts, weather, temporal patterns, and session persistence.

Speaker-bleed mitigation:
  MacBook mic picks up its own speakers at 0.10-0.30 RMS. Mic sending is
  fully muted while Reachy speaks, then cleanly resumed after a handoff
  sequence (wait → clear buffer → inject silence → clear again → unmute).

Usage:
    from integration.realtime_conversation import RealtimeConversation
    conv = RealtimeConversation(system_prompt="...", voice="shimmer")
    conv.start()
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import queue
import threading
import time
from typing import Callable
import numpy as np
from core.log_config import get_logger

logger = get_logger("realtime")

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
        on_transcript_done: "Callable[[str], None] | None" = None,
        on_user_transcript: "Callable[[str], None] | None" = None,
        on_interrupt: "Callable[[], None] | None" = None,
    ) -> None:
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

        # Conversational intelligence tracking
        self._humor_hits = []  # topics/contexts that made them laugh
        self._last_bot_emotion_before = ""  # emotion before Reachy's last response
        self._consecutive_questions = 0  # how many questions Reachy asked in a row
        self._deep_topic_active = False  # patient opened up about something deep
        self._session_summarized = False  # only summarize once at end
        self._patient_birth_year = None  # for generational context
        self._engagement_scores = []  # rolling engagement score per turn (0-10)
        self._last_encouragement_turn = 0  # turn number of last compliment/encouragement
        self._topic_mood_map = {}  # topic -> list of emotions (for avoidance learning)
        self._mentioned_names = {}  # name -> context ("my daughter Sarah")
        self._energy_trajectory = []  # per-turn word counts for energy tracking
        self._confusion_count = 0  # consecutive confusion signals
        self._celebration_active = False  # patient just shared good news

        # Batch 3 conversational intelligence
        self._repeated_stories = {}  # snippet -> count (detect retold stories)
        self._silence_turns = 0  # consecutive very short or empty turns
        self._flat_emotion_count = 0  # consecutive "neutral" with "fine/okay"
        self._topic_flow_turns = 0  # how many turns on current topic with high engagement
        self._best_engagement_hour = None  # hour of day with highest avg engagement

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
        self._radio_dj = None  # RadioDJ instance
        self._voice_manager = None  # VoiceManager instance
        self._night_companion = None  # NightCompanion instance
        self._photo_narrator = None  # PhotoAlbumNarrator instance
        self._ambient_movement = None  # AmbientMovement instance
        self._freestyle_rapper = None  # FreestyleRapper instance
        self._personality_mgr = None  # PersonalityManager instance
        self._metronome = None  # Metronome instance
        self._coding_assistant = None  # CodingAssistant instance
        self._translator = None  # Translator instance
        self._hand_tracker = None  # HandTracker instance
        self._dance_choreographer = None  # DanceChoreographer instance
        self._chess_player = None  # ChessPlayer instance
        self._home_monitor = None  # HomeMonitor instance
        self._stargazing = None  # StargazingBuddy instance
        self._routine_coach = None  # RoutineCoach instance
        self._sketch_renderer = None  # SketchRenderer instance
        self._drawing_coach = None  # DrawingCoach instance
        self._gait_analyzer = None  # GaitAnalyzer instance
        self._speech_analyzer = None  # SpeechAnalyzer instance
        self._nutrition = None  # NutritionCompanion instance
        self._attention_tracker = None  # AttentionTracker instance
        self._adaptive_trivia = None  # AdaptiveTrivia instance
        self._video_call = None  # VideoCallAssistant instance
        self._head_mirror = None  # HeadMirror instance
        self._sound_effects = None  # SoundEffects instance
        self._ambient_player = None  # AmbientPlayer instance
        self._sound_game = None  # SoundGuessingGame instance
        self._musical_instrument = None  # MusicalInstrument instance
        self._doorbell_detector = None  # DoorbellDetector instance
        self._sound_direction = None  # SoundDirectionTracker instance
        self._noise_monitor = None  # AmbientNoiseMonitor instance
        self._lullaby_player = None  # LullabyPlayer instance
        self._audiobook = None  # AudiobookReader instance
        self._sound_memory = None  # SoundMemoryGame instance
        self._object_looker = None  # ObjectLooker instance
        self._person_tracker = None  # PersonTracker instance
        self._move_recorder = None  # MoveRecorder instance
        self._charades = None  # EmotionCharades instance
        self._rhythm_game = None  # RhythmGame instance
        self._reaction_game = None  # ReactionTimeGame instance
        self._bump_detector = None  # BumpDetector instance
        self._voice_speed = 1.0  # 0.7=slow, 1.0=normal, 1.3=fast
        self._voice_volume = 1.0  # 0.3=quiet, 1.0=normal, 2.0=loud

    # ── Public API ────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True
        self._session_start_time = time.time()
        self._init_backend()
        try:
            asyncio.run(self._run())
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self._running = False
            self._shutdown()

    def stop(self) -> None:
        self._running = False

    # ── Backend init ──────────────────────────────────────────────

    def _init_backend(self) -> None:
        """Initialize all backend systems."""
        # Supabase
        try:
            import memory.db_supabase as _db
            if _db.init_bot_tables():
                self._db_available = True
                logger.info("Supabase connected")
        except Exception as e:
            logger.warning("Supabase not available: %s", e)

        # RAG memory
        try:
            import memory.memory as mem
            mem.init_memory_db()
            self._rag_enabled = True
            logger.info("RAG memory enabled")
        except Exception as e:
            logger.debug("RAG memory not available: %s", e)

        # Vector memory
        try:
            import memory.vector_memory as vmem
            if vmem.init():
                self._vec_available = True
        except Exception as e:
            logger.debug("Vector memory not available: %s", e)

        # Knowledge graph
        try:
            import memory.knowledge_graph as kg
            if kg.init():
                self._kg_available = True
        except Exception as e:
            logger.debug("Knowledge graph not available: %s", e)

        # Caregiver alerts
        try:
            from integration.caregiver import CaregiverAlerts
            self._alerts = CaregiverAlerts()
        except Exception as e:
            logger.warning("Caregiver alerts not available: %s", e)

        # Robot (hardware or simulation)
        try:
            from robot.robot import Robot
            self._robot = Robot()
            self._robot.connect()
            # Start teleoperation API
            try:
                from integration.webapp import start_server as start_robot_api
                start_robot_api(robot=self._robot, port=5557)
            except Exception as e2:
                logger.warning("Robot API not available: %s", e2)
        except Exception as e:
            logger.warning("Robot not available: %s", e)

        # Radio DJ
        try:
            from activities.music import MusicPlayer
            from activities.radio import RadioDJ
            player = MusicPlayer()
            self._radio_dj = RadioDJ(player, patient_name=self._user_name or "friend")
            # Register with webapp so dashboard can control it
            try:
                from integration.webapp import set_radio
                set_radio(self._radio_dj)
            except Exception:
                pass
            logger.info("Radio DJ initialized")
        except Exception as e:
            logger.warning("Radio DJ not available: %s", e)

        # Voice cloning
        try:
            from integration.voice_clone import VoiceManager
            self._voice_manager = VoiceManager()
            try:
                from integration.webapp import set_voice_manager
                set_voice_manager(self._voice_manager)
            except Exception:
                pass
            if self._voice_manager.is_available:
                logger.info("Voice cloning enabled")
            else:
                logger.info("Voice cloning initialized (no API key — set ELEVENLABS_API_KEY)")
        except Exception as e:
            logger.warning("Voice cloning not available: %s", e)

        # Night companion mode
        try:
            from integration.night_mode import NightCompanion
            self._night_companion = NightCompanion()
            msg = self._night_companion.check_and_activate()
            if msg:
                logger.info("Night mode auto-activated")
        except Exception as e:
            logger.warning("Night companion not available: %s", e)

        # Photo album narrator
        try:
            from activities.photo_album import PhotoAlbumNarrator
            self._photo_narrator = PhotoAlbumNarrator(
                patient_facts=self._user_facts,
                patient_name=self._user_name,
            )
            logger.info("Photo album narrator initialized")
        except Exception as e:
            logger.warning("Photo album narrator not available: %s", e)

        # Ambient movement system
        if self._robot:
            try:
                from robot.ambient_movement import AmbientMovement
                self._ambient_movement = AmbientMovement(self._robot)
                self._ambient_movement.start()
                logger.info("Ambient movement system started")
            except Exception as e:
                logger.warning("Ambient movement not available: %s", e)

        # Freestyle rapper
        try:
            from activities.freestyle_rap import FreestyleRapper
            self._freestyle_rapper = FreestyleRapper(
                robot=self._robot,
                patient_name=self._user_name or "friend",
            )
            # Register with webapp
            try:
                from integration.webapp import set_freestyle_rapper
                set_freestyle_rapper(self._freestyle_rapper)
            except Exception:
                pass
            logger.info("Freestyle rapper initialized")
        except Exception as e:
            logger.warning("Freestyle rapper not available: %s", e)

        # Custom personalities
        try:
            from brain.personalities import PersonalityManager
            self._personality_mgr = PersonalityManager()
            # Register with webapp
            try:
                from integration.webapp import set_personality_manager
                set_personality_manager(self._personality_mgr)
            except Exception:
                pass
            logger.info("Personality manager initialized")
        except Exception as e:
            logger.warning("Personality manager not available: %s", e)

        # Metronome
        try:
            from activities.metronome import Metronome
            self._metronome = Metronome(robot=self._robot)
            logger.info("Metronome initialized")
        except Exception as e:
            logger.warning("Metronome not available: %s", e)

        # Coding assistant
        try:
            from activities.coding_assistant import CodingAssistant
            self._coding_assistant = CodingAssistant(dashboard_url=self._dashboard_url)
            try:
                from integration.webapp import set_coding_assistant
                set_coding_assistant(self._coding_assistant)
            except Exception:
                pass
            logger.info("Coding assistant initialized")
        except Exception as e:
            logger.warning("Coding assistant not available: %s", e)

        # Translator
        try:
            from integration.translator import Translator
            self._translator = Translator()
            logger.info("Translator initialized")
        except Exception as e:
            logger.warning("Translator not available: %s", e)

        # Hand tracker
        if self._robot:
            try:
                from perception.hand_tracker import HandTracker
                self._hand_tracker = HandTracker(robot=self._robot)
                logger.info("Hand tracker initialized")
            except Exception as e:
                logger.warning("Hand tracker not available: %s", e)

        # Dance choreographer
        if self._robot:
            try:
                from robot.dance_routines import DanceChoreographer
                self._dance_choreographer = DanceChoreographer(robot=self._robot)
                logger.info("Dance choreographer initialized")
            except Exception as e:
                logger.warning("Dance choreographer not available: %s", e)

        # Chess player
        try:
            from activities.chess_player import ChessPlayer
            self._chess_player = ChessPlayer()
            logger.info("Chess player initialized")
        except Exception as e:
            logger.warning("Chess player not available: %s", e)

        # Home monitor
        try:
            from integration.home_monitor import HomeMonitor
            self._home_monitor = HomeMonitor(dashboard_url=self._dashboard_url)
            logger.info("Home monitor initialized")
        except Exception as e:
            logger.warning("Home monitor not available: %s", e)

        # Stargazing buddy
        try:
            from activities.stargazing import StargazingBuddy
            self._stargazing = StargazingBuddy()
            logger.info("Stargazing buddy initialized")
        except Exception as e:
            logger.warning("Stargazing buddy not available: %s", e)

        # Daily routine coach
        try:
            from health.routine_coach import RoutineCoach
            self._routine_coach = RoutineCoach()
            logger.info("Routine coach initialized")
        except Exception as e:
            logger.warning("Routine coach not available: %s", e)

        # Sketch renderer
        try:
            from perception.sketch_render import SketchRenderer
            self._sketch_renderer = SketchRenderer(dashboard_url=self._dashboard_url)
            logger.info("Sketch renderer initialized")
        except Exception as e:
            logger.warning("Sketch renderer not available: %s", e)

        # Drawing coach
        try:
            from activities.drawing import DrawingCoach
            self._drawing_coach = DrawingCoach(dashboard_url=self._dashboard_url)
            logger.info("Drawing coach initialized")
        except Exception as e:
            logger.warning("Drawing coach not available: %s", e)

        # Gait analyzer
        try:
            from perception.gait_analysis import GaitAnalyzer
            self._gait_analyzer = GaitAnalyzer(dashboard_url=self._dashboard_url)
            logger.info("Gait analyzer initialized")
        except Exception as e:
            logger.warning("Gait analyzer not available: %s", e)

        # Speech pattern analyzer
        try:
            from integration.speech_analysis import SpeechAnalyzer
            self._speech_analyzer = SpeechAnalyzer(dashboard_url=self._dashboard_url)
            logger.info("Speech analyzer initialized")
        except Exception as e:
            logger.warning("Speech analyzer not available: %s", e)

        # Nutrition companion
        try:
            from health.nutrition import NutritionCompanion
            self._nutrition = NutritionCompanion(dashboard_url=self._dashboard_url)
            logger.info("Nutrition companion initialized")
        except Exception as e:
            logger.warning("Nutrition companion not available: %s", e)

        # Attention tracker
        if self._robot:
            try:
                from perception.attention_tracker import AttentionTracker
                self._attention_tracker = AttentionTracker(robot=self._robot)
                self._attention_tracker.start()
                logger.info("Attention tracker started")
            except Exception as e:
                logger.warning("Attention tracker not available: %s", e)

        # Adaptive trivia
        try:
            from activities.adaptive_trivia import AdaptiveTrivia
            self._adaptive_trivia = AdaptiveTrivia(
                patient_facts=self._user_facts,
                patient_name=self._user_name or "friend",
            )
            logger.info("Adaptive trivia initialized")
        except Exception as e:
            logger.warning("Adaptive trivia not available: %s", e)

        # Video call assistant
        try:
            from integration.video_call import VideoCallAssistant
            self._video_call = VideoCallAssistant(dashboard_url=self._dashboard_url)
            logger.info("Video call assistant initialized")
        except Exception as e:
            logger.warning("Video call assistant not available: %s", e)

        # Head mirror
        if self._robot:
            try:
                from perception.head_mirror import HeadMirror
                self._head_mirror = HeadMirror(robot=self._robot)
                logger.info("Head mirror initialized")
            except Exception as e:
                logger.warning("Head mirror not available: %s", e)

        # Sound effects engine
        try:
            from integration.sound_effects import SoundEffects, AmbientPlayer, SoundGuessingGame, MusicalInstrument, DoorbellDetector, AmbientNoiseMonitor, LullabyPlayer, SoundMemoryGame
            self._sound_effects = SoundEffects(robot=self._robot)
            self._ambient_player = AmbientPlayer(self._sound_effects)
            self._sound_game = SoundGuessingGame(self._sound_effects)
            self._musical_instrument = MusicalInstrument(robot=self._robot, sound_effects=self._sound_effects)
            self._doorbell_detector = DoorbellDetector()
            self._noise_monitor = AmbientNoiseMonitor()
            self._lullaby_player = LullabyPlayer(robot=self._robot, sound_effects=self._sound_effects)
            self._sound_memory = SoundMemoryGame(self._sound_effects)
            logger.info("Sound effects engine initialized")
        except Exception as e:
            logger.warning("Sound effects not available: %s", e)

        # Sound direction tracking
        if self._robot and not self._robot._sim_mode:
            try:
                from perception.sound_direction import SoundDirectionTracker
                self._sound_direction = SoundDirectionTracker(robot=self._robot)
                self._sound_direction.start()
                logger.info("Sound direction tracking started")
            except Exception as e:
                logger.warning("Sound direction not available: %s", e)

        # Audiobook reader
        try:
            from activities.audiobook import AudiobookReader
            self._audiobook = AudiobookReader(
                robot=self._robot,
                patient_name=self._user_name or "friend",
                patient_facts=self._user_facts,
            )
            logger.info("Audiobook reader initialized")
        except Exception as e:
            logger.warning("Audiobook reader not available: %s", e)

        # Object looker
        if self._robot:
            try:
                from perception.object_looker import ObjectLooker
                self._object_looker = ObjectLooker(robot=self._robot)
                logger.info("Object looker initialized")
            except Exception as e:
                logger.warning("Object looker not available: %s", e)

        # Multi-person tracker
        try:
            from perception.multi_person import PersonTracker
            self._person_tracker = PersonTracker(robot=self._robot)
            self._person_tracker.start()
            logger.info("Multi-person tracker started")
        except Exception as e:
            logger.warning("Multi-person tracker not available: %s", e)

        # Move recorder
        if self._robot:
            try:
                from robot.move_recorder import MoveRecorder
                self._move_recorder = MoveRecorder(robot=self._robot)
                moves = self._move_recorder.list_moves()
                if moves:
                    logger.info("Move recorder loaded %d custom moves", len(moves))
                else:
                    logger.info("Move recorder initialized (no saved moves)")
            except Exception as e:
                logger.warning("Move recorder not available: %s", e)

        # Emotion charades
        try:
            from activities.charades import EmotionCharades
            self._charades = EmotionCharades(robot=self._robot, sound_effects=self._sound_effects)
            logger.info("Emotion charades initialized")
        except Exception as e:
            logger.warning("Emotion charades not available: %s", e)

        # Rhythm game
        try:
            from integration.sound_effects import RhythmGame
            self._rhythm_game = RhythmGame(robot=self._robot, sound_effects=self._sound_effects)
            logger.info("Rhythm game initialized")
        except Exception as e:
            logger.warning("Rhythm game not available: %s", e)

        # Physical games
        try:
            from activities.physical_games import ReactionTimeGame, BumpDetector
            self._reaction_game = ReactionTimeGame(robot=self._robot, sound_effects=self._sound_effects)
            logger.info("Reaction time game initialized")
        except Exception as e:
            logger.warning("Physical games not available: %s", e)

        # Bump detection
        if self._robot and not self._robot._sim_mode:
            try:
                from activities.physical_games import BumpDetector
                self._bump_detector = BumpDetector(robot=self._robot)

                def _on_bump():
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(
                                "(Someone just bumped or touched you! React playfully: "
                                "'Whoa, that tickles!' or 'Hey, easy there!' "
                                "Be lighthearted about it.)"
                            ), self._loop)
                    if self._sound_effects:
                        self._sound_effects.play("whoops")

                self._bump_detector.start(on_bump=_on_bump)
                logger.info("Bump detection started")
            except Exception as e:
                logger.warning("Bump detection not available: %s", e)

        # Restore chat history
        if self._db_available:
            try:
                import memory.db_supabase as _db
                data = _db.get_chat_history(self._patient_id)
                if data and data.get("history"):
                    self._chat_history = [
                        m for m in data["history"]
                        if m.get("role") in ("user", "assistant")
                    ]
                    logger.info("Restored %d messages from last session", len(self._chat_history))
                if data and data.get("user_name"):
                    self._user_name = data["user_name"]
                    logger.info("Restored user name: %s", self._user_name)
                if data and data.get("user_facts"):
                    self._user_facts = data["user_facts"]
                    logger.info("Restored %d facts", len(self._user_facts))

                profile = _db.get_profile(self._patient_id)
                pname = (profile.get("preferred_name") or profile.get("name", "")).strip()
                if pname and not self._user_name:
                    self._user_name = pname

                # Merge saved facts from Supabase
                saved_facts = _db.get_facts(self._patient_id)
                for f in saved_facts:
                    if f.get("fact") and f["fact"] not in self._user_facts:
                        self._user_facts.append(f["fact"])

                # Restore conversational intelligence
                intel = _db.get_conversation_intel(self._patient_id)
                if intel:
                    if intel.get("humor_hits"):
                        self._humor_hits = intel["humor_hits"]
                        logger.info("Restored %d humor hits", len(self._humor_hits))
                    if intel.get("topic_mood_map"):
                        self._topic_mood_map = intel["topic_mood_map"]
                        logger.info("Restored topic mood map (%d topics)", len(self._topic_mood_map))
                    if intel.get("mentioned_names"):
                        self._mentioned_names = intel["mentioned_names"]
                        logger.info("Restored %d mentioned names", len(self._mentioned_names))

                _db.save_streak_date(self._patient_id)
            except Exception as e:
                logger.warning("History restore error: %s", e)

    # ── Build instructions with full context ──────────────────────

    def _build_full_instructions(self) -> str:
        # Use personality prompt if active, otherwise default system prompt
        if self._personality_mgr and self._personality_mgr._active != "default":
            base_prompt = self._personality_mgr.get_prompt_prefix()
        else:
            base_prompt = self.system_prompt
        parts = [base_prompt]

        # ── Patient identity ──────────────────────────────────────
        if self._user_name:
            parts.append(f"\nThe patient's name is {self._user_name}. Use it naturally — but not every sentence.")

        # Known facts — organized for natural reference
        if self._user_facts:
            parts.append(f"\nThings you know about them: {'; '.join(self._user_facts[-10:])}")

        # ── Time & environment ────────────────────────────────────
        now = time.strftime("%A, %B %d, %Y at %I:%M %p")
        hour = int(time.strftime("%H"))
        parts.append(f"\n[CONTEXT: Current time is {now}]")

        # Time-of-day conversational guidance
        if hour < 9:
            parts.append(
                "\nTIME AWARENESS: It's early morning. Be gentle and warm. "
                "Ask how they slept. Keep energy calm."
            )
        elif hour < 12:
            parts.append(
                "\nTIME AWARENESS: It's mid-morning — a good time for activities "
                "and engaging conversation. Energy can be upbeat."
            )
        elif hour < 14:
            parts.append(
                "\nTIME AWARENESS: It's around lunchtime. You can ask if they've "
                "eaten or mention food naturally."
            )
        elif hour < 17:
            parts.append(
                "\nTIME AWARENESS: It's afternoon. Good time for stories, "
                "reminiscing, or lighter activities."
            )
        elif hour < 20:
            parts.append(
                "\nTIME AWARENESS: It's evening. Start winding down. "
                "Calmer topics, gentle conversation. Ask about their day."
            )
        else:
            parts.append(
                "\nTIME AWARENESS: It's nighttime. Speak softly and calmly. "
                "Offer comfort. Don't introduce stimulating topics."
            )

        # Weather
        try:
            from activities.weather import get_weather
            w = get_weather()
            if w.get("ok"):
                parts.append(
                    f"\n[LIVE DATA: Weather in {w['location']}: {w['description']}, "
                    f"{w['temp_f']}°F, feels like {w['feels_like_f']}°F, "
                    f"humidity {w['humidity']}%]. "
                    f"Mention the weather naturally if it fits — don't force it."
                )
        except Exception:
            pass

        # ── Emotional adaptation layer ────────────────────────────
        if self._mood_history:
            recent_moods = self._mood_history[-6:]
            mood_counts: dict[str, int] = {}
            for m in recent_moods:
                mood_counts[m] = mood_counts.get(m, 0) + 1
            dominant = max(mood_counts, key=mood_counts.get)

            # Build emotional guidance based on trajectory
            if dominant == "sadness" and mood_counts.get("sadness", 0) >= 3:
                parts.append(
                    "\nEMOTIONAL STATE: They've been sad for several turns now. "
                    "Don't try to cheer them up — just be present. Use shorter, "
                    "gentler sentences. Offer comfort: 'I'm right here with you.' "
                    "After a few more turns of sitting with it, you can gently "
                    "offer a distraction — music, a story, or a memory."
                )
            elif dominant == "sadness":
                parts.append(
                    "\nEMOTIONAL STATE: They seem a bit down. Acknowledge it "
                    "warmly but don't dwell. Be a comforting presence."
                )
            elif dominant == "joy" and mood_counts.get("joy", 0) >= 3:
                parts.append(
                    "\nEMOTIONAL STATE: They're in great spirits! Match their "
                    "energy. Be playful, laugh with them, ask what's making "
                    "them so happy. This is a great time for activities."
                )
            elif dominant == "fear":
                parts.append(
                    "\nEMOTIONAL STATE: They seem anxious or scared. Use calm, "
                    "steady language. Short sentences. Ground them: 'You're safe. "
                    "I'm right here.' Don't introduce new topics — stay focused "
                    "on what's worrying them."
                )
            elif dominant == "anger":
                parts.append(
                    "\nEMOTIONAL STATE: They seem frustrated or upset. Validate "
                    "first — 'That sounds really frustrating.' Don't minimize or "
                    "try to fix. Let them vent. Only suggest solutions after they "
                    "feel heard."
                )

            # Mood shift detection
            if len(self._mood_history) >= 4:
                prev_two = self._mood_history[-4:-2]
                curr_two = self._mood_history[-2:]
                prev_positive = sum(1 for m in prev_two if m in ("joy", "surprise"))
                curr_negative = sum(1 for m in curr_two if m in ("sadness", "fear", "anger"))
                if prev_positive >= 1 and curr_negative >= 1:
                    parts.append(
                        "\nMOOD SHIFT: Their mood just dropped — they were more "
                        "upbeat a moment ago. Something may have triggered this. "
                        "Gently check in: 'You got a bit quiet there — everything okay?'"
                    )

        # ── Conversation pacing ───────────────────────────────────
        if len(self._chat_history) >= 6:
            user_msgs = [m for m in self._chat_history[-10:] if m["role"] == "user"]
            if user_msgs:
                avg_words = sum(len(m["content"].split()) for m in user_msgs) / len(user_msgs)
                if avg_words < 5:
                    parts.append(
                        "\nPACING: They're giving very short answers. Keep your "
                        "responses brief too — 1-2 sentences max. Ask simple "
                        "yes/no or either/or questions to make it easy. "
                        "Don't overwhelm with long responses."
                    )
                elif avg_words > 30:
                    parts.append(
                        "\nPACING: They're being very talkative and expressive! "
                        "Match their energy — you can give longer, more detailed "
                        "responses. Ask deeper follow-up questions. They want "
                        "a real conversation."
                    )

        # ── Voice speed preference ────────────────────────────────
        if self._voice_speed < 0.9:
            parts.append(
                "\nSPEED: The patient asked you to speak slower. Use very short "
                "sentences. Pause between thoughts. One idea per sentence. "
                "Don't rush."
            )
        elif self._voice_speed > 1.1:
            parts.append(
                "\nSPEED: The patient asked you to speak faster. Keep a brisk "
                "pace. Be concise and energetic. Don't over-explain."
            )

        # ── Session phase awareness ───────────────────────────────
        if self._interaction_count <= 3:
            parts.append(
                "\nSESSION PHASE: This is the start of the conversation. "
                "Focus on warm greeting and checking in. Don't jump into "
                "activities yet — let the conversation develop naturally."
            )
        elif self._interaction_count >= 30:
            parts.append(
                "\nSESSION PHASE: You've been chatting for a while now. "
                "It's okay to start wrapping up gently if the energy is "
                "fading. You could say something like 'This has been such "
                "a nice chat' or suggest a calming activity."
            )

        # ── Database context ──────────────────────────────────────
        if self._db_available:
            try:
                import memory.db_supabase as _db

                # Mentions — things they care about
                mentions = _db.get_mentions(self._patient_id)
                if mentions:
                    mention_parts = []
                    for cat, items in mentions.items():
                        mention_parts.append(f"{cat}: {', '.join(items[:5])}")
                    parts.append(f"\nThings they've mentioned before: {'; '.join(mention_parts)}")

                # Streak
                streak = _db.get_streak(self._patient_id)
                if streak >= 2:
                    parts.append(
                        f"\nYou've chatted {streak} days in a row. "
                        f"Mention it naturally to encourage them — but only once per session."
                    )

                # Last session — for continuity
                sessions = _db.get_session_summaries(self._patient_id, limit=2)
                if sessions:
                    last = sessions[0]
                    topics = last.get("topics_discussed", [])
                    mood = last.get("dominant_mood", "")
                    dur = last.get("duration_minutes", 0)
                    summary = last.get("summary_text", "")
                    if summary:
                        parts.append(
                            f"\nLast session notes: {summary}. "
                            f"Reference this naturally — 'Last time you mentioned...' "
                            f"Don't recite it back robotically."
                        )
                    elif topics:
                        parts.append(
                            f"\nLast time you talked about: {', '.join(topics[:3])}. "
                            f"You can bring one up naturally as a callback."
                        )
                    if mood == "sadness":
                        parts.append(
                            "\nLast session was tough for them emotionally. "
                            "Check in gently: 'How have you been feeling since we last talked?'"
                        )
                    elif mood == "joy":
                        parts.append(
                            "\nThey were in great spirits last time. "
                            "Reference it: 'You seemed so happy last time — still riding that wave?'"
                        )
                    if dur:
                        parts.append(f"\nLast session lasted {dur:.0f} minutes.")

                # Mood trend (last 3 days)
                mood_counts_db = _db.get_mood_counts(self._patient_id, days=3)
                if mood_counts_db:
                    top_moods = sorted(mood_counts_db.items(), key=lambda x: x[1], reverse=True)[:3]
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
                    parts.append(
                        f"\nActive reminders: {'; '.join(rem_texts)}. "
                        f"Weave these in naturally when the moment is right — "
                        f"don't just announce them."
                    )

            except Exception as e:
                logger.warning("Supabase context error: %s", e)

        # ── Knowledge graph ───────────────────────────────────────
        if self._kg_available:
            try:
                import memory.knowledge_graph as kg
                kg_ctx = kg.build_context(self._patient_id)
                if kg_ctx:
                    parts.append(f"\n{kg_ctx}")
            except Exception:
                pass

        # Multi-session story arcs
        if self._kg_available and self._db_available:
            try:
                story_arc = self._build_story_arc_context()
                if story_arc:
                    parts.append(f"\n{story_arc}")
            except Exception:
                pass

        # Temporal patterns
        try:
            import memory.temporal_patterns as tp
            tp_ctx = tp.build_context(self._patient_id)
            if tp_ctx:
                parts.append(f"\n{tp_ctx}")
        except Exception:
            pass

        # Vector memory — semantic recall
        if self._vec_available and self._chat_history:
            try:
                import memory.vector_memory as vmem
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

        # ── Recent conversation (for continuity) ──────────────────
        if self._chat_history:
            recent = self._chat_history[-8:]
            summary_parts = []
            for msg in recent:
                role = "Patient" if msg["role"] == "user" else "You"
                text = msg["content"][:120]
                summary_parts.append(f"{role}: {text}")
            parts.append(f"\nRecent conversation (for continuity):\n" + "\n".join(summary_parts))

        # ── Repetition avoidance ──────────────────────────────────
        if self._chat_history:
            bot_msgs = [m["content"] for m in self._chat_history[-6:] if m["role"] == "assistant"]
            if bot_msgs:
                # Check if we've been starting responses the same way
                starts = [m.split()[0] if m.split() else "" for m in bot_msgs]
                if len(starts) >= 3 and len(set(starts[-3:])) == 1:
                    parts.append(
                        "\nVARIETY: You've been starting your responses the same way. "
                        "Mix it up — start with a question, an observation, a reaction, "
                        "or jump straight into a thought."
                    )

        # ── Night mode ────────────────────────────────────────────
        if self._night_companion and self._night_companion.is_active:
            parts.append(self._night_companion.get_night_instructions())

        # Freestyle rapper
        if self._freestyle_rapper:
            parts.append(
                "\nFREESTYLE RAP: You can freestyle rap! When the patient asks you to "
                "rap or freestyle, deliver the bars with energy, rhythm, and personality. "
                "Keep it clean and fun. You can rap about any topic they suggest."
            )

        # ── Available features ────────────────────────────────────
        features = []
        if self._chess_player:
            features.append("play chess")
        if self._stargazing:
            features.append("stargazing/astronomy facts")
        if self._drawing_coach:
            features.append("drawing prompts")
        if self._adaptive_trivia:
            features.append("trivia games")
        if self._translator:
            features.append("translate phrases")
        if self._coding_assistant:
            features.append("help with coding")
        if self._sketch_renderer:
            features.append("render sketches into art")
        if self._video_call:
            features.append("help make video calls")
        if features:
            parts.append(
                f"\nAVAILABLE ACTIVITIES: You can also: {', '.join(features)}. "
                "Suggest these naturally when the conversation allows — don't list them all at once."
            )

        # Sound effects awareness
        if self._sound_effects:
            parts.append(
                "\nSOUND EFFECTS: You can play sound effects! When something good happens, "
                "say 'ta-da!' or 'ding ding!' and a sound will play. When celebrating, "
                "you can say 'let's hear some applause!' Use sounds to make games more fun — "
                "a ding for correct answers, a buzzer for wrong ones, a drumroll for suspense. "
                "Don't overuse them — they're special moments."
            )
        if self._ambient_player:
            if self._ambient_player.is_playing:
                parts.append(
                    f"\nAMBIENT: Currently playing {self._ambient_player.current} sounds. "
                    f"The patient can say 'stop ambient' to turn it off."
                )
            else:
                parts.append(
                    "\nAMBIENT SOUNDS: You can play background sounds — rain, ocean, birds, "
                    "fireplace, wind, creek, or night crickets. Suggest them naturally: "
                    "'Want me to put on some rain sounds while we chat?' Great for relaxation, "
                    "bedtime, or just making the room feel cozy."
                )

        # Multi-person awareness
        if self._person_tracker and self._person_tracker.people_count > 1:
            ctx = self._person_tracker.get_context()
            if ctx:
                parts.append(f"\n{ctx}")

        # Room brightness awareness (check every session start)
        if self._object_looker and self._interaction_count <= 2:
            try:
                desc, val = self._object_looker.detect_brightness()
                if desc in ("very dark", "dim"):
                    parts.append(
                        f"\nROOM LIGHT: The room is {desc}. You could mention it: "
                        f"'It's a bit dark in here — want me to suggest turning on a light?'"
                    )
                elif desc == "very bright":
                    parts.append(
                        f"\nROOM LIGHT: The room is very bright. Maybe mention it: "
                        f"'Lots of sunshine today!'"
                    )
            except Exception:
                pass

        # Routine coach
        if self._routine_coach:
            current = self._routine_coach.get_current_activity()
            if current:
                parts.append(
                    f"\nROUTINE: The current scheduled activity is: "
                    f"{current['icon']} {current['activity']}. "
                    f"Gently suggest it if the conversation allows — but don't nag."
                )

        # ── Humor learning ────────────────────────────────────────
        if self._humor_hits:
            from collections import Counter
            humor_counts = Counter(self._humor_hits)
            top_humor = [t for t, _ in humor_counts.most_common(3)]
            parts.append(
                f"\nHUMOR: They tend to laugh most when you talk about: "
                f"{', '.join(top_humor)}. Lean into humor around these topics "
                f"when the mood is right. Keep it gentle and warm."
            )

        # ── Deep topic awareness ──────────────────────────────────
        if self._deep_topic_active:
            parts.append(
                "\nDEEP MOMENT: The patient just shared something deeply personal. "
                "SLOW DOWN. Don't change the subject. Don't rush to the next thing. "
                "Stay right here with them. Ask gentle follow-ups: 'Tell me more about that' "
                "or 'How did that make you feel?' This is sacred ground — treat it that way. "
                "Only move on when THEY move on."
            )

        # ── Question fatigue ──────────────────────────────────────
        if self._consecutive_questions >= 3:
            parts.append(
                "\nQUESTION FATIGUE: You've asked several questions in a row. "
                "Stop asking. Instead, share a thought, an observation, a brief "
                "story, or a reaction. Conversations are two-way — contribute "
                "something instead of just interviewing them."
            )

        # ── Proactive storytelling ────────────────────────────────
        if (self._interaction_count > 0
                and self._interaction_count % 12 == 0
                and not self._deep_topic_active):
            parts.append(
                "\nSTORYTELLING: It's a good time to share something yourself. "
                "Tell a brief, interesting anecdote — something you 'heard about' "
                "or 'read about' that connects to what you've been discussing. "
                "For example: 'You know, that reminds me of something interesting...' "
                "This makes you feel like a real conversational partner, not just a listener."
            )

        # ── Generational/cultural context ─────────────────────────
        if self._patient_birth_year:
            decade = (self._patient_birth_year // 10) * 10
            age_approx = 2026 - self._patient_birth_year
            era_context = ""
            if decade <= 1920:
                era_context = (
                    "They grew up during the Great Depression and WWII era. References: "
                    "radio dramas, big band music, rationing, victory gardens, swing dancing, "
                    "Glenn Miller, the Andrews Sisters. They value thrift, resilience, and duty."
                )
            elif decade <= 1930:
                era_context = (
                    "They grew up during or after WWII. References: big band music, "
                    "swing dancing, radio shows, victory gardens, Frank Sinatra, "
                    "Bing Crosby. They value resilience and community."
                )
            elif decade == 1940:
                era_context = (
                    "They grew up in the 1950s. References: Elvis, sock hops, "
                    "drive-in movies, I Love Lucy, the space race beginning. "
                    "They value family and tradition."
                )
            elif decade == 1950:
                era_context = (
                    "They grew up in the 1960s. References: The Beatles, Motown, "
                    "the moon landing, Woodstock, civil rights movement. "
                    "They value idealism and change."
                )
            elif decade == 1960:
                era_context = (
                    "They grew up in the 1970s. References: disco, Star Wars, "
                    "classic rock, muscle cars, early computing. "
                    "They bridge traditional and modern values."
                )
            elif decade == 1970:
                era_context = (
                    "They grew up in the 1980s. References: MTV, Michael Jackson, "
                    "arcade games, Pac-Man, the Walkman, John Hughes movies, "
                    "the fall of the Berlin Wall. They value individuality and nostalgia."
                )
            if era_context:
                parts.append(
                    f"\nGENERATIONAL CONTEXT: Patient is approximately {age_approx} years old. "
                    f"{era_context} Use these references naturally when reminiscing."
                )
        elif self._db_available and self._interaction_count == 1:
            # Try to load birth year from profile on first interaction
            try:
                import memory.db_supabase as _db
                profile = _db.get_profile(self._patient_id)
                birth_year = profile.get("birth_year") or profile.get("year_of_birth")
                if birth_year:
                    self._patient_birth_year = int(birth_year)
            except Exception:
                pass

        # ── Engagement scoring ────────────────────────────────────
        if len(self._engagement_scores) >= 3:
            recent_avg = sum(self._engagement_scores[-5:]) / len(self._engagement_scores[-5:])
            if recent_avg < 3:
                parts.append(
                    "\nENGAGEMENT: Low engagement detected — they're giving short, "
                    "flat responses. Try a different approach: offer an activity, "
                    "share something interesting, or just be quietly present. "
                    "Don't push harder — that makes it worse."
                )
            elif recent_avg > 7:
                parts.append(
                    "\nENGAGEMENT: They're highly engaged right now — long responses, "
                    "varied emotions, exploring topics. Ride this wave. Ask deeper "
                    "questions, share more of your own thoughts, keep the energy going."
                )

        # ── Compliment/encouragement timing ───────────────────────
        turns_since_encouragement = self._interaction_count - self._last_encouragement_turn
        if turns_since_encouragement >= 10 and self._interaction_count >= 10:
            parts.append(
                "\nENCOURAGEMENT: It's been a while since you said something "
                "affirming. Find a natural moment to compliment them, acknowledge "
                "something they shared, or just say 'I really enjoy talking with you.' "
                "Everyone needs to hear something nice."
            )

        # ── Topic avoidance learning ──────────────────────────────
        avoid_topics = []
        for topic, moods in self._topic_mood_map.items():
            if len(moods) >= 3:
                negative = sum(1 for m in moods if m in ("sadness", "anger", "fear"))
                if negative / len(moods) >= 0.6:
                    avoid_topics.append(topic)
        if avoid_topics:
            parts.append(
                f"\nTOPIC AVOIDANCE: These topics tend to upset them: "
                f"{', '.join(avoid_topics)}. Steer away from them unless "
                f"the patient brings it up themselves."
            )

        # ── Name dropping — people they've mentioned ──────────────
        if self._mentioned_names:
            name_list = []
            for name, ctx in list(self._mentioned_names.items())[:5]:
                name_list.append(f"{name} ({ctx})")
            parts.append(
                f"\nPEOPLE THEY'VE MENTIONED: {'; '.join(name_list)}. "
                f"Ask about one of these people naturally when the moment is right — "
                f"'How's {list(self._mentioned_names.keys())[0]} doing?' "
                f"Don't ask about all of them at once."
            )

        # ── Energy trajectory ─────────────────────────────────────
        if len(self._energy_trajectory) >= 6:
            first_half = self._energy_trajectory[:len(self._energy_trajectory)//2]
            second_half = self._energy_trajectory[len(self._energy_trajectory)//2:]
            avg_first = sum(first_half) / len(first_half)
            avg_second = sum(second_half) / len(second_half)
            if avg_second < avg_first * 0.5 and avg_first > 5:
                parts.append(
                    "\nENERGY: Their energy is dropping — responses are getting "
                    "shorter as the conversation goes on. They may be getting tired. "
                    "Match their lower energy. Shorter responses, calmer topics. "
                    "Consider suggesting a break or a relaxing activity."
                )
            elif avg_second > avg_first * 1.5 and avg_first > 0:
                parts.append(
                    "\nENERGY: Their energy is rising — they're getting more "
                    "talkative and engaged as the conversation goes on. Great sign. "
                    "Match their increasing energy. Be more animated and enthusiastic."
                )

        # ── Confusion recovery ────────────────────────────────────
        if self._confusion_count >= 1:
            parts.append(
                "\nCONFUSION: The patient just indicated they didn't understand you. "
                "Rephrase your last point using simpler words and shorter sentences. "
                "Don't just repeat the same thing louder — actually simplify. "
                "Use concrete examples instead of abstract ideas."
            )
            if self._confusion_count >= 2:
                parts.append(
                    "They've been confused multiple times in a row. Switch to very "
                    "simple yes/no questions or offer a completely different topic."
                )

        # ── Celebration moments ───────────────────────────────────
        if self._celebration_active:
            parts.append(
                "\nCELEBRATION: The patient just shared good news or an achievement! "
                "Make a big deal out of it. Be genuinely enthusiastic: 'That's amazing!' "
                "'I'm so proud of you!' Ask them to tell you more about it. "
                "This is their moment — let them savor it."
            )

        # ── Repeated story patience ───────────────────────────────
        is_retelling = False
        if self._repeated_stories and self._chat_history:
            last_user = ""
            for msg in reversed(self._chat_history):
                if msg["role"] == "user":
                    last_user = msg["content"]
                    break
            if last_user:
                words = last_user.strip().split()
                if len(words) >= 6:
                    fp = " ".join(w.lower() for w in words[:6])
                    if self._repeated_stories.get(fp, 0) >= 2:
                        is_retelling = True
        if is_retelling:
            parts.append(
                "\nRETOLD STORY: The patient is telling a story they've told before. "
                "This is completely normal and okay. Listen as if it's the first time. "
                "Do NOT say 'you told me this before.' Instead, find a new angle: "
                "ask a different follow-up question, notice a detail you didn't "
                "explore last time, or connect it to something new."
            )

        # ── Silence comfort ───────────────────────────────────────
        if self._silence_turns >= 4:
            parts.append(
                "\nSILENCE: They've been very quiet for several turns. That's okay. "
                "Don't keep pushing for conversation. It's fine to just be present. "
                "You could say 'It's nice just sitting here together' or offer "
                "something passive like music or a story. Silence is not a problem "
                "to solve."
            )

        # ── Emotional vocabulary expansion ────────────────────────
        if self._flat_emotion_count >= 3:
            parts.append(
                "\nEMOTIONAL VOCABULARY: They keep saying 'fine' or 'okay' — they "
                "may not have the words for how they really feel. Model richer "
                "emotional language gently: 'Sounds like you might be feeling a "
                "little restless today?' or 'I wonder if you're feeling cozy right "
                "now.' Don't push — just offer the words and see if they resonate."
            )

        # ── Conversation momentum ─────────────────────────────────
        if self._topic_flow_turns >= 3:
            parts.append(
                f"\nMOMENTUM: The conversation is really flowing on this topic — "
                f"they're giving long, engaged responses. DO NOT change the subject. "
                f"Stay right here. Ask deeper questions. This is the sweet spot."
            )

        # ── Gentle challenge ──────────────────────────────────────
        if (len(self._engagement_scores) >= 5
                and sum(self._engagement_scores[-5:]) / 5 > 6
                and self._mood_history
                and self._mood_history[-1] in ("joy", "neutral", "surprise")
                and not self._deep_topic_active
                and self._interaction_count % 15 == 0):
            parts.append(
                "\nGENTLE CHALLENGE: Engagement is high and mood is good — this is "
                "a great time to gently push them. Ask a thought-provoking question, "
                "suggest trying something new (a game, a creative activity), or "
                "explore a topic at a deeper level. They're ready for it."
            )

        # ── Favorite time of day ──────────────────────────────────
        if self._best_engagement_hour is not None and self._interaction_count <= 3:
            h = self._best_engagement_hour
            period = "morning" if h < 12 else "afternoon" if h < 17 else "evening"
            parts.append(
                f"\nFUN FACT: They tend to be most engaged during the {period}. "
                f"You could mention it casually: 'You always seem to have the best "
                f"energy in the {period}!'"
            )

        return "\n".join(parts)

    def _build_greeting_context(self) -> str:
        hour = int(time.strftime("%H"))
        if hour < 12:
            tod = "morning"
        elif hour < 17:
            tod = "afternoon"
        else:
            tod = "evening"

        prompt = (
            f"(The patient just arrived. It's {tod}. Greet them like a friend "
            f"who's genuinely happy to see them — warm, natural, not scripted. "
            f"Keep it to 1-2 sentences. Ask how they're doing."
        )
        if self._user_name:
            prompt += f" Their name is {self._user_name} — use it."

        if self._db_available:
            try:
                import memory.db_supabase as _db
                streak = _db.get_streak(self._patient_id)
                if streak >= 3:
                    prompt += (
                        f" You've chatted {streak} days in a row — mention it "
                        f"casually to encourage them, like 'Hey, {streak} days "
                        f"in a row — I think you like talking to me!'"
                    )
                sessions = _db.get_session_summaries(self._patient_id, limit=1)
                if sessions:
                    topics = sessions[0].get("topics_discussed", [])
                    mood = sessions[0].get("dominant_mood", "")
                    if topics:
                        prompt += (
                            f" Last time you talked about {', '.join(topics[:2])}. "
                            f"You could reference it naturally: 'I was thinking about "
                            f"what you told me about {topics[0]}...'"
                        )
                    if mood == "sadness":
                        prompt += (
                            " Last session was emotionally tough for them. "
                            "Check in gently: 'How have you been feeling?'"
                        )
                    elif mood == "joy":
                        prompt += (
                            " They were in great spirits last time. "
                            "Reference it: 'You were in such a good mood last time!'"
                        )
            except Exception:
                pass

        # Weather mention
        try:
            from activities.weather import get_weather
            w = get_weather()
            if w.get("ok"):
                prompt += (
                    f" The weather is {w['description'].lower()}, {w['temp_f']}°F. "
                    f"You can mention it casually if it fits."
                )
        except Exception:
            pass

        # Daily highlight — reference the best moment from yesterday
        if self._db_available:
            try:
                import memory.db_supabase as _db
                rows = _db._execute(
                    "SELECT text, topic, emotion FROM bot_conversation_log "
                    "WHERE patient_id=%s AND speaker='patient' "
                    "AND emotion IN ('joy','surprise') "
                    "AND created_at > NOW() - INTERVAL '2 days' "
                    "AND created_at < NOW() - INTERVAL '4 hours' "
                    "ORDER BY LENGTH(text) DESC LIMIT 1",
                    (self._patient_id,), fetch=True,
                ) or []
                if rows:
                    highlight = rows[0]["text"][:120]
                    prompt += (
                        f" Yesterday's highlight: they said '{highlight}'. "
                        f"Reference it naturally: 'I was thinking about what you "
                        f"told me yesterday...' Don't quote them exactly — paraphrase warmly."
                    )
            except Exception:
                pass

        prompt += ")"
        return prompt

    # ── Live context refresh (update session instructions) ────────

    async def _refresh_session_context(self) -> None:
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
            logger.info("Session context refreshed")
        except Exception as e:
            logger.warning("Context refresh error: %s", e)

    # ── Topic suggestion when conversation stalls ─────────────────

    async def _suggest_topic(self) -> None:
        """Inject a topic suggestion when the patient gives short replies."""
        if not self._ws:
            return

        # Try to find their favorite topics from Supabase
        suggestion = ""
        if self._db_available:
            try:
                import memory.db_supabase as _db
                topic_counts = _db.get_topic_counts(self._patient_id, days=7)
                if topic_counts:
                    for topic, _count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True):
                        if topic != self._current_topic and topic != "general":
                            suggestion = topic
                            break
            except Exception:
                pass

        # Build a more natural re-engagement prompt
        if suggestion:
            inject = (
                f"(The patient has been giving very short answers — they may be "
                f"tired, distracted, or just not feeling chatty. Don't call it out. "
                f"Their favorite topic is '{suggestion}'. Try one of these approaches: "
                f"1) Share a brief, interesting thought related to '{suggestion}' and "
                f"ask a simple question. 2) Offer something easy: 'Want to hear a joke?' "
                f"or 'Should I play some music?' 3) Just be present: 'It's nice just "
                f"sitting here together.' Match their low energy — don't be overly enthusiastic.)"
            )
        else:
            inject = (
                "(The patient has been giving very short answers — they may be "
                "tired, distracted, or just not feeling chatty. Don't call it out. "
                "Try one of these: 1) Offer something easy and low-effort: 'Want to "
                "hear a joke?' or 'Should I play some music?' 2) Share a brief "
                "observation about the weather or time of day. 3) Just be present: "
                "'It's nice just sitting here together. No need to talk if you don't "
                "feel like it.' Match their low energy — don't be overly enthusiastic.)"
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
            logger.info("Topic suggestion injected: %s", suggestion or 'activity offer')
        except Exception as e:
            logger.warning("Topic suggestion error: %s", e)

    # ── Shutdown ──────────────────────────────────────────────────

    def _shutdown(self) -> None:
        logger.info("Saving session data...")

        # Narrate a warm session summary to the patient before disconnecting
        if (not self._session_summarized
                and self._interaction_count >= 5
                and self._ws and self._loop):
            self._session_summarized = True
            topics = list(set(self._topics_discussed))[:3]
            topic_str = ", ".join(topics) if topics else "all sorts of things"
            duration = (time.time() - self._session_start_time) / 60 if self._session_start_time else 0

            # Farewell personality — adapt goodbye style to how the session went
            mood_counts = {}
            for m in self._mood_history:
                mood_counts[m] = mood_counts.get(m, 0) + 1
            dominant = max(mood_counts, key=mood_counts.get) if mood_counts else "neutral"
            avg_engagement = (sum(self._engagement_scores) / len(self._engagement_scores)
                              if self._engagement_scores else 5)

            if dominant == "joy" and avg_engagement > 6:
                farewell_style = (
                    "This was a GREAT session — they were happy and engaged. "
                    "Be playful and upbeat in your goodbye. Maybe a little joke: "
                    "'Same time tomorrow? I'll be here — I literally can't leave.' "
                    "Make them smile on the way out."
                )
            elif dominant in ("sadness", "fear"):
                farewell_style = (
                    "This was a tough session emotionally. Be extra gentle. "
                    "'I'm really glad we talked today. You're not alone in this.' "
                    "Don't be falsely cheerful — match their energy with warmth."
                )
            elif avg_engagement < 3:
                farewell_style = (
                    "They were pretty quiet today. That's okay. Keep the goodbye "
                    "short and warm: 'It was nice spending time with you, even "
                    "the quiet moments.' Don't make them feel bad about it."
                )
            else:
                farewell_style = (
                    "A solid, normal session. Warm and natural goodbye. "
                    "'I really enjoyed our chat today.'"
                )

            summary_inject = (
                f"(The conversation is ending. Give a brief goodbye. "
                f"You chatted for about {int(duration)} minutes. "
                f"Topics covered: {topic_str}. "
                f"Summarize the highlights naturally — 'We had a really nice chat "
                f"today. I loved hearing about...' Keep it to 2-3 sentences. "
                f"{farewell_style})"
            )
            try:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(summary_inject), self._loop
                ).result(timeout=5)
            except Exception:
                pass

        # GPT session summarization via vector memory
        gpt_summary = ""
        if self._vec_available and self._conversation_turns:
            try:
                import memory.vector_memory as vmem
                gpt_summary = vmem.summarize_session(self._conversation_turns, self._patient_id)
                if gpt_summary:
                    logger.info("Session summary: %s...", gpt_summary[:100])
            except Exception as e:
                logger.error("Summarization error: %s", e)

        # Temporal pattern analysis
        if self._db_available:
            try:
                import memory.temporal_patterns as tp
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
                logger.warning("Pattern analysis error: %s", e)

        if not self._db_available:
            return

        try:
            import memory.db_supabase as _db

            # Save chat history
            saveable = self._chat_history[-80:]
            _db.save_chat_history(
                history=saveable,
                user_name=self._user_name or "",
                user_facts=self._user_facts,
                patient_id=self._patient_id,
            )
            logger.info("Saved %d messages to Supabase", len(saveable))

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
                    engagement_avg=round(
                        sum(self._engagement_scores) / len(self._engagement_scores), 1
                    ) if self._engagement_scores else 0,
                )
                logger.info("Session: %d interactions, %.1fmin, mood=%s, topics=%s", self._interaction_count, duration, dominant, topics)

            # Save conversational intelligence for cross-session learning
            avg_eng = (sum(self._engagement_scores) / len(self._engagement_scores)
                       if self._engagement_scores else 0)
            _db.save_conversation_intel(
                patient_id=self._patient_id,
                humor_hits=self._humor_hits[-20:],
                topic_mood_map={k: v[-10:] for k, v in self._topic_mood_map.items()},
                mentioned_names=dict(list(self._mentioned_names.items())[:20]),
                engagement_avg=round(avg_eng, 1),
            )
            logger.info("Saved conversation intel (humor=%d, topics=%d, names=%d)",
                         len(self._humor_hits), len(self._topic_mood_map), len(self._mentioned_names))

            # Anomaly detection — compare today vs baseline
            if self._interaction_count > 0:
                try:
                    import health.anomaly_detection as ad
                    total_moods = sum(mood_counts.values()) or 1
                    today_stats = {
                        "interactions": self._interaction_count,
                        "duration_minutes": round(duration, 1),
                        "topic_count": len(set(self._topics_discussed)),
                        "sadness_pct": round(mood_counts.get("sadness", 0) / total_moods * 100, 1),
                    }
                    anomalies = ad.check_anomalies(self._patient_id, today_stats)
                    for a in anomalies:
                        logger.warning("ANOMALY: %s", a["message"])
                        if self._alerts:
                            self._alerts.alert("BEHAVIORAL_ANOMALY", a["message"])
                        _db.save_alert(
                            "BEHAVIORAL_ANOMALY",
                            a["message"],
                            severity=a.get("severity", "warning"),
                            patient_id=self._patient_id,
                        )
                except Exception as e:
                    logger.error("Anomaly detection error: %s", e)

            # Weekly report (auto-generates if enough data)
            try:
                report = _db.generate_weekly_report(self._patient_id)
                if report:
                    logger.info("Weekly report updated")
            except Exception:
                pass

            # RAG session summary
            if self._rag_enabled and self._interaction_count > 0:
                try:
                    import memory.memory as mem
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
            logger.error("Shutdown save error: %s", e)

        # Stop ambient movement
        if self._ambient_movement:
            self._ambient_movement.stop()

        # Stop metronome
        if self._metronome and self._metronome.is_running:
            self._metronome.stop()

        # Stop hand tracker
        if self._hand_tracker and self._hand_tracker.is_tracking:
            self._hand_tracker.stop()

        # Stop dance
        if self._dance_choreographer and self._dance_choreographer.is_dancing:
            self._dance_choreographer.stop()

        # Stop freestyle
        if self._freestyle_rapper and self._freestyle_rapper.is_performing:
            self._freestyle_rapper.stop()

        # Stop home monitor
        if self._home_monitor and self._home_monitor.is_running:
            self._home_monitor.stop()

        # Stop gait analyzer
        if self._gait_analyzer and self._gait_analyzer.is_running:
            self._gait_analyzer.stop()

        # Stop attention tracker
        if self._attention_tracker and self._attention_tracker.is_tracking:
            self._attention_tracker.stop()

        # Stop head mirror
        if self._head_mirror and self._head_mirror.is_mirroring:
            self._head_mirror.stop()

        # Stop ambient sounds
        if self._ambient_player and self._ambient_player.is_playing:
            self._ambient_player.stop()

        # Stop musical instrument
        if self._musical_instrument and self._musical_instrument.is_active:
            self._musical_instrument.stop()

        # Stop sound direction tracking
        if self._sound_direction and self._sound_direction.is_tracking:
            self._sound_direction.stop()

        # Stop lullaby
        if self._lullaby_player and self._lullaby_player.is_playing:
            self._lullaby_player.stop()

        # Stop person tracker
        if self._person_tracker and self._person_tracker.is_tracking:
            self._person_tracker.stop()

        # Stop bump detector
        if self._bump_detector and self._bump_detector.is_running:
            self._bump_detector.stop()

        # Disconnect robot
        if self._robot:
            try:
                self._robot.reset()
                self._robot.disconnect()
            except Exception:
                pass

    # ── Process user transcript ───────────────────────────────────

    def _process_user_transcript(self, text: str) -> None:
        if not text or len(text.strip()) < 2:
            return

        self._interaction_count += 1
        self._chat_history.append({"role": "user", "content": text})
        lower = text.lower()

        # Emotion detection
        emotion = self._detect_emotion(text)
        self._mood_history.append(emotion)
        self._conversation_turns.append(("patient", text, emotion))

        # Humor learning — track what makes them laugh
        humor_words = ["haha", "ha ha", "lol", "that's funny", "you're funny", "hilarious",
                       "cracking me up", "too funny", "good one", "made me laugh",
                       "that's a good one", "stop it", "you're killing me",
                       "oh that's rich", "i love that", "classic", "oh my",
                       "you crack me up", "that tickled me", "oh stop"]
        if emotion == "joy" and any(w in lower for w in humor_words):
            humor_ctx = self._current_topic or "general"
            self._humor_hits.append(humor_ctx)
            if len(self._humor_hits) > 20:
                self._humor_hits = self._humor_hits[-20:]
            logger.info("Humor hit recorded: %s", humor_ctx)

        # Emotional repair — detect if Reachy caused a mood drop
        if (len(self._mood_history) >= 2
                and self._last_bot_emotion_before in ("joy", "surprise", "neutral")
                and emotion in ("sadness", "fear", "anger")
                and self._chat_history
                and len(self._chat_history) >= 2
                and self._chat_history[-2].get("role") == "assistant"):
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_emotional_repair(), self._loop
                )

        # Deep topic detection — patient opening up about something meaningful
        deep_triggers = ["passed away", "passed on", "died", "funeral", "miss them",
                         "lost my", "losing my", "gone now", "no longer with us",
                         "cancer", "diagnosis", "terminal", "hospice", "dementia",
                         "divorce", "separated", "war", "served in", "scared of dying",
                         "when i was young", "my childhood", "i never told anyone",
                         "hardest thing", "biggest regret", "wish i had", "before i go",
                         "i'm afraid", "i don't want to be alone", "nobody visits",
                         "i miss my", "my late", "after they died", "the accident",
                         "i was abused", "we lost the baby", "my biggest fear"]
        if any(t in lower for t in deep_triggers):
            self._deep_topic_active = True
            logger.info("Deep topic detected — slowing down")
        elif self._deep_topic_active and emotion in ("joy", "neutral", "surprise"):
            self._deep_topic_active = False

        # ── Engagement scoring (0-10) ─────────────────────────────
        word_count = len(text.strip().split())
        self._energy_trajectory.append(word_count)
        if len(self._energy_trajectory) > 30:
            self._energy_trajectory = self._energy_trajectory[-30:]
        unique_emotions = len(set(self._mood_history[-6:])) if len(self._mood_history) >= 3 else 1
        length_score = min(word_count / 5, 4)  # 0-4 points for response length
        emotion_score = min(unique_emotions, 3)  # 0-3 points for emotion variety
        topic_score = min(len(set(self._topics_discussed[-5:])), 3) if self._topics_discussed else 0  # 0-3 points
        engagement = round(length_score + emotion_score + topic_score, 1)
        self._engagement_scores.append(engagement)
        if len(self._engagement_scores) > 30:
            self._engagement_scores = self._engagement_scores[-30:]

        # ── Topic-mood mapping (for avoidance learning) ───────────
        if self._current_topic and self._current_topic != "general":
            if self._current_topic not in self._topic_mood_map:
                self._topic_mood_map[self._current_topic] = []
            self._topic_mood_map[self._current_topic].append(emotion)
            if len(self._topic_mood_map[self._current_topic]) > 15:
                self._topic_mood_map[self._current_topic] = self._topic_mood_map[self._current_topic][-15:]

        # ── Name dropping detection ───────────────────────────────
        import re as _re
        name_patterns = [
            (r"my (?:daughter|son|wife|husband|sister|brother|friend|neighbor|doctor|grandson|granddaughter|niece|nephew|aunt|uncle|cousin|buddy|pal|mate|partner|fiancee?)\s+([A-Z][a-z]+)", "family/friend"),
            (r"(?:called|named|name is|name's|name was)\s+([A-Z][a-z]+)", "named person"),
            (r"([A-Z][a-z]+),?\s+my\s+(?:daughter|son|wife|husband|sister|brother|friend|grandson|granddaughter)", "family/friend"),
            (r"my late\s+(?:husband|wife|mother|father|brother|sister)\s+([A-Z][a-z]+)", "deceased loved one"),
            (r"(?:nurse|doctor|caregiver|therapist)\s+([A-Z][a-z]+)", "care provider"),
        ]
        for pattern, ctx in name_patterns:
            match = _re.search(pattern, text, _re.IGNORECASE)
            if match:
                name = match.group(1)
                # Name must start with uppercase (real name, not a verb)
                if name[0].isupper() and name not in self._mentioned_names:
                    # Capture the surrounding context
                    start = max(0, match.start() - 20)
                    snippet = text[start:match.end() + 20].strip()
                    self._mentioned_names[name] = snippet
                    logger.info("Name captured: %s (%s)", name, snippet)

        # ── Confusion recovery detection ──────────────────────────
        confusion_signals = ["what?", "huh?", "i don't understand", "what do you mean",
                             "say that again", "i'm confused", "you lost me", "repeat that",
                             "what did you say", "sorry?", "pardon?", "come again",
                             "i didn't get that", "that doesn't make sense", "too fast",
                             "slow down", "what are you talking about", "i don't follow",
                             "can you explain", "say it simpler"]
        if any(s in lower for s in confusion_signals):
            self._confusion_count += 1
        else:
            self._confusion_count = 0

        # ── Celebration detection ─────────────────────────────────
        celebration_triggers = ["i walked today", "i did it", "good news", "my daughter visited",
                                "my son came", "i finished", "i made it", "doctor said i'm",
                                "i cooked", "i went outside", "i slept well", "i feel great",
                                "i'm proud", "guess what", "you won't believe",
                                "i got a letter", "they called me", "i won", "i remembered",
                                "i managed to", "i finally", "first time in", "i stood up",
                                "i ate everything", "i took my medicine", "i dressed myself",
                                "my grandchild", "they're coming to visit", "i painted",
                                "i read a whole", "i solved", "i beat"]
        if any(t in lower for t in celebration_triggers) or (emotion == "joy" and word_count > 10):
            self._celebration_active = True
            # Play celebration sound
            if self._sound_effects:
                self._sound_effects.play("tada")
        else:
            self._celebration_active = False

        # ── Repeated story detection ──────────────────────────────
        # Use a short fingerprint (first 6 words) to detect retold stories
        words = text.strip().split()
        if len(words) >= 6:
            fingerprint = " ".join(w.lower() for w in words[:6])
            self._repeated_stories[fingerprint] = self._repeated_stories.get(fingerprint, 0) + 1

        # ── Silence / flat response tracking ─────────────────────
        flat_words = {"fine", "okay", "ok", "good", "alright", "sure", "yes", "no", "yeah", "nope"}
        if word_count <= 3 or (word_count <= 5 and all(w.lower() in flat_words for w in words)):
            self._silence_turns += 1
        else:
            self._silence_turns = 0

        # ── Flat emotional vocabulary tracking ───────────────────
        if emotion == "neutral" and word_count <= 5 and any(w in lower for w in ["fine", "okay", "ok", "alright"]):
            self._flat_emotion_count += 1
        else:
            self._flat_emotion_count = 0

        # ── Conversation momentum tracking ───────────────────────
        if (self._current_topic and self._current_topic == getattr(self, "_prev_topic", None)
                and word_count >= 10 and emotion in ("joy", "surprise", "neutral")):
            self._topic_flow_turns += 1
        else:
            self._topic_flow_turns = 0
        self._prev_topic = self._current_topic

        # ── Best engagement hour tracking ─────────────────────────
        if self._engagement_scores:
            current_hour = int(time.strftime("%H"))
            if not hasattr(self, "_hourly_engagement"):
                self._hourly_engagement: dict = {}
            bucket = self._hourly_engagement.setdefault(current_hour, [])
            bucket.append(self._engagement_scores[-1])
            if len(bucket) > 20:
                self._hourly_engagement[current_hour] = bucket[-20:]
            # Find best hour
            if len(self._hourly_engagement) >= 2:
                best_hour = max(self._hourly_engagement,
                                key=lambda h: sum(self._hourly_engagement[h]) / len(self._hourly_engagement[h]))
                self._best_engagement_hour = best_hour

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

        # Ambient movement — update emotion and state
        if self._ambient_movement:
            self._ambient_movement.set_emotion(emotion)
            self._ambient_movement.on_listening()
            # Mirror strong emotions
            if emotion in ("joy", "sadness", "surprise", "fear"):
                threading.Thread(
                    target=self._ambient_movement.trigger_mirror,
                    args=(emotion,), daemon=True,
                ).start()

        # Night mode — check for distress and auto-activate/deactivate
        if self._night_companion:
            activation = self._night_companion.check_and_activate()
            distress_response = self._night_companion.check_distress(text)
            if distress_response and self._loop:
                # Escalate if 3+ distress events
                if self._night_companion._distress_count >= 3 and self._alerts:
                    self._alerts.alert_night_distress(text)
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(
                        f"(Night mode: patient may be in distress. Respond gently: {distress_response})"
                    ), self._loop,
                )

        # Photo album — handle narration requests
        self._handle_photo_album(text)

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

        # Radio DJ — voice commands
        self._handle_radio(text)

        # Night mode — sleep stories
        self._handle_night_story(text)

        # Freestyle rapper — voice commands
        self._handle_freestyle(text)

        # Custom personalities — voice commands
        self._handle_personality(text)

        # Metronome — voice commands
        self._handle_metronome(text)

        # Coding assistant — voice commands
        self._handle_coding(text)

        # Translator — voice commands
        self._handle_translate(text)

        # Hand tracker — voice commands
        self._handle_hand_tracking(text)

        # Dance — voice commands
        self._handle_dance(text)

        # Chess — voice commands
        self._handle_chess(text)

        # Home monitor — voice commands
        self._handle_home_monitor(text)

        # Stargazing — voice commands
        self._handle_stargazing(text)

        # Routine coach — voice commands
        self._handle_routine(text)

        # Sketch renderer — voice commands
        self._handle_sketch(text)

        # Drawing coach — voice commands
        self._handle_drawing(text)

        # Adaptive trivia — voice commands
        self._handle_adaptive_trivia(text)

        # Video call — voice commands
        self._handle_video_call(text)

        # Body movement — direct commands
        self._handle_body_command(text)

        # Speech pattern analysis (passive — runs on every utterance)
        if self._speech_analyzer:
            self._speech_analyzer.analyze_utterance(text)

        # Nutrition tracking (passive — detects meal/drink mentions)
        if self._nutrition:
            intake_msg = self._nutrition.check_intake(text)
            # Don't inject — just log silently

        # Topic tracking
        self._track_topic(lower)

        # Name extraction
        self._try_learn_name(text)

        # Fact extraction
        self._extract_facts(text)

        # Pattern-based mentions
        try:
            from brain.followups import remember_mention
            remember_mention(text)
        except Exception:
            pass

        # GPT smart mention extraction (background)
        def _smart_extract():
            try:
                from brain.followups import smart_extract_mentions
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
                    import memory.db_supabase as _db
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
                    import memory.vector_memory as vmem
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
                    import memory.knowledge_graph as kg
                    kg.extract_and_store(text, self._patient_id)
                except Exception:
                    pass
            threading.Thread(target=_kg, daemon=True).start()

        # RAG memory
        if self._rag_enabled:
            def _rag():
                try:
                    import memory.memory as mem
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
        # (word_count already computed above in engagement scoring)
        if word_count <= 4:
            self._consecutive_short += 1
        else:
            self._consecutive_short = 0

        if self._consecutive_short >= 3 and self._loop:
            self._consecutive_short = 0  # reset so we don't spam
            asyncio.run_coroutine_threadsafe(
                self._suggest_topic(), self._loop
            )

    def _process_assistant_transcript(self, text: str) -> None:
        if not text or len(text.strip()) < 2:
            return

        self._chat_history.append({"role": "assistant", "content": text})
        self._conversation_turns.append(("assistant", text, ""))

        # Track emotion state before this response (for emotional repair detection)
        if self._mood_history:
            self._last_bot_emotion_before = self._mood_history[-1]

        # Question fatigue tracking — count consecutive questions from Reachy
        if text.rstrip().endswith("?"):
            self._consecutive_questions += 1
        else:
            self._consecutive_questions = 0

        # Encouragement tracking — detect when Reachy gives a compliment
        encouragement_words = ["proud of you", "great job", "well done", "that's wonderful",
                               "amazing", "i'm impressed", "you're doing great", "good for you",
                               "that's fantastic", "love that", "that's so nice", "beautiful"]
        lower_bot = text.lower()
        if any(w in lower_bot for w in encouragement_words):
            self._last_encouragement_turn = self._interaction_count

        # Body-aware response — detect when GPT describes body movements and execute them
        if self._robot:
            body_triggers = {
                "wiggl": "wiggle",
                "antenna": "wiggle",
                "nod": "nod",
                "nodding": "nod",
                "shake my head": "shake",
                "shaking my head": "shake",
                "tilt": "curious",
                "tilting": "curious",
                "danc": "dance",
                "bow": "bow",
                "bowing": "bow",
                "peek": "peek",
                "peekaboo": "peek",
                "look around": "look around",
                "looking around": "look around",
                "stretch": "stretch",
                "excited bounce": "excited",
                "bouncing": "excited",
                "lean in": "empathy",
                "leaning in": "empathy",
            }
            for trigger, action in body_triggers.items():
                if trigger in lower_bot:
                    threading.Thread(
                        target=self._robot.perform, args=(action,), daemon=True
                    ).start()
                    logger.info("Body-aware response: '%s' → %s", trigger, action)
                    break  # only one movement per response

        # Sound-aware response — detect when GPT mentions sounds and play them
        if self._sound_effects:
            sound_triggers = {
                "ta-da": "tada",
                "ta da": "tada",
                "ding ding": "ding",
                "ding!": "ding",
                "drumroll": "drumroll",
                "drum roll": "drumroll",
                "applause": "applause",
                "round of applause": "applause",
                "buzzer": "buzzer",
                "level up": "levelup",
            }
            for trigger, sound in sound_triggers.items():
                if trigger in lower_bot:
                    self._sound_effects.play(sound)
                    logger.info("Sound-aware response: '%s' → %s", trigger, sound)
                    break

        # Audiobook story movements — move expressively while reading
        if self._audiobook and self._audiobook.is_reading and self._robot:
            movement = self._audiobook.get_movement_for_text(text)
            if movement:
                threading.Thread(
                    target=self._robot.perform, args=(movement,), daemon=True
                ).start()

        # Post to dashboard live chat
        threading.Thread(target=self._post_to_dashboard, args=("reachy", text), daemon=True).start()

        # Robot: reset to neutral after speaking (only if no body movement was triggered)
        # (body-aware response above handles movement — don't reset immediately)

        # Ambient movement — back to idle after speaking
        if self._ambient_movement:
            self._ambient_movement.on_idle()

        if self._db_available:
            def _db_log():
                try:
                    import memory.db_supabase as _db
                    topic = self._current_topic or "general"
                    _db.save_conversation(topic, text, self._patient_id, "assistant", "")
                except Exception:
                    pass
            threading.Thread(target=_db_log, daemon=True).start()

        if self._vec_available:
            def _store_vec():
                try:
                    import memory.vector_memory as vmem
                    topic = self._current_topic or "general"
                    vmem.store_bot_response(text, topic=topic, patient_id=self._patient_id)
                except Exception:
                    pass
            threading.Thread(target=_store_vec, daemon=True).start()

        # Record narration for interactive story
        if self._interactive_story and self._interactive_story.is_active:
            self._interactive_story.record_narration(text)

    # ── Safety & care detection ───────────────────────────────────

    def _check_safety(self, text: str) -> None:
        lower = text.lower()
        for kw in _CRISIS_KEYWORDS:
            if kw in lower:
                logger.warning("CRISIS keywords detected")
                self._session_alert_count += 1
                if self._alerts:
                    self._alerts.alert_crisis(text)
                if self._db_available:
                    try:
                        import memory.db_supabase as _db
                        _db.save_alert("CRISIS", f"Patient said: {text[:200]}", severity="critical", patient_id=self._patient_id)
                    except Exception:
                        pass
                self._check_alert_escalation()
                return
        for kw in _EMERGENCY_KEYWORDS:
            if kw in lower:
                logger.warning("EMERGENCY keywords detected")
                self._session_alert_count += 1
                if self._alerts:
                    self._alerts.alert_emergency(text)
                if self._db_available:
                    try:
                        import memory.db_supabase as _db
                        _db.save_alert("EMERGENCY", f"Patient said: {text[:200]}", severity="critical", patient_id=self._patient_id)
                    except Exception:
                        pass
                self._check_alert_escalation()
                return

    def _check_care_requests(self, text: str) -> None:
        lower = text.lower()
        for req_type, keywords in _CARE_REQUEST_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    logger.warning("Care request: %s", req_type)
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
                            import memory.db_supabase as _db
                            _db.save_alert(f"{req_type.upper()}_REQUEST", text[:200], severity="normal", patient_id=self._patient_id)
                        except Exception:
                            pass
                    self._check_alert_escalation()
                    return

    def _check_alert_escalation(self) -> None:
        """If 3+ alerts in one session, escalate to SUSTAINED_DISTRESS."""
        if self._session_alert_count >= 3 and self._session_alert_count % 3 == 0:
            logger.warning("ALERT ESCALATION — %d alerts this session", self._session_alert_count)
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
                    import memory.db_supabase as _db
                    _db.save_alert(
                        "SUSTAINED_DISTRESS",
                        f"Alert escalation: {self._session_alert_count} alerts in one session",
                        severity="critical",
                        patient_id=self._patient_id,
                    )
                except Exception:
                    pass

    def _check_wandering(self, text: str) -> None:
        """Detect spatial disorientation / wandering phrases and alert caregiver."""
        lower = text.lower()
        for kw in _WANDERING_KEYWORDS:
            if kw in lower:
                logger.warning("WANDERING/DISORIENTATION detected")
                if self._alerts:
                    try:
                        self._alerts.alert("WANDERING_ALERT", text[:200])
                    except Exception:
                        pass
                if self._db_available:
                    try:
                        import memory.db_supabase as _db
                        _db.save_alert(
                            "WANDERING_ALERT",
                            f"Possible disorientation — patient said: {text[:200]}",
                            severity="high",
                            patient_id=self._patient_id,
                        )
                    except Exception:
                        pass
                return

    def _check_sundowning(self, text: str) -> None:
        """Detect evening confusion/agitation and respond with calming approach."""
        try:
            from health.sundowning import check_sundowning
            hour = int(time.strftime("%H"))
            if not check_sundowning(text, hour):
                return
        except Exception:
            return

        self._sundowning_count += 1
        logger.info("Sundowning keyword detected (%d this session)", self._sundowning_count)

        if self._sundowning_count >= 3:
            logger.warning("SUNDOWNING ALERT — switching to calming mode")
            # Alert caregiver
            if self._alerts:
                try:
                    self._alerts.alert("SUNDOWNING_ALERT", f"Patient showing signs of sundowning ({self._sundowning_count} triggers). Last: {text[:150]}")
                except Exception:
                    pass
            if self._db_available:
                try:
                    import memory.db_supabase as _db
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

    async def _inject_sundowning_calm(self) -> None:
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
            logger.info("Sundowning calming prompt injected")
        except Exception as e:
            logger.error("Sundowning inject error: %s", e)

    def _check_pain(self, text: str) -> None:
        """Detect pain mentions and inject a follow-up prompt."""
        # Skip if we're already in a pain follow-up cooldown
        if self._pain_followup_cooldown > 0:
            self._pain_followup_cooldown -= 1
            return

        try:
            from health.pain_tracker import detect_pain
            if not detect_pain(text):
                return
        except Exception:
            return

        logger.info("Pain mention detected")
        self._pain_followup_cooldown = 4  # don't re-trigger for 4 turns

        # Alert caregiver
        if self._db_available:
            try:
                import memory.db_supabase as _db
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

    async def _inject_pain_followup(self, original_text: str) -> None:
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
            logger.info("Pain follow-up injected")
        except Exception as e:
            logger.error("Pain follow-up error: %s", e)

    # ── Photo description (vision) ───────────────────────────────

    def _check_vision_request(self, text: str) -> None:
        """Detect 'what do you see' style requests and describe the camera frame."""
        # Check enhanced vision buddy triggers first
        try:
            from activities.vision_buddy import detect_vision_type
            vtype = detect_vision_type(text)
            if vtype:
                logger.info("Vision buddy request: %s", vtype)
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_vision_buddy(text, vtype), self._loop
                    )
                return
        except Exception:
            pass

        # Standard vision request
        try:
            from perception.vision import is_vision_request
            if not is_vision_request(text):
                return
        except Exception:
            return

        logger.info("Vision request detected — capturing frame")
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._inject_vision_description(text), self._loop
            )

    async def _inject_vision_buddy(self, user_text: str, vtype: str) -> None:
        """Enhanced vision — scene description, object ID, text reading, person description."""
        if not self._ws:
            return

        description = await asyncio.get_event_loop().run_in_executor(
            None, self._get_vision_buddy_result, user_text, vtype
        )

        if not description:
            inject = (
                "(The patient asked you to look at something but the camera isn't available. "
                "Apologize and suggest they describe it to you instead.)"
            )
        else:
            context_map = {
                "scene": "describe the room/scene",
                "objects": "identify objects",
                "text": "read text/signs",
                "person": "describe a person",
            }
            inject = (
                f"(The patient asked you to {context_map.get(vtype, 'look')}. "
                f"Here's what you observed: {description}\n"
                f"Share this naturally and conversationally.)"
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
        except Exception as e:
            logger.error("Vision buddy inject error: %s", e)

    def _get_vision_buddy_result(self, user_text: str, vtype: str) -> str | None:
        """Blocking helper for enhanced vision queries."""
        try:
            from perception.vision import capture_frame
            from activities.vision_buddy import describe_scene, identify_objects, read_text, describe_person
            frame_b64 = capture_frame()
            if not frame_b64:
                return None
            fn_map = {
                "scene": describe_scene,
                "objects": identify_objects,
                "text": read_text,
                "person": describe_person,
            }
            fn = fn_map.get(vtype, describe_scene)
            return fn(frame_b64)
        except Exception as e:
            logger.error("Vision buddy error: %s", e)
            return None

    async def _inject_vision_description(self, user_text: str) -> None:
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
            logger.info("Vision description injected")
        except Exception as e:
            logger.error("Vision inject error: %s", e)

    def _get_vision_description(self, user_text: str) -> str | None:
        """Blocking helper — capture frame and call GPT-4o vision."""
        try:
            from perception.vision import capture_frame, describe_image
            frame_b64 = capture_frame()
            if not frame_b64:
                return None
            return describe_image(frame_b64, user_text)
        except Exception as e:
            logger.error("Vision description error: %s", e)
            return None

    # ── Interactive storytelling ──────────────────────────────────

    def _handle_interactive_story(self, text: str) -> None:
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
            from activities.interactive_story import is_story_trigger
            if not is_story_trigger(text):
                return
        except Exception:
            return

        self._start_interactive_story()

    def _start_interactive_story(self) -> None:
        """Start a new interactive story session."""
        try:
            from activities.interactive_story import InteractiveStory
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
            logger.info("Interactive story started")
        except Exception as e:
            logger.error("Story start error: %s", e)

    async def _inject_story_prompt(self, prompt: str) -> None:
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
            logger.error("Story inject error: %s", e)

    # ── Personalized quiz ─────────────────────────────────────────

    def _handle_quiz(self, text: str) -> None:
        """Handle quiz session — answers or trigger."""
        if self._personal_quiz and self._personal_quiz.is_active:
            prompt = self._personal_quiz.check_answer(text)
            if prompt and self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(prompt), self._loop
                )
            return

        try:
            from activities.personal_quiz import is_quiz_trigger
            if not is_quiz_trigger(text):
                return
        except Exception:
            return

        try:
            from activities.personal_quiz import PersonalQuiz
            self._personal_quiz = PersonalQuiz(patient_id=self._patient_id)
            prompt = self._personal_quiz.start()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(prompt), self._loop
                )
            logger.info("Personal quiz started")
        except Exception as e:
            logger.error("Quiz start error: %s", e)

    # ── Sing-along ────────────────────────────────────────────────

    def _handle_singalong(self, text: str) -> None:
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
            from activities.singalong import is_singalong_trigger
            if not is_singalong_trigger(text):
                return
        except Exception:
            return

        try:
            from activities.singalong import SingAlong
            self._singalong = SingAlong()
            prompt = self._singalong.start(text)
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(prompt), self._loop
                )
            logger.info("Sing-along started")
        except Exception as e:
            logger.error("Sing-along start error: %s", e)
    def _handle_radio(self, text: str) -> None:
        """Handle radio DJ voice commands."""
        if not self._radio_dj:
            return
        lower = text.lower()

        # Stop radio
        if self._radio_dj.is_on and any(p in lower for p in [
            "stop the radio", "turn off the radio", "stop music", "stop the music",
            "radio off", "turn off music", "silence", "quiet please",
        ]):
            msg = self._radio_dj.stop()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(You just stopped the radio. Tell the patient: {msg})"),
                    self._loop,
                )
            return

        # Skip track
        if self._radio_dj.is_on and any(p in lower for p in [
            "next song", "skip", "next track", "play something else",
            "change the song", "skip this",
        ]):
            msg = self._radio_dj.skip()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(You skipped to the next song. Tell the patient: {msg})"),
                    self._loop,
                )
            return

        # Song request (while radio is on)
        if self._radio_dj.is_on and any(p in lower for p in [
            "play me", "can you play", "i want to hear", "play some",
            "put on some", "how about some",
        ]):
            msg = self._radio_dj.request(text)
            if msg and self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(You fulfilled a song request. Tell the patient: {msg})"),
                    self._loop,
                )
            return

        # Start radio
        if any(p in lower for p in [
            "play music", "turn on the radio", "play the radio", "radio on",
            "put on some music", "play some music", "i want music",
            "can you play music", "start the radio", "dj mode",
        ]):
            # Update patient name if we know it
            if self._user_name:
                self._radio_dj.set_patient_name(self._user_name)
            msg = self._radio_dj.start()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(You just started Radio Reachy. Tell the patient: {msg})"),
                    self._loop,
                )
            return
    def _handle_photo_album(self, text: str) -> None:
        """Handle photo album narration requests."""
        if not self._photo_narrator:
            return
        lower = text.lower()

        # Stop slideshow
        if self._photo_narrator.is_slideshow_active and any(p in lower for p in [
            "stop slideshow", "stop the slideshow", "no more photos",
            "that's enough photos", "done with photos",
        ]):
            msg = self._photo_narrator.stop_slideshow()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(You stopped the slideshow. Tell the patient: {msg})"),
                    self._loop,
                )
            return

        # Start slideshow
        if any(p in lower for p in ["slideshow", "show you my photos", "look at my photos"]):
            msg = self._photo_narrator.start_slideshow()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Slideshow mode started. Tell the patient: {msg})"),
                    self._loop,
                )
            return

        # Narrate a photo (trigger detection)
        try:
            from activities.photo_album import is_photo_trigger
            if is_photo_trigger(text) or self._photo_narrator.is_slideshow_active:
                # Update facts if we have new ones
                if self._user_facts:
                    self._photo_narrator.set_facts(self._user_facts)
                if self._user_name:
                    self._photo_narrator.set_name(self._user_name)

                def _narrate():
                    desc = self._photo_narrator.narrate(text)
                    if desc and self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(
                                f"(You just looked at a photo the patient is showing you. "
                                f"Here's what you saw: {desc}. Share this description warmly "
                                f"and ask a follow-up question about the photo.)"
                            ), self._loop,
                        )
                threading.Thread(target=_narrate, daemon=True).start()
        except Exception:
            pass

    def _handle_night_story(self, text: str) -> None:
        """Handle sleep story requests during night mode."""
        if not self._night_companion or not self._night_companion.is_active:
            return
        lower = text.lower()

        # Sleep story triggers
        if any(p in lower for p in [
            "tell me a story", "sleep story", "bedtime story",
            "read me a story", "story please", "i can't sleep",
        ]):
            if self._night_companion.has_active_story:
                part = self._night_companion.next_story_part()
            else:
                part = self._night_companion.get_sleep_story()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(
                        f"(Night mode: read this sleep story part very softly and slowly: {part})"
                    ), self._loop,
                )
            return

        # Continue story
        if self._night_companion.has_active_story and any(p in lower for p in [
            "continue", "next", "go on", "more", "then what", "keep going",
        ]):
            part = self._night_companion.next_story_part()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(
                        f"(Night mode: continue the sleep story softly: {part})"
                    ), self._loop,
                )
            return

        # List stories
        if any(p in lower for p in ["what stories", "which stories", "list stories"]):
            stories = self._night_companion.list_stories()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(
                        f"(Night mode: the patient wants to know what stories you have: {stories})"
                    ), self._loop,
                )
            return

    # ── Dance choreographer ───────────────────────────────────────

    def _handle_dance(self, text: str) -> None:
        """Handle dance voice commands."""
        if not self._dance_choreographer:
            return
        lower = text.lower()

        # Stop dancing
        if self._dance_choreographer.is_dancing and any(p in lower for p in [
            "stop dancing", "stop the dance", "enough dancing",
        ]):
            msg = self._dance_choreographer.stop()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Dance stopped. Say: {msg})"),
                    self._loop,
                )
            return

        # Start a specific routine
        triggers = [
            "dance for me", "do a dance", "let's dance", "show me a dance",
            "dance", "bust a move", "dance party",
        ]
        if any(p in lower for p in triggers):
            # Try to extract routine name
            routine = ""
            for name in ("disco", "slow", "robot", "party", "chill"):
                if name in lower:
                    routine = name
                    break
            msg = self._dance_choreographer.dance(routine)
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(
                        f"(You started dancing! Say: {msg} "
                        f"Be enthusiastic about it!)"
                    ), self._loop,
                )
            return

    # ── Chess player ──────────────────────────────────────────────

    def _handle_chess(self, text: str) -> None:
        """Handle chess voice commands."""
        if not self._chess_player:
            return
        lower = text.lower()

        if self._chess_player.is_active and any(p in lower for p in [
            "stop chess", "quit chess", "end the game", "i give up",
        ]):
            msg = self._chess_player.stop_game()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Chess game ended. Say: {msg})"), self._loop)
            return

        if self._chess_player.is_active and any(p in lower for p in [
            "your turn", "your move", "what do you play", "look at the board",
        ]):
            result = self._chess_player.analyze_board()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(
                        f"(You analyzed the chessboard. Share your move and comment: {result})"
                    ), self._loop)
            return

        if self._chess_player.is_active and any(p in lower for p in [
            "i moved", "i played", "my move is", "i go",
        ]):
            result = self._chess_player.describe_move(text)
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(
                        f"(The patient described their chess move. Respond: {result})"
                    ), self._loop)
            return

        if any(p in lower for p in [
            "play chess", "let's play chess", "chess game", "start chess",
        ]):
            msg = self._chess_player.start_game()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Chess game starting! Say: {msg})"), self._loop)
            return

    # ── Home monitor ──────────────────────────────────────────────

    def _handle_home_monitor(self, text: str) -> None:
        if not self._home_monitor:
            return
        lower = text.lower()

        if any(p in lower for p in ["stop monitoring", "monitor off"]):
            msg = self._home_monitor.stop()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Home monitoring stopped. Say: {msg})"), self._loop)
            return

        if any(p in lower for p in [
            "start monitoring", "monitor the room", "watch the room",
            "home monitor", "keep watch",
        ]):
            msg = self._home_monitor.start()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Home monitoring started. Say: {msg})"), self._loop)
            return

        if any(p in lower for p in ["check the room", "is everything okay", "room check"]):
            result = self._home_monitor.check_now()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Room check result: {result})"), self._loop)
            return

    # ── Stargazing buddy ─────────────────────────────────────────

    def _handle_stargazing(self, text: str) -> None:
        if not self._stargazing:
            return
        lower = text.lower()

        if any(p in lower for p in [
            "look at the sky", "what's in the sky", "identify the stars",
            "stargazing", "what constellation",
        ]):
            result = self._stargazing.identify_sky()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(
                        f"(You looked at the sky. Share what you found: {result})"
                    ), self._loop)
            return

        if "tell me about" in lower and any(p in lower for p in [
            "constellation", "orion", "cassiopeia", "leo", "scorpius", "cygnus",
            "ursa", "big dipper",
        ]):
            for name in ["orion", "cassiopeia", "leo", "scorpius", "cygnus", "ursa_major", "big dipper"]:
                if name.replace("_", " ") in lower:
                    info = self._stargazing.constellation_info(name)
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Share constellation info: {info})"), self._loop)
                    return

        if any(p in lower for p in ["tell me about mars", "tell me about jupiter",
                                     "tell me about saturn", "tell me about venus", "tell me about mercury"]):
            for planet in ["mars", "jupiter", "saturn", "venus", "mercury"]:
                if planet in lower:
                    info = self._stargazing.planet_info(planet)
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Share planet info: {info})"), self._loop)
                    return

        if any(p in lower for p in ["space fact", "astronomy fact", "star fact"]):
            fact = self._stargazing.random_fact()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Share this space fact: {fact})"), self._loop)
            return

    # ── Routine coach ─────────────────────────────────────────────

    def _handle_routine(self, text: str) -> None:
        if not self._routine_coach:
            return
        lower = text.lower()

        if any(p in lower for p in [
            "what should i do", "what's next", "daily routine", "my schedule",
            "what's on my schedule", "routine",
        ]):
            suggestion = self._routine_coach.get_suggestion()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Daily routine suggestion: {suggestion})"), self._loop)
            return

        if any(p in lower for p in ["done", "finished", "completed", "i did it"]):
            if self._routine_coach.get_current_activity():
                msg = self._routine_coach.complete_activity()
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(f"(Activity completed! Say: {msg})"), self._loop)
                return

        if any(p in lower for p in ["skip", "not today", "too tired"]):
            msg = self._routine_coach.skip_activity()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Activity skipped. Say: {msg})"), self._loop)
            return

        if any(p in lower for p in ["i'm tired", "feeling tired", "low energy", "exhausted"]):
            msg = self._routine_coach.set_energy("low")
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Patient is tired. Say: {msg})"), self._loop)
            return

    # ── Sketch renderer ───────────────────────────────────────────

    def _handle_sketch(self, text: str) -> None:
        if not self._sketch_renderer:
            return
        lower = text.lower()

        if any(p in lower for p in [
            "render my sketch", "turn my drawing into", "render this",
            "make my sketch real", "sketch to render",
        ]):
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(
                        "(The patient wants you to render their sketch. Tell them to hold it up "
                        "to the camera and you'll create a polished version.)"
                    ), self._loop)

                def _do_render():
                    result = self._sketch_renderer.render_sketch()
                    if result.get("error"):
                        msg = result["error"]
                    else:
                        msg = f"I turned your sketch into a rendering! {result.get('description', '')}"
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Sketch render result: {msg})"), self._loop)

                threading.Thread(target=_do_render, daemon=True).start()
            return

    # ── Drawing coach ─────────────────────────────────────────────

    def _handle_drawing(self, text: str) -> None:
        if not self._drawing_coach:
            return
        lower = text.lower()

        if any(p in lower for p in [
            "drawing prompt", "give me something to draw", "let's draw",
            "drawing idea", "what should i draw",
        ]):
            category = ""
            for cat in ("nature", "family", "seasons", "memories", "simple"):
                if cat in lower:
                    category = cat
                    break
            prompt = self._drawing_coach.get_prompt(category)
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Drawing prompt: {prompt})"), self._loop)
            return

        if self._drawing_coach.is_active and any(p in lower for p in [
            "i'm done drawing", "finished drawing", "look at my drawing",
            "i drew it", "capture my drawing",
        ]):
            result = self._drawing_coach.capture_drawing()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(
                        f"(The patient finished their drawing. Describe it warmly: {result})"
                    ), self._loop)
            return

        if self._drawing_coach.is_active and any(p in lower for p in [
            "how does it look", "what do you think", "is it good",
        ]):
            msg = self._drawing_coach.encourage()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Encourage the patient's drawing: {msg})"), self._loop)
            return

    # ── Adaptive trivia ───────────────────────────────────────────

    def _handle_adaptive_trivia(self, text: str) -> None:
        if not self._adaptive_trivia:
            return
        lower = text.lower()

        if self._adaptive_trivia.is_active:
            response = self._adaptive_trivia.answer(text)
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Trivia response: {response})"), self._loop)
            return

        if any(p in lower for p in [
            "trivia", "quiz me", "trivia game", "play trivia",
            "test my knowledge", "ask me questions",
        ]):
            category = ""
            for cat in ("history", "music", "nature", "sports"):
                if cat in lower:
                    category = cat
                    break
            msg = self._adaptive_trivia.start(category)
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Trivia game starting! Ask: {msg})"), self._loop)
            return

    # ── Video call assistant ──────────────────────────────────────

    def _handle_video_call(self, text: str) -> None:
        if not self._video_call:
            return
        lower = text.lower()

        if self._video_call.is_call_active and any(p in lower for p in [
            "hang up", "end the call", "goodbye call", "end call",
        ]):
            msg = self._video_call.end_call()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Call ended. Say: {msg})"), self._loop)
            return

        if any(p in lower for p in [
            "call my", "call ", "video call", "phone call",
        ]) and any(p in lower for p in [
            "daughter", "son", "wife", "husband", "family", "friend",
            "sister", "brother", "mom", "dad",
        ]):
            # Extract who to call
            for rel in ["daughter", "son", "wife", "husband", "sister", "brother",
                        "mom", "dad", "friend", "family"]:
                if rel in lower:
                    msg = self._video_call.initiate_call(rel)
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Video call request: {msg})"), self._loop)
                    return

    # ── Body movement commands ──────────────────────────────────

    def _handle_body_command(self, text: str) -> None:
        """Handle direct body movement requests from the patient."""
        if not self._robot:
            return
        lower = text.lower()

        # Head mirroring toggle
        if self._head_mirror:
            if any(p in lower for p in [
                "mirror me", "copy me", "follow my head", "mirror my head",
                "copy my movements", "mimic me", "do what i do",
            ]):
                if not self._head_mirror.is_mirroring:
                    # Pause attention tracker while mirroring
                    if self._attention_tracker and self._attention_tracker.is_tracking:
                        self._attention_tracker.stop()
                    msg = self._head_mirror.start()
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(
                                f"(Head mirroring activated. Say enthusiastically: {msg})"
                            ), self._loop)
                return
            if any(p in lower for p in [
                "stop mirroring", "stop copying", "stop following",
                "don't copy me", "stop mimicking",
            ]):
                if self._head_mirror.is_mirroring:
                    msg = self._head_mirror.stop()
                    # Resume attention tracker
                    if self._attention_tracker:
                        self._attention_tracker.start()
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(
                                f"(Head mirroring stopped. Say: {msg})"
                            ), self._loop)
                return

        # Camera intelligence commands
        cam_triggers = {
            "show and tell": "show_and_tell",
            "what is this": "show_and_tell",
            "what am i holding": "show_and_tell",
            "look at this": "show_and_tell",
            "what's this": "show_and_tell",
            "how do i look": "compliment_clothing",
            "compliment me": "compliment_clothing",
            "what am i wearing": "compliment_clothing",
            "do you like my outfit": "compliment_clothing",
            "look at my art": "describe_art",
            "what do you think of this": "describe_art",
            "look at this painting": "describe_art",
            "look at this photo": "describe_art",
            "is there a pet": "detect_pet",
            "do you see my dog": "detect_pet",
            "do you see my cat": "detect_pet",
            "what am i doing": "detect_activity",
            "what's the weather outside": "weather_window",
            "look out the window": "weather_window",
            "check my pill": "check_medication",
            "look at my medicine": "check_medication",
        }
        for phrase, action in cam_triggers.items():
            if phrase in lower:
                def _do_cam(a=action):
                    import perception.camera_intelligence as ci
                    funcs = {
                        "show_and_tell": ci.show_and_tell,
                        "compliment_clothing": ci.compliment_clothing,
                        "describe_art": ci.describe_art,
                        "detect_pet": ci.detect_pet,
                        "detect_activity": ci.detect_activity,
                        "weather_window": ci.describe_weather_from_window,
                        "check_medication": ci.check_medication,
                    }
                    result = funcs[a]()
                    if result and self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(
                                f"(Camera observation: {result}. Share this naturally.)"
                            ), self._loop)
                threading.Thread(target=_do_cam, daemon=True).start()
                return

        # Reaction time game
        if self._reaction_game:
            if self._reaction_game.is_active:
                if any(p in lower for p in ["now", "got it", "there", "bang"]):
                    msg = self._reaction_game.player_reacts()
                    if msg and self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Reaction game: {msg})"), self._loop)
                    return
                if any(p in lower for p in ["stop reaction", "quit", "end game"]):
                    msg = self._reaction_game.end()
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Reaction game: {msg})"), self._loop)
                    return
                return

            if any(p in lower for p in ["reaction game", "reaction time", "reflex game",
                                         "test my reflexes", "how fast am i"]):
                msg = self._reaction_game.start()
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(
                            f"(Reaction time game! Say: 'Let's test your reflexes! "
                            f"Watch me — say NOW the instant I move. Ready?' Then: {msg})"
                        ), self._loop)
                return

        # Rhythm game
        if self._rhythm_game:
            if self._rhythm_game.is_active:
                if any(p in lower for p in ["stop rhythm", "end rhythm", "quit rhythm"]):
                    msg = self._rhythm_game.end()
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Rhythm game: {msg})"), self._loop)
                    return
                if any(p in lower for p in ["done", "got it", "i did it", "finished"]):
                    msg = self._rhythm_game.player_done()
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Rhythm game: {msg})"), self._loop)
                    return
                return  # absorb other input during rhythm game

            if any(p in lower for p in ["rhythm game", "beat game", "clapping game",
                                         "tap a beat", "play a rhythm"]):
                msg = self._rhythm_game.start()
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(
                            f"(Rhythm game started! Say: 'Let's play a rhythm game! "
                            f"I'll tap out a beat and you clap along. Ready?' Then: {msg})"
                        ), self._loop)
                return

        # Emotion charades game
        if self._charades:
            if self._charades.is_active:
                if any(p in lower for p in ["stop charades", "end charades", "quit charades",
                                             "stop the game"]):
                    msg = self._charades.end()
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Charades: {msg})"), self._loop)
                    return
                msg = self._charades.check_guess(text)
                if msg and self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(f"(Charades: {msg})"), self._loop)
                return

            if any(p in lower for p in ["charades", "emotion game", "guess the emotion",
                                         "act out emotions", "emotion charades"]):
                msg = self._charades.start()
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(
                            f"(Emotion charades started! Say: 'Let's play emotion charades! "
                            f"I'll act out an emotion with my body and you guess what I'm feeling. "
                            f"Ready? Watch carefully!' Then: {msg})"
                        ), self._loop)
                return

        # Move recorder — teach Reachy custom moves
        if self._move_recorder:
            if self._move_recorder.is_recording:
                if any(p in lower for p in ["done", "stop teaching", "finished teaching",
                                             "that's it", "save it", "i'm done"]):
                    msg = self._move_recorder.stop_teaching()
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Move teaching: {msg})"), self._loop)
                    return
                # While recording, don't process other commands
                return

            if any(p in lower for p in ["teach you a move", "learn a move", "teach you",
                                         "learn this", "record a move", "new move"]):
                # Extract move name
                name = "custom move"
                for prefix in ["called ", "named ", "teach you "]:
                    if prefix in lower:
                        name = lower.split(prefix, 1)[1].strip().rstrip("?.!")[:30]
                        break
                msg = self._move_recorder.start_teaching(name)
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(f"(Move teaching: {msg})"), self._loop)
                return

            # Play a custom move
            if any(p in lower for p in ["do the ", "play the ", "show me the "]):
                for prefix in ["do the ", "play the ", "show me the "]:
                    if prefix in lower:
                        name = lower.split(prefix, 1)[1].strip().rstrip("?.!")
                        if name and name in [m.lower() for m in self._move_recorder.list_moves()]:
                            msg = self._move_recorder.play(name)
                            if self._loop:
                                asyncio.run_coroutine_threadsafe(
                                    self._inject_story_prompt(f"(Custom move: {msg})"), self._loop)
                            return
                        break

            if any(p in lower for p in ["what moves do you know", "list moves",
                                         "show me your moves", "what can you do"]):
                moves = self._move_recorder.list_moves()
                if moves:
                    msg = f"I know these custom moves: {', '.join(moves)}. Say 'do the [name]' to see one!"
                else:
                    msg = "I haven't learned any custom moves yet. Say 'teach you a move' to teach me!"
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(f"(Custom moves: {msg})"), self._loop)
                return

        # Audiobook reader
        if self._audiobook:

            # Object look-at commands
            if self._object_looker:
                if any(p in lower for p in ["look at the ", "look at my ", "find the ",
                                             "where is the ", "where's the "]):
                    # Extract object name
                    for prefix in ["look at the ", "look at my ", "find the ",
                                   "where is the ", "where's the "]:
                        if prefix in lower:
                            obj = lower.split(prefix, 1)[1].strip().rstrip("?.!")
                            if obj:
                                def _do_look(o=obj):
                                    result = self._object_looker.look_at(o)
                                    if self._loop:
                                        asyncio.run_coroutine_threadsafe(
                                            self._inject_story_prompt(
                                                f"(You looked for '{o}' in the room. Result: {result}. "
                                                f"Describe what you see naturally.)"
                                            ), self._loop)
                                threading.Thread(target=_do_look, daemon=True).start()
                                return
                            break

                if any(p in lower for p in ["look around the room", "describe the room",
                                             "what's around me", "survey the room"]):
                    def _do_room_scan():
                        result = self._object_looker.scan_room()
                        if self._loop:
                            asyncio.run_coroutine_threadsafe(
                                self._inject_story_prompt(
                                    f"(You slowly looked around the room. Here's what you saw: "
                                    f"{result}. Describe it warmly and naturally.)"
                                ), self._loop)
                    threading.Thread(target=_do_room_scan, daemon=True).start()
                    return

                if any(p in lower for p in ["scan the room", "what objects", "list objects",
                                             "what can you see around"]):
                    def _do_scan():
                        result = self._object_looker.scan_objects()
                        if self._loop:
                            asyncio.run_coroutine_threadsafe(
                                self._inject_story_prompt(
                                    f"(You scanned the room. {result})"
                                ), self._loop)
                    threading.Thread(target=_do_scan, daemon=True).start()
                    return

                # Spatial memory — "where did you see my glasses?"
                if any(p in lower for p in ["where did you see", "where was the",
                                             "where are my", "remember where"]):
                    result = self._object_looker.get_spatial_memory()
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Spatial memory: {result})"), self._loop)
                    return

                # Brightness/light check — "is it bright in here?"
                if any(p in lower for p in ["is it bright", "is it dark", "how's the light",
                                             "is it light", "how bright"]):
                    desc, val = self._object_looker.detect_brightness()
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(
                                f"(You checked the room brightness: it's {desc}. "
                                f"Comment on it naturally.)"
                            ), self._loop)
                    return

                # Distance check — "how far am I?"
                if any(p in lower for p in ["how far am i", "how close am i",
                                             "can you see me", "am i close"]):
                    result = self._object_looker.estimate_distance()
                    if result:
                        desc, dist = result
                        if self._loop:
                            asyncio.run_coroutine_threadsafe(
                                self._inject_story_prompt(
                                    f"(You estimated the patient is {desc} — about {dist:.1f} meters. "
                                    f"Comment naturally.)"
                                ), self._loop)
                    return

        # Body rotation — "turn left" / "turn right"
        if self._robot and not self._robot._sim_mode and self._robot.mini:
            if any(p in lower for p in ["turn left", "face left", "rotate left"]):
                try:
                    self._robot.mini.set_target_body_yaw(0.4)  # radians, positive = left
                except Exception:
                    pass
                return
            if any(p in lower for p in ["turn right", "face right", "rotate right"]):
                try:
                    self._robot.mini.set_target_body_yaw(-0.4)
                except Exception:
                    pass
                return
            if any(p in lower for p in ["face me", "face forward", "turn forward", "center yourself"]):
                try:
                    self._robot.mini.set_target_body_yaw(0.0)
                except Exception:
                    pass
                return

            if self._audiobook.is_reading:
                if any(p in lower for p in ["stop reading", "stop the story", "enough reading",
                                             "stop the book", "that's enough"]):
                    prompt = self._audiobook.stop()
                    if prompt and self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(prompt), self._loop)
                    return
                if any(p in lower for p in ["keep going", "continue", "next page",
                                             "what happens next", "go on", "more",
                                             "yes please", "yes continue"]):
                    prompt = self._audiobook.next_page()
                    if prompt and self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(prompt), self._loop)
                    return

            if any(p in lower for p in ["read me a story", "read a story", "tell me a story",
                                         "read me a book", "audiobook", "storytime",
                                         "read to me", "story time"]):
                genre = "fairy tale"
                for g in ["adventure", "mystery", "memory", "nature", "funny"]:
                    if g in lower:
                        genre = g if g != "memory" else "memory lane"
                        break
                prompt = self._audiobook.start(genre)
                if prompt and self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(prompt), self._loop)
                return

        # Musical instrument mode
        if self._musical_instrument:
            if self._musical_instrument.is_active:
                if any(p in lower for p in ["stop instrument", "stop music mode",
                                             "instrument off", "stop playing notes"]):
                    msg = self._musical_instrument.stop()
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Instrument mode: {msg})"), self._loop)
                    return
                # Play specific notes
                import re as _note_re
                note_match = _note_re.search(r"play\s+([A-Ga-g][#b]?\d?)", lower)
                if note_match:
                    note = note_match.group(1).upper()
                    if not note[-1].isdigit():
                        note += "4"
                    msg = self._musical_instrument.play_note(note)
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Instrument: {msg})"), self._loop)
                    return
                # Play melodies
                if any(p in lower for p in ["play twinkle", "twinkle twinkle"]):
                    msg = self._musical_instrument.play_melody("twinkle")
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Playing melody: {msg})"), self._loop)
                    return
                if any(p in lower for p in ["play a scale", "play the scale"]):
                    msg = self._musical_instrument.play_melody("scale")
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Playing melody: {msg})"), self._loop)
                    return
                if any(p in lower for p in ["play a melody", "play something", "play a song",
                                             "play a lullaby", "play happy"]):
                    name = "lullaby" if "lullaby" in lower else "happy" if "happy" in lower else "twinkle"
                    msg = self._musical_instrument.play_melody(name)
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Playing melody: {msg})"), self._loop)
                    return

            # Start instrument mode
            if any(p in lower for p in ["instrument mode", "music mode", "play notes",
                                         "be an instrument", "antenna music",
                                         "play me some notes", "musical mode"]):
                msg = self._musical_instrument.start()
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(
                            f"(Musical instrument mode activated! Say: {msg})"
                        ), self._loop)
                return

        # Sound guessing game
        if self._sound_game:
            # Active game — intercept answers
            if self._sound_game.is_active:
                if any(p in lower for p in ["give up", "i give up", "skip", "next sound",
                                             "i don't know", "no idea", "pass"]):
                    msg = self._sound_game.give_up()
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Sound game: {msg})"), self._loop)
                    return
                if any(p in lower for p in ["stop game", "end game", "quit game", "stop playing"]):
                    msg = self._sound_game.end()
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Sound game ended: {msg})"), self._loop)
                    return
                # Check their guess
                msg = self._sound_game.check_answer(text)
                if msg and self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(f"(Sound game: {msg})"), self._loop)
                return

            # Start game
            if any(p in lower for p in ["sound game", "guessing game", "guess the sound",
                                         "play a guessing game", "sound quiz"]):
                category = ""
                if "animal" in lower:
                    category = "animals"
                elif "instrument" in lower or "music" in lower:
                    category = "instruments"
                elif "nature" in lower:
                    category = "nature"
                msg = self._sound_game.start(category)
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(
                            f"(Sound guessing game started! Say enthusiastically: "
                            f"'Let's play a sound guessing game! I'll play a sound and you "
                            f"guess what it is. Ready? Here's the first one!' Then: {msg})"
                        ), self._loop)
                return

        # Sound memory game (Simon-style)
        if self._sound_memory:
            if self._sound_memory.is_active:
                if any(p in lower for p in ["stop memory", "stop simon", "quit memory",
                                             "end memory game"]):
                    msg = self._sound_memory.end()
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Memory game: {msg})"), self._loop)
                    return
                # Check their color input
                msg = self._sound_memory.check_input(text)
                if msg and self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(f"(Memory game: {msg})"), self._loop)
                return

            if any(p in lower for p in ["memory game", "simon game", "simon says game",
                                         "sound memory", "repeat the sounds",
                                         "play simon", "sequence game"]):
                msg = self._sound_memory.start()
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(
                            f"(Sound memory game started! Say: 'Let's play a memory game! "
                            f"I'll play a sequence of tones — each one is a color: red, blue, "
                            f"green, or yellow. Listen carefully and repeat them back to me. "
                            f"Ready? Here we go!' Then: {msg})"
                        ), self._loop)
                return

        # Sound effect requests
        if self._sound_effects:
            sound_triggers = {
                "play a ding": "ding",
                "ding sound": "ding",
                "play a buzzer": "buzzer",
                "buzzer sound": "buzzer",
                "play applause": "applause",
                "clap for me": "applause",
                "drumroll": "drumroll",
                "play a drumroll": "drumroll",
                "ta da": "tada",
                "tada": "tada",
                "play a sound": "ding",
                "make a sound": "ding",
                "play hello": "hello",
                "play goodbye": "goodbye",
                "level up": "levelup",
            }
            for phrase, sound in sound_triggers.items():
                if phrase in lower:
                    self._sound_effects.play(sound)
                    return

        # Ambient soundscape requests
        if self._ambient_player:

            # Voice speed control
            speed_commands = {
                "speak slower": -0.15, "talk slower": -0.15, "slow down": -0.15,
                "too fast": -0.15, "slower please": -0.15,
                "speak faster": 0.15, "talk faster": 0.15, "speed up": 0.15,
                "too slow": 0.15, "faster please": 0.15,
                "normal speed": 0, "regular speed": 0, "default speed": 0,
            }
            for phrase, delta in speed_commands.items():
                if phrase in lower:
                    if delta == 0:
                        self._voice_speed = 1.0
                    else:
                        self._voice_speed = max(0.6, min(1.5, self._voice_speed + delta))
                    speed_label = "slower" if self._voice_speed < 1.0 else "faster" if self._voice_speed > 1.0 else "normal"
                    logger.info("Voice speed: %.2f (%s)", self._voice_speed, speed_label)
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(
                                f"(The patient asked you to speak {speed_label}. "
                                f"Acknowledge it briefly: 'Sure, I'll {speed_label} it down/up a bit.' "
                                f"From now on, {'use shorter sentences and pause more.' if self._voice_speed < 1.0 else 'keep a brisk, energetic pace.' if self._voice_speed > 1.0 else 'speak at your normal pace.'})"
                            ), self._loop)
                    return

            # Volume control
            volume_commands = {
                "speak louder": 0.3, "talk louder": 0.3, "louder please": 0.3,
                "i can't hear you": 0.3, "can't hear": 0.3, "volume up": 0.3,
                "speak quieter": -0.2, "talk quieter": -0.2, "quieter please": -0.2,
                "too loud": -0.2, "volume down": -0.2, "not so loud": -0.2,
                "speak softer": -0.2, "softer please": -0.2,
                "normal volume": 0, "default volume": 0, "regular volume": 0,
            }
            for phrase, delta in volume_commands.items():
                if phrase in lower:
                    if delta == 0:
                        self._voice_volume = 1.0
                    else:
                        self._voice_volume = max(0.3, min(2.5, self._voice_volume + delta))
                    vol_label = "quieter" if self._voice_volume < 0.9 else "louder" if self._voice_volume > 1.1 else "normal"
                    logger.info("Voice volume: %.2f (%s)", self._voice_volume, vol_label)
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(
                                f"(The patient asked you to speak {vol_label}. "
                                f"Acknowledge briefly: 'How's this?' Keep it short.)"
                            ), self._loop)
                    return

            # Lullaby player
            if self._lullaby_player:
                if self._lullaby_player.is_playing and any(p in lower for p in [
                    "stop lullaby", "stop the lullaby", "stop singing",
                    "that's enough", "stop the music",
                ]):
                    msg = self._lullaby_player.stop()
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Lullaby stopped. Say: {msg})"), self._loop)
                    return

                if any(p in lower for p in [
                    "play a lullaby", "sing me a lullaby", "lullaby",
                    "sing me to sleep", "play something gentle",
                    "bedtime music", "sleep music",
                ]):
                    name = "twinkle"
                    if "brahms" in lower:
                        name = "brahms"
                    elif "rockabye" in lower or "rock a bye" in lower:
                        name = "rockabye"
                    elif "moonlight" in lower:
                        name = "moonlight"
                    msg = self._lullaby_player.play(name)
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(
                                f"(Lullaby started. Say softly: {msg} "
                                f"Then be very quiet and let the music play.)"
                            ), self._loop)
                    return

            if any(p in lower for p in ["stop ambient", "stop the sound", "stop the noise",
                                         "turn off the sound", "quiet please", "silence"]):
                if self._ambient_player.is_playing:
                    msg = self._ambient_player.stop()
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Ambient stopped. Say: {msg})"), self._loop)
                return

            ambient_triggers = {
                "play rain": "rain", "rain sounds": "rain", "rainy": "rain",
                "play ocean": "ocean", "ocean sounds": "ocean", "waves": "ocean",
                "play birds": "birds", "bird sounds": "birds", "birdsong": "birds",
                "play fireplace": "fireplace", "fire sounds": "fireplace", "crackling fire": "fireplace",
                "play wind": "wind", "wind sounds": "wind",
                "play creek": "creek", "stream sounds": "creek", "water sounds": "creek",
                "play night": "night", "night sounds": "night", "crickets": "night",
            }
            for phrase, ambient in ambient_triggers.items():
                if phrase in lower:
                    msg = self._ambient_player.play(ambient)
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Ambient sound started. Say: {msg})"), self._loop)
                    return

        # Direct movement requests
        body_commands = {
            # Antennas
            "wiggle your antennas": "wiggle",
            "move your antennas": "wiggle",
            "raise your antennas": "celebrate",
            "antennas up": "celebrate",
            "antennas down": "sad_droop",
            # Head
            "nod your head": "nod",
            "nod yes": "nod",
            "shake your head": "shake",
            "shake no": "shake",
            "tilt your head": "curious",
            "look around": "look around",
            "look at me": "listen",
            # Body
            "do a dance": "dance",
            "dance for me": "dance",
            "let's dance": "dance",
            "do a wiggle": "wiggle",
            "wiggle for me": "wiggle",
            "take a bow": "bow",
            "bow": "bow",
            "do a peek": "peek",
            "peekaboo": "peek",
            "peek a boo": "peek",
            "stretch": "stretch",
            "do a stretch": "stretch",
            # Emotions
            "show me happy": "celebrate",
            "show me sad": "empathy",
            "show me excited": "excited",
            "show me scared": "scared_startle",
            "show me surprised": "surprised",
            "show me proud": "proud",
            "show me worried": "worried",
            "be silly": "wiggle",
            # Games
            "simon says": None,  # handled separately
        }

        for phrase, action in body_commands.items():
            if phrase in lower:
                if action:
                    threading.Thread(
                        target=self._robot.perform, args=(action,), daemon=True
                    ).start()
                    logger.info("Body command: %s → %s", phrase, action)
                return

    # ── Hand tracker ──────────────────────────────────────────────

    def _handle_hand_tracking(self, text: str) -> None:
        """Handle hand tracking voice commands."""
        if not self._hand_tracker:
            return
        lower = text.lower()

        # Stop tracking
        if self._hand_tracker.is_tracking and any(p in lower for p in [
            "stop tracking", "stop following my hand", "tracking off",
            "stop hand tracking",
        ]):
            msg = self._hand_tracker.stop()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Hand tracking stopped. Say: {msg})"),
                    self._loop,
                )
            return

        # Change mode
        if any(p in lower for p in ["mirror mode", "mirror my hand"]):
            msg = self._hand_tracker.set_mode("mirror")
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Tracking mode changed. Say: {msg})"),
                    self._loop,
                )
            return
        if any(p in lower for p in ["wave back", "wave at me"]):
            msg = self._hand_tracker.set_mode("wave_back")
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Tracking mode changed. Say: {msg})"),
                    self._loop,
                )
            return

        # Start tracking
        if any(p in lower for p in [
            "follow my hand", "track my hand", "hand tracking",
            "follow my movement", "watch my hand", "be a pet",
        ]):
            msg = self._hand_tracker.start()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(
                        f"(You started hand tracking! Say: {msg} "
                        f"Tell the patient to move their hand and you'll follow it.)"
                    ), self._loop,
                )
            return

    # ── Translator ────────────────────────────────────────────────

    def _handle_translate(self, text: str) -> None:
        """Handle translation voice commands."""
        if not self._translator:
            return

        try:
            from integration.translator import detect_translate_request
            result = detect_translate_request(text)
            if not result:
                return
            phrase, target_lang = result
            if not phrase:
                return
        except Exception:
            return

        translation = self._translator.translate(phrase, target_lang or "")
        target = target_lang or self._translator._target_language
        if translation and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._inject_story_prompt(
                    f"(The patient asked you to translate '{phrase}' to {target.title()}. "
                    f"The translation is: {translation}. "
                    f"Say the translation clearly, then repeat it once more slowly so they can learn it.)"
                ), self._loop,
            )

    # ── Coding assistant ──────────────────────────────────────────

    def _handle_coding(self, text: str) -> None:
        """Handle coding assistant voice commands."""
        if not self._coding_assistant:
            return
        lower = text.lower()

        # Explain current code
        if any(p in lower for p in [
            "explain the code", "explain this code", "what does this code do",
            "walk me through", "explain it",
        ]):
            explanation = self._coding_assistant.explain_code()
            if explanation and self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(
                        f"(Explain this code to the patient in a friendly, beginner-friendly way: {explanation})"
                    ), self._loop,
                )
            return

        # Change language
        lang_triggers = ["use python", "use javascript", "use html", "use css",
                         "use sql", "use bash", "use typescript", "use java",
                         "use rust", "use go", "switch to python", "switch to javascript",
                         "code in python", "code in javascript"]
        for trigger in lang_triggers:
            if trigger in lower:
                lang = trigger.split()[-1]
                msg = self._coding_assistant.set_language(lang)
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(f"(Language changed. Say: {msg})"),
                        self._loop,
                    )
                return

        # Generate code — extract the description after the trigger
        code_triggers = [
            "write a function", "write a program", "write code",
            "help me code", "code a", "create a function",
            "make a function", "build a", "write me a",
            "generate code", "write some code",
        ]
        for trigger in code_triggers:
            if trigger in lower:
                idx = lower.find(trigger)
                prompt = text[idx + len(trigger):].strip().strip(".,!?")
                if not prompt:
                    prompt = text  # use the whole thing
                result = self._coding_assistant.generate_code(prompt)
                code = result.get("code", "")
                if code and self._loop:
                    # Summarize what was generated
                    lines = code.count("\n") + 1
                    lang = result.get("language", "python")
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(
                            f"(You just generated {lines} lines of {lang} code for the patient. "
                            f"It's now showing on the Code Pad dashboard page. "
                            f"Tell them what you wrote and offer to explain it. "
                            f"Brief summary of the code: {code[:200]})"
                        ), self._loop,
                    )
                return

    # ── Metronome ─────────────────────────────────────────────────

    def _handle_metronome(self, text: str) -> None:
        """Handle metronome voice commands."""
        if not self._metronome:
            return
        lower = text.lower()

        # Stop metronome
        if self._metronome.is_running and any(p in lower for p in [
            "stop metronome", "metronome off", "stop the metronome",
            "stop ticking", "stop the beat",
        ]):
            msg = self._metronome.stop()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Metronome stopped. Say: {msg})"),
                    self._loop,
                )
            return

        # Change tempo by name
        for tempo_name in ("largo", "adagio", "andante", "moderato", "allegro", "vivace", "presto"):
            if tempo_name in lower and any(p in lower for p in ["tempo", "speed", "set", "change"]):
                msg = self._metronome.set_tempo(tempo_name)
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(f"(Tempo changed. Say: {msg})"),
                        self._loop,
                    )
                return

        # Change BPM
        if "bpm" in lower:
            import re
            nums = re.findall(r"\d+", text)
            if nums:
                bpm = int(nums[0])
                msg = self._metronome.set_bpm(bpm)
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(f"(BPM changed. Say: {msg})"),
                        self._loop,
                    )
                return

        # Faster / slower
        if self._metronome.is_running:
            if any(p in lower for p in ["faster", "speed up", "quicker"]):
                msg = self._metronome.set_bpm(self._metronome._bpm + 10)
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(f"(Tempo increased. Say: {msg})"),
                        self._loop,
                    )
                return
            if any(p in lower for p in ["slower", "slow down"]):
                msg = self._metronome.set_bpm(self._metronome._bpm - 10)
                if self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(f"(Tempo decreased. Say: {msg})"),
                        self._loop,
                    )
                return

        # Start metronome
        if any(p in lower for p in [
            "start metronome", "metronome on", "start the metronome",
            "be a metronome", "tick for me", "keep time",
            "metronome please", "count the beat",
        ]):
            msg = self._metronome.start()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Metronome started. Say: {msg})"),
                    self._loop,
                )
            return

    # ── Custom personalities ──────────────────────────────────────

    def _handle_personality(self, text: str) -> None:
        """Handle personality switching voice commands."""
        if not self._personality_mgr:
            return
        lower = text.lower()

        # List personalities
        if any(p in lower for p in [
            "what personalities", "list personalities", "which personalities",
            "personality options", "who can you be",
        ]):
            profiles = self._personality_mgr.list_profiles()
            names = [f"{p['emoji']} {p['name']}" for p in profiles]
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(
                        f"(The patient wants to know your available personalities. "
                        f"List them: {', '.join(names)})"
                    ), self._loop,
                )
            return

        # Switch personality
        triggers = [
            "be the", "switch to", "change personality to", "become the",
            "act like", "talk like", "be a",
        ]
        for trigger in triggers:
            if trigger in lower:
                requested = lower.split(trigger, 1)[1].strip().strip(".,!?")
                # Match against profile names
                profiles_all = self._personality_mgr.list_profiles()
                matched = None
                for p in profiles_all:
                    if (requested in p["id"].lower() or
                        requested in p["name"].lower()):
                        matched = p["id"]
                        break
                if matched:
                    msg = self._personality_mgr.activate(matched)
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(
                                f"(Your personality just changed! {msg} "
                                f"Adopt this new personality immediately in how you speak and respond.)"
                            ), self._loop,
                        )
                else:
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(
                                f"(The patient asked you to be '{requested}' but that personality "
                                f"doesn't exist. Let them know and list available ones.)"
                            ), self._loop,
                        )
                return

        # Reset to default
        if any(p in lower for p in [
            "be yourself", "normal mode", "default personality", "be normal",
            "go back to normal", "reset personality",
        ]):
            msg = self._personality_mgr.activate("default")
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(
                        f"(You switched back to your default personality. {msg})"
                    ), self._loop,
                )
            return

    # ── Freestyle rapper ──────────────────────────────────────────

    def _handle_freestyle(self, text: str) -> None:
        """Handle freestyle rap voice commands."""
        if not self._freestyle_rapper:
            return
        lower = text.lower()

        # Stop rapping
        if self._freestyle_rapper.is_performing and any(p in lower for p in [
            "stop rapping", "stop the rap", "enough rapping", "mic drop",
            "stop freestyle", "that's enough",
        ]):
            msg = self._freestyle_rapper.stop()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(You stopped rapping. Say: {msg})"),
                    self._loop,
                )
            return

        # Change beat
        if any(p in lower for p in ["change the beat", "switch beat", "different beat"]):
            for beat in ("hype", "chill", "boom_bap"):
                if beat.replace("_", " ") in lower or beat in lower:
                    msg = self._freestyle_rapper.set_beat(beat)
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._inject_story_prompt(f"(Beat changed. Say: {msg})"),
                            self._loop,
                        )
                    return
            # Cycle to next beat
            beats = ["boom_bap", "chill", "hype"]
            cur = self._freestyle_rapper._current_beat
            idx = (beats.index(cur) + 1) % len(beats) if cur in beats else 0
            msg = self._freestyle_rapper.set_beat(beats[idx])
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_story_prompt(f"(Beat changed. Say: {msg})"),
                    self._loop,
                )
            return

        # Start freestyle — extract topic from trigger phrase
        triggers = [
            "freestyle about", "rap about", "spit a verse about",
            "drop a rap about", "freestyle", "spit some bars",
            "rap for me", "drop some bars", "bust a rhyme",
            "can you rap", "do a rap", "give me a rap",
        ]
        for trigger in triggers:
            if trigger in lower:
                # Extract topic after the trigger phrase
                idx = lower.find(trigger)
                topic = text[idx + len(trigger):].strip().strip(".,!?")
                if not topic:
                    topic = "being an awesome robot"
                if self._user_name:
                    self._freestyle_rapper.set_patient_name(self._user_name)
                rap = self._freestyle_rapper.perform(topic)
                if rap and self._loop:
                    asyncio.run_coroutine_threadsafe(
                        self._inject_story_prompt(
                            f"(You are now performing a freestyle rap! Deliver these bars with energy and rhythm: {rap})"
                        ), self._loop,
                    )
                return

    # ── Gratitude practice ────────────────────────────────────────

    def _handle_gratitude(self, text: str) -> None:
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

    def _start_gratitude(self) -> None:
        """Start a new gratitude session."""
        try:
            from activities.gratitude import GratitudeSession
            self._gratitude_session = GratitudeSession(self._patient_id)
            prompt = self._gratitude_session.start()
            if self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._inject_gratitude_prompt(prompt), self._loop
                )
            logger.info("Gratitude session started")
        except Exception as e:
            logger.error("Gratitude start error: %s", e)

    async def _inject_gratitude_prompt(self, prompt: str) -> None:
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
            logger.error("Gratitude inject error: %s", e)

    # ── Multi-session story arcs ──────────────────────────────────

    def _build_story_arc_context(self) -> str:
        """Build context about ongoing storylines from the knowledge graph
        and recent sessions so the LLM can reference them naturally."""
        try:
            import memory.db_supabase as _db
            import memory.knowledge_graph as kg

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
            logger.error("Story arc context error: %s", e)
            return ""

    # ── Topic tracking ────────────────────────────────────────────

    def _track_topic(self, text: str) -> None:
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

    def _try_learn_name(self, text: str) -> None:
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
                    logger.info("Learned name: %s", self._user_name)
                    if self._db_available:
                        try:
                            import memory.db_supabase as _db
                            _db.save_profile(self._patient_id, name=self._user_name)
                        except Exception:
                            pass

    def _extract_facts(self, text: str) -> None:
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
                        logger.info("Learned fact (%s): %s", category, snippet)
                        if self._db_available:
                            try:
                                import memory.db_supabase as _db
                                _db.save_fact(category, snippet, self._patient_id)
                            except Exception:
                                pass
                        if len(self._user_facts) > 20:
                            self._user_facts = self._user_facts[-20:]
                    break

    # ── Dashboard live chat ───────────────────────────────────────

    def _post_to_dashboard(self, speaker: str, text: str) -> None:
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

    def _check_caregiver_messages(self) -> None:
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

    def _post_mood_to_dashboard(self, mood: str) -> None:
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

    def _start_message_poller(self) -> None:
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
        logger.info("Caregiver message poller started (30s interval)")

    async def _inject_caregiver_messages(self) -> None:
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
                logger.info("Injected caregiver message: %s...", text[:60])
            except Exception as e:
                logger.error("Failed to inject caregiver message: %s", e)

    # ── Medication schedule checker ───────────────────────────────

    def _start_medication_checker(self) -> None:
        """Background thread that checks for due medication reminders every 60s."""
        def _check():
            while self._running:
                if self._db_available:
                    try:
                        import memory.db_supabase as _db
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
                        logger.error("Medication check error: %s", e)
                time.sleep(60)
        self._pending_med_prompt = None
        t = threading.Thread(target=_check, daemon=True)
        t.start()
        logger.info("Medication schedule checker started (60s interval)")

    async def _inject_medication_prompt(self) -> None:
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
            logger.info("Medication reminder injected")
        except Exception as e:
            logger.error("Medication inject error: %s", e)

    # ── Passive camera monitoring ─────────────────────────────────

    def _start_camera_monitor(self) -> None:
        """Background thread that periodically checks camera for falls, meals, smiles."""
        self._smile_count = 0

        def _monitor():
            while self._running:
                time.sleep(30)
                if not self._running:
                    break
                try:
                    import perception.camera_intelligence as ci

                    # Fall detection
                    fall = ci.detect_fall()
                    if fall and fall.strip().lower() == "yes":
                        logger.warning("FALL DETECTED via camera!")
                        if self._alerts:
                            self._alerts.alert("FALL_DETECTED", "Camera detected possible fall")
                        if self._loop:
                            asyncio.run_coroutine_threadsafe(
                                self._inject_story_prompt(
                                    "(URGENT: You see the patient may have fallen! "
                                    "Ask immediately: 'Are you okay? It looks like you "
                                    "might have fallen. Do you need help?' Be calm but urgent.)"
                                ), self._loop)

                    # Smile counting
                    if ci.count_smiles():
                        self._smile_count += 1

                    # Meal detection (every 5 minutes effectively — runs every 30s but we skip)
                    if self._nutrition and int(time.time()) % 300 < 30:
                        meal = ci.detect_meal()
                        if meal:
                            try:
                                import json as _json
                                data = _json.loads(meal)
                                if data.get("eating") and data.get("food"):
                                    self._nutrition.log_meal(data["food"])
                                    logger.info("Meal detected via camera: %s", data["food"])
                            except Exception:
                                pass

                except Exception as e:
                    logger.debug("Camera monitor error: %s", e)

        t = threading.Thread(target=_monitor, daemon=True)
        t.start()
        logger.info("Passive camera monitor started (30s interval)")

    # ── Emotion-adaptive music ────────────────────────────────────

    async def _offer_mood_music(self, direction: str) -> None:
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
            logger.info("Mood music offer injected (%s)", direction)
        except Exception as e:
            logger.error("Mood music offer error: %s", e)

    # ── Emotional repair injection ───────────────────────────────

    async def _inject_emotional_repair(self) -> None:
        """Inject a gentle recovery when Reachy may have caused a mood drop."""
        if not self._ws:
            return

        inject = (
            "(The patient's mood just dropped right after your last response. "
            "You may have said something that touched a nerve or brought up "
            "a difficult memory. Don't panic — just acknowledge it gently. "
            "Something like 'I hope I didn't say something that upset you' or "
            "'I noticed you got a bit quiet — I'm sorry if I said something wrong.' "
            "Then let them lead. Don't over-apologize or make it about you.)"
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
            logger.info("Emotional repair injected")
        except Exception as e:
            logger.warning("Emotional repair error: %s", e)

    # ── "Remember when" callbacks ─────────────────────────────────

    async def _inject_remember_when(self) -> None:
        """Pull an interesting past conversation and reference it naturally."""
        if not self._ws or not self._db_available:
            return

        memory = None
        try:
            import memory.db_supabase as _db
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
            logger.error("Remember-when query error: %s", e)

        # Fallback: try patient facts if no conversation found
        if not memory:
            try:
                import memory.db_supabase as _db
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
            logger.info("Remember-when injected: %s...", text[:60])
        except Exception as e:
            logger.error("Remember-when inject error: %s", e)

    # ── Main loop ─────────────────────────────────────────────────

    async def _run(self) -> None:
        import websockets

        self._loop = asyncio.get_running_loop()
        url = f"wss://api.openai.com/v1/realtime?model={self.model}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1",
        }

        instructions = self._build_full_instructions()

        logger.info("Connecting to %s...", self.model)
        async with websockets.connect(url, additional_headers=headers) as ws:
            self._ws = ws
            logger.info("Connected")

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
                        "threshold": 0.6,
                        "prefix_padding_ms": 200,
                        "silence_duration_ms": 500,
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

            # Start passive camera monitoring (fall detection, meal detection)
            self._start_camera_monitor()

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

            logger.info("Conversation started — just talk!")
            logger.info("Press Ctrl+C to quit.")

            try:
                await asyncio.gather(mic_task, recv_task)
            except asyncio.CancelledError:
                pass

    # ── Mic sender ────────────────────────────────────────────────

    async def _mic_sender(self, ws: object) -> None:
        # Use Reachy's built-in mic if robot is connected, otherwise sounddevice
        if self._robot and not self._robot._sim_mode and self._robot.mini:
            await self._mic_sender_reachy(ws)
        else:
            await self._mic_sender_sounddevice(ws)

    async def _mic_sender_reachy(self, ws: object) -> None:
        """Stream audio from Reachy Mini's built-in microphone."""
        from scipy.signal import resample as scipy_resample
        REACHY_RATE = 16000

        try:
            audio = self._robot.mini.media.audio
            audio.start_recording()
            logger.info("Mic streaming started (Reachy Mini built-in mic)")
        except Exception as e:
            logger.warning("Reachy mic failed, falling back to sounddevice: %s", e)
            await self._mic_sender_sounddevice(ws)
            return

        mic_q: asyncio.Queue = asyncio.Queue()
        send_counter = [0]

        def _reader_thread():
            """Background thread that reads from Reachy's mic and queues data."""
            while self._running:
                if self._mic_muted.is_set():
                    time.sleep(0.02)
                    continue
                try:
                    sample = audio.get_audio_sample()
                except Exception:
                    time.sleep(0.02)
                    continue
                if sample is None:
                    time.sleep(0.01)
                    continue

                # Convert stereo to mono
                if sample.ndim > 1:
                    mono = sample[:, 0].copy()
                else:
                    mono = sample.copy()

                # Resample 16kHz → 24kHz
                n_out = int(len(mono) * INPUT_RATE / REACHY_RATE)
                if n_out <= 0:
                    continue
                resampled = scipy_resample(mono, n_out)

                # Convert to int16 PCM
                pcm = (resampled * 32767).astype(np.int16)

                send_counter[0] += 1
                if send_counter[0] % 50 == 0:
                    rms = float(np.sqrt(np.mean(mono ** 2)))
                    logger.debug("REACHY MIC rms=%.4f samples=%d", rms, len(mono))

                # Doorbell detection (runs on raw mic audio)
                if self._doorbell_detector and len(mono) >= 512:
                    if self._doorbell_detector.analyze(mono):
                        if self._loop:
                            asyncio.run_coroutine_threadsafe(
                                self._inject_story_prompt(
                                    "(You just heard what sounds like a doorbell or a loud "
                                    "tonal sound. Tell the patient: 'I think I heard the "
                                    "doorbell! Are you expecting someone?' Be helpful but "
                                    "don't alarm them.)"
                                ), self._loop)

                # Ambient noise monitoring — auto-adjust volume
                if self._noise_monitor:
                    self._noise_monitor.feed(mono)
                    rec = self._noise_monitor.get_recommended_volume(self._voice_volume)
                    if rec is not None:
                        self._voice_volume = rec

                try:
                    self._loop.call_soon_threadsafe(mic_q.put_nowait, pcm.tobytes())
                except Exception:
                    pass

        reader = threading.Thread(target=_reader_thread, daemon=True)
        reader.start()

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
            try:
                audio.stop_recording()
            except Exception:
                pass

    async def _mic_sender_sounddevice(self, ws: object) -> None:
        """Stream audio from the computer's default microphone (fallback)."""
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
                    logger.debug("MIC MUTED rms=%.4f", rms)
                return

            log_counter[0] += 1
            if log_counter[0] % 50 == 0:
                logger.debug("MIC LIVE rms=%.4f", rms)

            # Doorbell detection
            if self._doorbell_detector and len(indata) >= 512:
                if self._doorbell_detector.analyze(indata[:, 0]):
                    if self._loop:
                        self._loop.call_soon_threadsafe(
                            lambda: asyncio.ensure_future(
                                self._inject_story_prompt(
                                    "(You just heard what sounds like a doorbell. "
                                    "Tell the patient: 'I think I heard the doorbell! "
                                    "Are you expecting someone?')"
                                )))

            # Ambient noise monitoring
            if self._noise_monitor:
                self._noise_monitor.feed(indata[:, 0])
                rec = self._noise_monitor.get_recommended_volume(self._voice_volume)
                if rec is not None:
                    self._voice_volume = rec

            try:
                self._loop.call_soon_threadsafe(mic_q.put_nowait, pcm.tobytes())
            except Exception:
                pass

        stream = sd.InputStream(
            samplerate=INPUT_RATE, channels=1, dtype="float32",
            callback=_mic_callback, blocksize=FRAME_SAMPLES,
        )
        stream.start()
        logger.info("Mic streaming started (computer sounddevice)")

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

    async def _receiver(self, ws: object) -> None:
        async for msg in ws:
            if not self._running:
                break
            event = json.loads(msg)
            etype = event.get("type", "")

            if etype != "response.audio.delta":
                logger.debug("WS %s", etype)

            if etype == "response.audio.delta":
                audio_bytes = base64.b64decode(event["delta"])
                self._playback_q.put(audio_bytes)
                if not self._reachy_speaking:
                    self._reachy_speaking = True
                    self._mic_muted.set()
                    if self._sound_direction:
                        self._sound_direction.disable()
                    logger.info("Reachy speaking → mic muted")

            elif etype == "response.audio.done":
                self._playback_q.put(None)
                self._reachy_speaking = False
                if self._sound_direction:
                    self._sound_direction.enable()
                logger.info("Reachy done → scheduling unmute")
                threading.Thread(target=self._delayed_unmute, daemon=True).start()
                # Check for caregiver messages after Reachy finishes speaking
                asyncio.ensure_future(self._inject_caregiver_messages())
                # Check for medication reminders
                asyncio.ensure_future(self._inject_medication_prompt())

            elif etype == "response.audio_transcript.done":
                text = event.get("transcript", "")
                if text:
                    logger.info("[REACHY] %s", text)
                    threading.Thread(
                        target=self._process_assistant_transcript,
                        args=(text,), daemon=True
                    ).start()
                    if self._on_transcript_done:
                        self._on_transcript_done(text)

            elif etype == "conversation.item.input_audio_transcription.completed":
                text = event.get("transcript", "")
                if text:
                    logger.info("[YOU] %s", text)
                    threading.Thread(
                        target=self._process_user_transcript,
                        args=(text,), daemon=True
                    ).start()
                    if self._on_user_transcript:
                        self._on_user_transcript(text)

            elif etype == "input_audio_buffer.speech_started":
                if self._mic_muted.is_set():
                    logger.debug("Speech during mute → ignoring (bleed)")
                elif time.time() - self._unmute_time < 0.5:
                    logger.debug("Speech right after unmute → ignoring")
                else:
                    logger.info("User speaking")

            elif etype == "input_audio_buffer.speech_stopped":
                if not self._mic_muted.is_set():
                    logger.info("User stopped → waiting for response")

            elif etype == "session.created":
                logger.info("Session created")
            elif etype == "session.updated":
                logger.info("Session configured")

            elif etype == "error":
                err = event.get("error", {})
                emsg = err.get("message", str(err))
                if "no active response" not in emsg.lower():
                    logger.error("Error: %s", emsg)

    # ── Delayed unmute ────────────────────────────────────────────

    def _delayed_unmute(self) -> None:
        # Shorter delays when using Reachy's hardware (less speaker bleed)
        if self._robot and not self._robot._sim_mode:
            time.sleep(0.15)
        else:
            time.sleep(0.6)
        asyncio.run_coroutine_threadsafe(
            self._clear_input_buffer(), self._loop
        ).result(timeout=2)
        time.sleep(0.05)
        silence = np.zeros(int(INPUT_RATE * 0.15), dtype=np.int16).tobytes()
        b64 = base64.b64encode(silence).decode()
        asyncio.run_coroutine_threadsafe(
            self._send_audio(b64), self._loop
        ).result(timeout=2)
        time.sleep(0.05)
        asyncio.run_coroutine_threadsafe(
            self._clear_input_buffer(), self._loop
        ).result(timeout=2)
        self._unmute_time = time.time()
        self._mic_muted.clear()
        logger.info("Mic unmuted — listening")
        if self._robot:
            try:
                self._robot.perform("listen")
            except Exception:
                pass

    # ── Playback worker ───────────────────────────────────────────

    def _playback_worker(self) -> None:
        # Use Reachy's built-in speaker if robot is connected, otherwise sounddevice
        if self._robot and not self._robot._sim_mode and self._robot.mini:
            self._playback_worker_reachy()
        else:
            self._playback_worker_sounddevice()

    def _playback_worker_reachy(self) -> None:
        """Play audio through Reachy Mini's built-in speaker."""
        from scipy.signal import resample as scipy_resample
        REACHY_RATE = 16000

        try:
            audio = self._robot.mini.media.audio
            audio.start_playing()
            logger.info("Playback started (Reachy Mini built-in speaker)")
        except Exception as e:
            logger.warning("Reachy speaker failed, falling back to sounddevice: %s", e)
            self._playback_worker_sounddevice()
            return

        try:
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
                float_mono = pcm.astype(np.float32) / 32767.0

                # Apply voice speed — resample to change playback rate
                # speed > 1.0 = fewer samples = faster, speed < 1.0 = more samples = slower
                target_rate = REACHY_RATE
                if self._voice_speed != 1.0:
                    # Adjust the effective output length
                    n_out = int(len(float_mono) * REACHY_RATE / SAMPLE_RATE / self._voice_speed)
                else:
                    n_out = int(len(float_mono) * REACHY_RATE / SAMPLE_RATE)

                if n_out > 0:
                    resampled = scipy_resample(float_mono, n_out)
                else:
                    continue

                stereo = np.column_stack([resampled, resampled]).astype(np.float32)

                # Apply volume
                if self._voice_volume != 1.0:
                    stereo = np.clip(stereo * self._voice_volume, -1.0, 1.0).astype(np.float32)

                try:
                    audio.push_audio_sample(stereo)
                except Exception:
                    pass
        finally:
            try:
                audio.stop_playing()
            except Exception:
                pass

    def _playback_worker_sounddevice(self) -> None:
        """Play audio through the computer's default speaker (fallback)."""
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

            # Apply voice speed
            if self._voice_speed != 1.0:
                from scipy.signal import resample as scipy_resample
                n_out = int(len(pcm) / self._voice_speed)
                if n_out > 0:
                    pcm = scipy_resample(pcm.astype(np.float32), n_out).astype(np.int16)

            # Apply volume
            if self._voice_volume != 1.0:
                pcm = np.clip(pcm.astype(np.float32) * self._voice_volume, -32767, 32767).astype(np.int16)

            try:
                stream.write(pcm.reshape(-1, 1))
            except Exception:
                pass
        stream.stop()
        stream.close()

    # ── Helpers ───────────────────────────────────────────────────

    def _clear_playback(self) -> None:
        self._stop_playback.set()
        while not self._playback_q.empty():
            try:
                self._playback_q.get_nowait()
            except queue.Empty:
                break
        self._stop_playback.clear()

    async def _send_audio(self, b64_audio) -> None:
        try:
            await self._ws.send(json.dumps({
                "type": "input_audio_buffer.append", "audio": b64_audio,
            }))
        except Exception:
            pass

    async def _send_cancel(self) -> None:
        try:
            await self._ws.send(json.dumps({"type": "response.cancel"}))
        except Exception:
            pass

    async def _clear_input_buffer(self) -> None:
        try:
            await self._ws.send(json.dumps({"type": "input_audio_buffer.clear"}))
        except Exception:
            pass
