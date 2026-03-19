"""Main interaction loop — ties everything together: speech, emotion,
brain, face detection, reminders, check-in, cognitive games,
reminiscence therapy, caregiver alerts, weather, camera, inactivity
monitoring, and medication confirmation."""

import random
import time
import os
import json
import urllib.request
import threading
from robot import Robot
from speech import SpeechEngine
from emotion import EmotionDetector
from config import RESPONSES


class InteractionLoop:
    def __init__(
        self,
        text_mode: bool = False,
        emotion_backend: str = "keywords",
        use_face: bool = False,
        brain_backend: str = None,
        language: str = "en",
        profile: str = "elderly",
    ):
        from profiles import get_profile, get_care_response
        self.profile = get_profile(profile)
        self.profile_name = profile
        self._get_care_response = get_care_response

        self.robot = Robot()
        self.speech = SpeechEngine(text_mode=text_mode, language=language,
                                   tts_rate=self.profile.get("tts_rate", 150))
        self.emotion = EmotionDetector(backend=emotion_backend)
        self.face_detector = None
        self.brain = None

        # Face emotion detection (webcam)
        if use_face:
            from face_emotion import FaceEmotionDetector
            self.face_detector = FaceEmotionDetector()

        # LLM brain for real conversation
        if brain_backend:
            from brain import Brain
            self.brain = Brain(backend=brain_backend,
                               profile_prompt=self.profile.get("system_prompt_addon", ""))

        # Subsystems
        from reminders import ReminderManager
        from checkin import DailyCheckIn
        from caregiver import CaregiverAlerts
        from reminiscence import ReminiscenceTherapy
        from cognitive import CognitiveExercises
        from music import MusicPlayer
        from exercises import GuidedExercises
        from stories import StoryReader
        from meditation import MeditationGuide

        self.reminders = ReminderManager(on_reminder=self._on_reminder)
        self.checkin = DailyCheckIn()
        self.caregiver = CaregiverAlerts()
        self.reminiscence = ReminiscenceTherapy()
        self.cognitive = CognitiveExercises(on_game_end=self._on_cognitive_game_end)
        self.music = MusicPlayer()
        self.exercises = GuidedExercises(on_exercise_done=self._on_exercise_done)
        self.stories = StoryReader()
        self.meditation = MeditationGuide()

        # Fall detection
        from fall_detection import FallDetector
        self.fall_detector = FallDetector(on_fall=self._on_fall_detected)

        # Vitals monitoring
        from vitals import VitalsMonitor
        self.vitals_monitor = VitalsMonitor(on_alert=self._on_vitals_alert, interval=60)

        # Autonomy engine (proactive behaviors)
        from autonomy import AutonomyEngine
        self.autonomy = AutonomyEngine(profile_config=self.profile.get("autonomy", {}))

        # Vector memory (Supabase pgvector)
        try:
            import vector_memory as vmem
            vmem.init()
        except Exception:
            pass

        # Knowledge graph
        try:
            import knowledge_graph as kg
            kg.init()
        except Exception:
            pass

        self._pending_reminder = None
        self._pending_fall_alert = False
        self._pending_vitals_alerts = []
        self._pending_cg_messages = []
        self._cg_lock = threading.Lock()
        self._dashboard_url = os.environ.get("DASHBOARD_URL", "http://localhost:5555")
        self._last_interaction = time.time()
        self._inactivity_threshold = 30 * 60  # 30 minutes
        self._inactivity_warned = False
        self._weather_city = os.environ.get("WEATHER_CITY", "auto")
        self._greeted_today = False

    # ── Reminder callback (called from background thread) ───────────

    def _on_reminder(self, message: str):
        self._pending_reminder = message

    # ── Fall detection callback (called from background thread) ────

    def _on_fall_detected(self, details: dict):
        """Called by FallDetector when a fall is detected."""
        self.caregiver.alert_fall_detected(details)
        self._log_activity("fall_detected",
                           f"confidence={details.get('confidence', 0):.0%}")
        self._pending_fall_alert = True

    # ── Vitals alert callback (called from background thread) ─────

    def _on_vitals_alert(self, alert_msg: str):
        """Called by VitalsMonitor when a reading exceeds thresholds."""
        self._pending_vitals_alerts.append(alert_msg)

    # ── Cognitive game score callback ─────────────────────────────

    def _on_cognitive_game_end(self, game_type: str, score: float, max_score: float):
        """Called when a cognitive game finishes — log to patient model + Supabase."""
        try:
            from patient_model import log_cognitive_score, init_model_db
            init_model_db()
            log_cognitive_score(game_type, score, max_score)
            self._log_activity("cognitive_score",
                               f"{game_type}: {score}/{max_score}")
        except Exception as e:
            print(f"[INFO] Could not log cognitive score: {e}")
        try:
            import db_supabase as _db
            if _db.is_available():
                _db.save_cognitive_score(game_type, score, max_score)
        except Exception:
            pass

    # ── Exercise completion callback ──────────────────────────────

    def _on_exercise_done(self, exercise_name: str, completed: bool):
        """Called when a guided exercise finishes — log to patient model + Supabase."""
        try:
            from patient_model import log_exercise, init_model_db
            init_model_db()
            log_exercise(exercise_name, completed=completed)
            self._log_activity("exercise_done",
                               f"{exercise_name} ({'completed' if completed else 'stopped early'})")
        except Exception as e:
            print(f"[INFO] Could not log exercise: {e}")
        try:
            import db_supabase as _db
            if _db.is_available():
                _db.save_exercise(exercise_name, completed=completed)
        except Exception:
            pass

    # ── Emotion combining ───────────────────────────────────────────

    def _combine_emotions(self, text_emotion: str, face_emotion: str) -> str:
        if face_emotion and face_emotion != "neutral":
            face_map = {
                "happy": "joy", "sad": "sadness", "angry": "anger",
                "fear": "fear", "surprise": "surprise",
                "disgust": "disgust", "neutral": "neutral",
            }
            mapped = face_map.get(face_emotion, face_emotion)
            print(f"[EMOTION] Combined: text={text_emotion}, face={mapped} -> using {mapped}")
            return mapped
        return text_emotion

    # ── Command detection ───────────────────────────────────────────

    def _check_command(self, text: str) -> str | None:
        """Only intercept commands that NEED to run actual code (music, exercises,
        safety alerts, sessions, etc.). Everything else goes to GPT for natural conversation."""
        lower = text.lower().strip()

        # ── Check-in (interactive multi-step session) ──────────────
        if any(w in lower for w in ["check-in", "check in", "checkin", "daily check"]):
            return self.checkin.start()

        # ── Care requests -> alert caregiver ───────────────────────
        medication_words = ["need my medication", "need my medicine", "need my pills",
                            "give me my medication", "give me my medicine", "give me my pills",
                            "where is my medication", "where are my pills", "time for my medicine",
                            "i need medication", "i need medicine", "i need my meds",
                            "bring me my pills", "bring my medication"]
        food_words = ["i'm hungry", "i am hungry", "need food", "need something to eat",
                      "i'm thirsty", "i am thirsty", "need water", "need a drink",
                      "can i eat", "want food", "want something to eat", "want water",
                      "want a drink", "bring me food", "bring me water", "need a snack",
                      "haven't eaten", "need to eat", "need lunch", "need dinner",
                      "need breakfast"]
        help_words = ["call my caregiver", "call the nurse", "i need help",
                      "get someone", "call someone", "need a nurse",
                      "need my caregiver", "call my family", "call my daughter",
                      "call my son", "need assistance"]

        for word in medication_words:
            if word in lower:
                self.caregiver.alert_medication_request(text)
                self._log_activity("medication_request", text)
                self.robot.express("neutral")
                return ("I've notified your caregiver that you need your medication. "
                        "They'll be with you soon. Is there anything else I can help with?")
        for word in food_words:
            if word in lower:
                self.caregiver.alert_food_request(text)
                self._log_activity("food_request", text)
                self.robot.express("neutral")
                return ("I've let your caregiver know. They'll bring you something soon. "
                        "In the meantime, would you like to chat or listen to some music?")
        for word in help_words:
            if word in lower:
                self.caregiver.alert_help_request(text)
                self._log_activity("help_request", text)
                self.robot.express("neutral")
                return ("I've sent a message to your caregiver right away. "
                        "They should be with you shortly. I'm right here with you.")

        # ── Profile-specific care detection (disabled) ─────────────
        care_resp = self._get_care_response(self.profile, "care", text)
        if care_resp:
            self.caregiver.alert_help_request(text)
            self._log_activity("care_request", text)
            self.robot.express("neutral")
            return care_resp

        # ── Medication confirmation ────────────────────────────────
        if any(w in lower for w in ["took my medication", "took my medicine", "took my pills",
                                     "took my meds", "i took it", "already took",
                                     "yes i took", "medication taken", "pills taken"]):
            return self._handle_med_confirmation(text)

        # ── Reminders (needs to write to reminder system) ──────────
        if any(w in lower for w in ["remind me", "add reminder", "set reminder"]):
            return self._handle_reminder_add(lower)
        if any(w in lower for w in ["my reminders", "list reminders", "what reminders", "show reminders"]):
            return self.reminders.list_reminders()

        # ── Reminiscence (interactive session) ─────────────────────
        if any(w in lower for w in ["memory lane", "reminisce", "tell me about the past",
                                     "old times", "good old days"]):
            theme = None
            for t in self.reminiscence.available_themes():
                if t.replace("_", " ") in lower:
                    theme = t
            return self.reminiscence.start(theme)

        # ── Cognitive games ────────────────────────────────────────
        if any(w in lower for w in ["play a game", "brain game", "let's play", "game time",
                                     "cognitive", "exercise my brain", "word game", "trivia"]):
            return self.cognitive.list_games()
        if any(w in lower for w in ["word association", "story builder", "categories",
                                     "memory game"]) and not self.cognitive.is_active:
            return self.cognitive.start_game(text)

        # ── Guided exercises ────────────────────────────────────────
        if any(w in lower for w in ["exercise", "exercises", "workout", "physical therapy",
                                     "let's exercise", "guided exercise", "morning routine",
                                     "afternoon routine", "evening routine"]):
            if self.exercises.is_active:
                text_resp, action = self.exercises.next_step()
                if action:
                    self.robot.perform(action)
                return text_resp
            text_resp, action = self.exercises.start_exercise(text)
            if action:
                self.robot.perform(action)
            self._log_activity("exercise_start", text)
            return text_resp
        if lower in ["next", "continue", "go on", "keep going"] and self.exercises.is_active:
            text_resp, action = self.exercises.next_step()
            if action:
                self.robot.perform(action)
            return text_resp

        # ── Stories / audiobook ────────────────────────────────────
        if any(w in lower for w in ["read me a story", "tell me a story", "story time",
                                     "read a story", "audiobook", "bedtime story",
                                     "fable", "fairy tale"]):
            if self.stories.is_active:
                return self.stories.next_page()
            self._log_activity("story_start", text)
            return self.stories.start_story(text)
        if any(w in lower for w in ["list stories", "what stories", "which stories"]):
            return self.stories.list_stories()
        if lower in ["next", "continue", "go on", "keep going"] and self.stories.is_active:
            return self.stories.next_page()

        # ── Sleep tracking (needs to log actual times) ──────────────
        if any(w in lower for w in ["going to bed", "going to sleep",
                                     "goodnight", "good night", "time to sleep"]):
            from sleep_tracker import log_bedtime
            self.robot.perform("sleepy")
            self._log_activity("bedtime", "Patient going to sleep")
            return log_bedtime()
        if any(w in lower for w in ["just woke up", "i'm awake", "i am awake",
                                     "woke up"]) and "good morning" not in lower:
            from sleep_tracker import log_wake_time
            self._log_activity("wake_up", "Patient woke up")
            return log_wake_time()
        if any(w in lower for w in ["sleep report", "how did i sleep", "sleep quality",
                                     "sleep tracking", "my sleep"]):
            from sleep_tracker import sleep_report
            return sleep_report()

        # ── Calendar (needs to write to tracker) ──────────────────
        if any(w in lower for w in ["add appointment", "schedule appointment",
                                     "i have an appointment"]):
            from calendar_tracker import parse_appointment
            return parse_appointment(text)
        if any(w in lower for w in ["my appointments", "list appointments",
                                     "upcoming appointments"]):
            from calendar_tracker import list_appointments
            return list_appointments()

        # ── Water reminder (needs to schedule via dashboard) ───────
        if "water reminder" in lower or "hydration reminder" in lower:
            self._post_dashboard("/api/scheduled", {
                "text": "Time to drink some water! Stay hydrated!",
                "time": "09:00", "repeat": "daily",
            })
            self._log_activity("hydration_reminder", "Set up water reminders")
            return "I've set up a daily water reminder for you!"

        # ── News (fetches real data) ───────────────────────────────
        if any(w in lower for w in ["news", "headlines", "what's happening",
                                     "read me the news", "today's news"]):
            from news import news_briefing
            self._log_activity("news", "Patient asked for news")
            return news_briefing()

        # ── Meditation / mindfulness ───────────────────────────────
        if any(w in lower for w in ["meditate", "meditation", "mindfulness",
                                     "body scan", "peaceful place", "loving kindness",
                                     "guided meditation", "mindful"]):
            if self.meditation.is_active:
                return self.meditation.next_step()
            self.robot.perform("breathe")
            self._log_activity("meditation_start", text)
            return self.meditation.start(text)
        if any(w in lower for w in ["list meditations", "what meditations",
                                     "meditation options"]):
            return self.meditation.list_sessions()
        if lower in ["next", "continue", "go on", "keep going"] and self.meditation.is_active:
            return self.meditation.next_step()

        # ── Voice journal (interactive session) ────────────────────
        if any(w in lower for w in ["start journal", "journal entry", "write in my journal",
                                     "dear diary", "i want to journal", "voice journal"]):
            from journal import start_journal
            self._log_activity("journal_start", "Patient started journaling")
            return start_journal()
        if any(w in lower for w in ["save journal", "done journaling", "finish journal"]):
            from journal import save_journal
            return save_journal()
        if any(w in lower for w in ["cancel journal", "discard journal", "nevermind journal"]):
            from journal import cancel_journal
            return cancel_journal()

        # ── Music (needs to play actual audio files) ───────────────
        if any(w in lower for w in ["play music", "play a song", "play something",
                                     "play me", "put on", "i want to hear",
                                     "can you play", "lullaby"]):
            if any(w in lower for w in ["what songs", "how many songs", "song library",
                                         "list songs", "what music do you have"]):
                count = self.music.get_song_count()
                melodies = ", ".join(self.music.list_melodies())
                if count > 0:
                    return f"I have {count} songs in my library plus these melodies: {melodies}. Ask me to play a song by name, or by mood like 'play something calm'."
                return f"I don't have any songs in my library yet, but I can play these melodies: {melodies}. You can add MP3 or WAV files to the songs folder!"
            resp, played = self.music.get_song_for_request(text)
            if resp:
                self._log_activity("music_play", text[:80])
                return resp
            return self._handle_music(lower)
        if any(w in lower for w in ["stop music", "stop playing", "stop the music",
                                     "turn off music", "music off"]):
            self.music.stop()
            return "Okay, music stopped."

        # ── Smart home (needs to send actual commands) ─────────────
        from smart_home import parse_smart_home_command
        sh_response, sh_handled = parse_smart_home_command(text)
        if sh_handled:
            self._log_activity("smart_home", text[:80])
            return sh_response

        # ── Vitals (needs to read from device) ────────────────────
        if any(w in lower for w in ["my vitals", "check my vitals", "heart rate",
                                     "blood pressure", "oxygen level",
                                     "how's my health", "health check", "pulse"]):
            from vitals import get_vitals_summary
            self._log_activity("vitals_check", "Patient asked for vitals")
            return get_vitals_summary()

        # ── Stop / quit active sessions ────────────────────────────
        if any(w in lower for w in ["stop", "quit", "enough", "done", "exit", "no more"]):
            if self.cognitive.is_active:
                return self.cognitive.stop_game()
            if self.reminiscence.is_active:
                self.reminiscence.active = False
                return "Of course. Thanks for sharing those memories with me. We can do it again anytime."
            if self.checkin.is_active:
                self.checkin.active = False
                return "No problem, we can finish the check-in another time."
            if self.exercises.is_active:
                return self.exercises.stop()
            if self.stories.is_active:
                return self.stories.stop()
            if self.meditation.is_active:
                return self.meditation.stop()

        # ── Help ───────────────────────────────────────────────────
        if lower in ["help", "what can you do", "commands", "menu"]:
            return (
                "Here's what I can do:\n"
                "- Just chat with me about anything\n"
                "- 'check-in' — daily wellness check\n"
                "- 'remind me' — set reminders\n"
                "- 'play a game' — brain games\n"
                "- 'exercise' — guided exercises\n"
                "- 'meditate' — guided meditation\n"
                "- 'read me a story' — story time\n"
                "- 'play music' — melodies and songs\n"
                "- 'journal' — voice journaling\n"
                "- 'my appointments' — calendar\n"
                "- 'check my vitals' — health readings\n"
                "- 'news' — today's headlines\n"
                "- 'stop' — end any active session\n"
                "- Or just talk to me about anything!"
            )

        # Everything else → GPT handles it naturally
        return None

    # ── Feature handlers ────────────────────────────────────────────

    def _handle_weather(self, text: str = "") -> str:
        """Fetch and speak weather. Parse city from user's speech if mentioned."""
        import re
        city = self._weather_city

        # Try to extract city from what the user said
        # Patterns: "weather in Kansas City", "weather for New York", "how's the weather in London"
        match = re.search(r'(?:weather|temperature|forecast)\s+(?:in|for|at)\s+(.+)', text.lower())
        if match:
            city = match.group(1).strip().rstrip("?.!")
            # Capitalize words for the API
            city = city.title().replace(" ", "+")

        self._log_activity("weather_check", f"Weather for {city}")
        from weather import weather_briefing
        return weather_briefing(city)

    def _enrich_with_live_data(self, text: str) -> str:
        """Inject real-time data GPT can't know on its own (time, date, weather)
        so it can respond naturally without hardcoded command handlers."""
        from datetime import datetime
        now = datetime.now()
        time_str = now.strftime("%I:%M %p").lstrip("0")
        date_str = now.strftime("%A, %B %d, %Y")
        enriched = text

        # Always include current time/date so GPT can answer naturally
        enriched += f"\n[CONTEXT: Current time is {time_str}, {date_str}.]"

        # If they mention weather, fetch it and inject
        lower = text.lower()
        if any(w in lower for w in ["weather", "temperature", "forecast",
                                     "is it cold", "is it hot", "is it raining"]):
            weather_data = self._handle_weather(text)
            enriched += f"\n[LIVE DATA: {weather_data}]"

        return enriched

    def _handle_med_confirmation(self, text: str) -> str:
        """Patient confirms they took medication."""
        self._log_activity("med_confirmed", text)
        self._post_dashboard("/api/activity", {
            "action": "med_confirmed",
            "details": f"Patient confirmed: {text}",
        })
        try:
            from patient_model import log_med_adherence, init_model_db
            init_model_db()
            log_med_adherence("unknown", "taken")
        except Exception as e:
            print(f"[INFO] Could not log med adherence: {e}")
        self.robot.express("joy")
        return "Great job taking your medication! I'll let your caregiver know. Keep it up!"

    def _handle_reminder_add(self, text: str) -> str:
        """Parse a simple reminder request."""
        import re
        time_pattern = r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))'
        times_found = re.findall(time_pattern, text, re.IGNORECASE)

        parsed_times = []
        for t in times_found:
            try:
                t_clean = t.strip().upper()
                if ":" not in t_clean:
                    t_clean = t_clean.replace("AM", ":00 AM").replace("PM", ":00 PM")
                from datetime import datetime
                dt = datetime.strptime(t_clean.strip(), "%I:%M %p")
                parsed_times.append(dt.strftime("%H:%M"))
            except ValueError:
                pass

        words = text.split()
        med_name = None
        for trigger in ["take", "medication", "medicine", "med", "pill"]:
            if trigger in words:
                idx = words.index(trigger)
                if idx + 1 < len(words):
                    med_name = words[idx + 1].strip(".,!?")
                    break

        if med_name and parsed_times:
            return self.reminders.add_medication(med_name, parsed_times)
        elif med_name:
            return self.reminders.add_medication(med_name, ["08:00"])
        else:
            return (
                "I'd love to help set a reminder! Could you tell me:\n"
                "- What medication? (e.g., 'aspirin')\n"
                "- What time? (e.g., '8am and 8pm')\n"
                "For example: 'remind me to take aspirin at 8am and 8pm'"
            )

    def _handle_appointment_add(self, text: str) -> str:
        return (
            "I can track appointments for you! Tell me something like:\n"
            "'I have a doctor appointment on March 20 at 2pm'\n"
            "For now, I'll note that you mentioned an appointment. "
            "Could you give me the details?"
        )

    def _breathing_exercise(self) -> str:
        return (
            "Let's do a breathing exercise together. Follow along with me:\n\n"
            "Breathe in slowly through your nose... 1... 2... 3... 4...\n"
            "Hold it gently... 1... 2... 3... 4...\n"
            "Now breathe out slowly through your mouth... 1... 2... 3... 4...\n\n"
            "Let's do that two more times. In... hold... and out.\n"
            "One more time. In... hold... and out.\n\n"
            "How do you feel? A little calmer, I hope."
        )

    def _handle_music(self, text: str) -> str:
        """Handle music requests."""
        melody_map = {
            "calm": ["calm", "peaceful", "relaxing", "soothing"],
            "happy": ["happy", "cheerful", "upbeat", "fun"],
            "lullaby": ["lullaby", "sleep", "bedtime", "goodnight"],
            "morning": ["morning", "wake up", "sunrise"],
            "celebration": ["celebration", "celebrate", "party", "hooray"],
            "thinking": ["thinking", "think", "contemplat"],
            "gentle": ["gentle", "soft", "quiet", "background"],
            "waltz": ["waltz", "dance music", "elegant"],
            "nostalgic": ["nostalgic", "old times", "memories", "remember"],
            "playful": ["playful", "silly", "funny", "goofy"],
            "rain": ["rain", "rainy", "storm", "water"],
            "sunset": ["sunset", "evening", "dusk", "twilight"],
        }
        for melody, triggers in melody_map.items():
            if any(t in text for t in triggers):
                self.music.play_melody(melody)
                responses = {
                    "calm": "Here's something peaceful for you.",
                    "happy": "Here's a cheerful little tune!",
                    "lullaby": "A gentle lullaby for you...",
                    "morning": "Rise and shine! Here's a bright melody.",
                    "celebration": "Let's celebrate!",
                    "thinking": "Some thinking music...",
                    "gentle": "Something soft and gentle.",
                    "waltz": "A lovely little waltz for you.",
                    "nostalgic": "This one might bring back some memories.",
                    "playful": "Here's something fun and playful!",
                    "rain": "Like a gentle rain falling...",
                    "sunset": "A peaceful sunset melody.",
                }
                return responses.get(melody, "Here you go!")

        self.music.play_melody("gentle")
        melodies = ", ".join(self.music.list_melodies())
        return f"Here's a gentle melody. I can also play: {melodies}. Just ask!"

    # ── Inactivity monitoring ──────────────────────────────────────

    def _check_inactivity(self):
        """Check if patient has been inactive too long and initiate contact."""
        elapsed = time.time() - self._last_interaction
        if elapsed > self._inactivity_threshold and not self._inactivity_warned:
            self._inactivity_warned = True
            self._log_activity("inactivity_check", f"No interaction for {int(elapsed/60)} minutes")
            self.robot.express("neutral")
            # Use companion conversation starters for more engaging check-ins
            from companion import get_conversation_starter
            from affirmations import get_daily_affirmation
            options = [
                f"Hey there! I haven't heard from you in a while. {get_conversation_starter()}",
                f"Just checking in! Here's something for you: {get_daily_affirmation()}",
                f"Hi! It's been quiet. {get_conversation_starter()}",
                "Hello! I'm still here if you need anything. How are you feeling?",
            ]
            msg = random.choice(options)
            self.speech.speak(msg)
            self._log_to_dashboard("reachy", msg)

    def _get_silence_hint(self) -> str:
        """Determine how long to wait for silence based on conversation context.
        Returns 'question' if Reachy just asked something (wait longer),
        'quick' if it's a fast exchange, or 'default'."""
        # Check what Reachy last said
        last_response = ""
        if self.brain and hasattr(self.brain, '_last_response'):
            last_response = self.brain._last_response

        if not last_response:
            return "default"

        # If Reachy asked a question, give the patient more time to think
        stripped = last_response.rstrip()
        if stripped.endswith("?"):
            return "question"

        # If the last response was short (< 15 words), it's a quick exchange
        if len(last_response.split()) < 15:
            return "quick"

        return "default"

    def _reset_inactivity(self):
        """Reset the inactivity timer."""
        self._last_interaction = time.time()
        self._inactivity_warned = False

    # ── Dashboard helpers ──────────────────────────────────────────

    def _post_dashboard(self, endpoint: str, data: dict):
        """POST JSON to the caregiver dashboard (fire and forget)."""
        import threading
        def _send():
            try:
                payload = json.dumps(data).encode("utf-8")
                req = urllib.request.Request(
                    f"{self._dashboard_url}{endpoint}",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=3)
            except Exception:
                pass
        threading.Thread(target=_send, daemon=True).start()

    def _log_to_dashboard(self, speaker: str, text: str):
        """Log a conversation entry to the dashboard."""
        self._post_dashboard("/api/conversation", {"speaker": speaker, "text": text})

    def _log_activity(self, action: str, details: str = ""):
        """Log an activity event to the dashboard."""
        self._post_dashboard("/api/activity", {"action": action, "details": details})

    def _update_dashboard_status(self, **kwargs):
        """Update patient status on the dashboard."""
        self._post_dashboard("/api/status", kwargs)

    def _check_caregiver_messages(self):
        """Poll the dashboard for messages from the caregiver."""
        try:
            req = urllib.request.Request(
                f"{self._dashboard_url}/api/messages/pending",
                method="GET",
            )
            resp = urllib.request.urlopen(req, timeout=2)
            messages = json.loads(resp.read().decode("utf-8"))
            return messages
        except Exception:
            return []

    def _start_message_poller(self):
        """Background thread that polls for caregiver messages every 3s."""
        def _poll():
            while True:
                try:
                    msgs = self._check_caregiver_messages()
                    if msgs:
                        with self._cg_lock:
                            self._pending_cg_messages.extend(msgs)
                except Exception:
                    pass
                time.sleep(3)
        t = threading.Thread(target=_poll, daemon=True)
        t.start()

    # ── Medication check from dashboard ────────────────────────────

    def _check_medication_reminders(self):
        """Check if any medications are due and remind the patient."""
        try:
            req = urllib.request.Request(
                f"{self._dashboard_url}/api/medications",
                method="GET",
            )
            resp = urllib.request.urlopen(req, timeout=2)
            meds = json.loads(resp.read().decode("utf-8"))
            from datetime import datetime
            now = datetime.now().strftime("%H:%M")
            for med in meds:
                if not med.get("active"):
                    continue
                times = [t.strip() for t in med.get("times", "").split(",")]
                for t in times:
                    if t == now:
                        msg = f"It's time to take your {med['name']} {med.get('dosage', '')}. Have you taken it?"
                        self.robot.express("neutral")
                        self.speech.speak(msg)
                        self._log_to_dashboard("reachy", msg)
                        self._log_activity("med_reminder", f"Reminded: {med['name']} at {t}")
                        try:
                            from patient_model import log_med_adherence, init_model_db
                            init_model_db()
                            log_med_adherence(med['name'], "reminded", scheduled_time=t)
                        except Exception:
                            pass
        except Exception:
            pass

    # ── Main loop ───────────────────────────────────────────────────

    def start(self):
        """Run the main interaction loop."""
        self.robot.connect()
        self.reminders.start()

        # Start camera stream server + frame capture
        try:
            if self.robot.start_camera_stream(port=5556):
                self._camera_server = True
            else:
                # Fallback: start server only (no frames until robot connects)
                from camera_stream import start_stream_server
                self._camera_server = start_stream_server(port=5556)
        except Exception as e:
            print(f"[INFO] Camera stream not available: {e}")
            self._camera_server = None

        # Start face detection background thread if enabled
        if self.face_detector:
            if self.face_detector.start_continuous():
                print("[INFO] Face emotion detection running in background")
            else:
                print("[INFO] Face detection unavailable, using text only")
                self.face_detector = None

        # Start robot teleoperation API
        try:
            from webapp import start_server as start_robot_api
            start_robot_api(robot=self.robot, port=5557)
        except Exception as e:
            print(f"[INFO] Robot API not available: {e}")

        # Start fall detection using camera frames
        if self.fall_detector.available and self._camera_server:
            from camera_stream import get_latest_frame
            self.fall_detector.start_monitoring(frame_source=get_latest_frame)
            mode_info_fall = True
        else:
            mode_info_fall = False
            if not self.fall_detector.available:
                print("[INFO] Fall detection unavailable (install mediapipe)")
            elif not self._camera_server:
                print("[INFO] Fall detection needs camera — skipped")

        mode_info = []
        if self.brain:
            mode_info.append("LLM brain")
        if self.face_detector:
            mode_info.append("face detection")
        if self._camera_server:
            mode_info.append("camera stream")
        if mode_info_fall:
            mode_info.append("fall detection")

        # Start vitals monitoring background thread
        self.vitals_monitor.start()
        mode_info.append("vitals monitor")

        mode_str = " + ".join(mode_info) if mode_info else "basic mode"

        print(f"\n=== Reachy Accessibility Assistant ({mode_str}) ===")
        print(f"Profile: {self.profile['name']} ({self.profile_name})")
        print("Say 'help' to see what I can do. Press Ctrl+C to quit.\n")

        self._log_activity("session_start", "Reachy assistant started")
        self._last_med_check_minute = ""

        # Start autonomy engine
        self.autonomy.start()

        # Start background message poller
        self._start_message_poller()

        # Restore conversation history from Supabase (cross-session memory)
        if self.brain:
            try:
                self.brain.restore_history()
            except Exception as e:
                print(f"[INFO] Could not restore history: {e}")

        # Startup greeting — personalized via GPT if brain is available
        self.robot.perform("greet")
        if self.brain and self.brain.client:
            try:
                greeting_ctx = self.brain._build_greeting_context()
                resp = self.brain.client.chat.completions.create(
                    model=self.brain.model,
                    messages=[
                        {"role": "system", "content": self.brain.history[0]["content"]},
                        {"role": "system", "content": greeting_ctx},
                        {"role": "user", "content": "(Session just started. Greet me.)"},
                    ],
                    max_tokens=100,
                    temperature=0.9,
                )
                greeting = resp.choices[0].message.content.strip()
                # Store in brain history so GPT knows what it said
                self.brain.history.append({"role": "assistant", "content": greeting})
                self.brain.session_start = False
                print(f"[BRAIN] Personalized greeting: {greeting}")
            except Exception as e:
                print(f"[INFO] GPT greeting failed, using fallback: {e}")
                greeting = random.choice([
                    "Hello! I'm Reachy, your companion. I'm here to help you throughout the day.",
                    "Hi there! Reachy here, ready to keep you company. Just talk to me anytime!",
                    "Good to see you! I'm Reachy, your assistant. Let me know if you need anything!",
                ])
        else:
            greeting = random.choice([
                "Hello! I'm Reachy, your companion. I'm here to help you throughout the day. Say 'help' to see what I can do!",
                "Hi there! Reachy here, ready to keep you company. Just talk to me anytime!",
                "Good to see you! I'm Reachy, your assistant. Let me know if you need anything!",
            ])
        self.speech.speak(greeting)
        self._log_to_dashboard("reachy", greeting)
        self._log_activity("greeting", "Startup greeting")

        try:
            # Background tracking function — runs after every response
            def _bg_track(txt, resp, emotion, has_brain):
                try:
                    from followups import log_mood, log_conversation, log_conversation_date, remember_mention, track_topic, smart_extract_mentions
                    log_mood(emotion)
                    log_conversation(txt)
                    log_conversation_date()
                    remember_mention(txt)
                    track_topic(txt)
                    if has_brain:
                        smart_extract_mentions(txt)
                except Exception as e:
                    print(f"[INFO] Followups tracking error: {e}")
                try:
                    import vector_memory as vmem
                    if vmem.is_available():
                        from followups import get_topic
                        t = get_topic(txt)
                        vmem.store_turn(txt, speaker="patient", emotion=emotion, topic=t)
                        vmem.store_bot_response(resp, emotion=emotion, topic=t)
                except Exception as e:
                    print(f"[INFO] Vector memory store error: {e}")
                try:
                    import knowledge_graph as kg
                    if kg.is_available() and has_brain:
                        kg.extract_and_store(txt)
                except Exception as e:
                    print(f"[INFO] Knowledge graph error: {e}")
                if has_brain:
                    try:
                        import temporal_patterns as tp
                        findings = tp.analyze()
                        for f in findings:
                            if f["severity"] == "warning":
                                self.caregiver.alert("PATTERN_DETECTED", f["description"])
                    except Exception:
                        pass

            while True:
                # Check for pending reminders
                if self._pending_reminder:
                    msg = self._pending_reminder
                    self._pending_reminder = None
                    self.robot.express("surprise")
                    self.speech.speak(msg)
                    self._log_to_dashboard("reachy", msg)
                    time.sleep(0.5)
                    self.robot.reset()

                # Handle fall detection alert
                if self._pending_fall_alert:
                    self._pending_fall_alert = False
                    self.robot.express("fear")
                    fall_msg = ("I detected a possible fall! Are you okay? "
                                "I've already notified your caregiver. "
                                "If you need immediate help, say 'I need help'.")
                    self.speech.speak(fall_msg)
                    self._log_to_dashboard("reachy", fall_msg)
                    time.sleep(0.5)
                    self.robot.reset()

                # Handle vitals alerts
                if self._pending_vitals_alerts:
                    alerts = self._pending_vitals_alerts[:]
                    self._pending_vitals_alerts.clear()
                    combined = "; ".join(alerts)
                    self.caregiver.alert(
                        "VITALS_ALERT",
                        f"Abnormal vitals detected: {combined}",
                    )
                    self.robot.express("neutral")
                    vitals_msg = (f"I noticed something in your vitals: {combined}. "
                                  "I've let your caregiver know.")
                    self.speech.speak(vitals_msg)
                    self._log_to_dashboard("reachy", vitals_msg)
                    self._log_activity("vitals_alert", combined[:80])
                    time.sleep(0.5)
                    self.robot.reset()

                # Check for caregiver messages (from background poller)
                with self._cg_lock:
                    cg_messages = self._pending_cg_messages[:]
                    self._pending_cg_messages.clear()
                for cg_msg in cg_messages:
                    text = cg_msg.get("text", "")
                    if text:
                        self.robot.express("joy")
                        prefix = "Message from your caregiver: "
                        self.speech.speak(prefix + text)
                        self._log_to_dashboard("reachy", prefix + text)
                        self.robot.reset()

                # Check medication schedule (once per minute)
                from datetime import datetime
                current_minute = datetime.now().strftime("%H:%M")
                if current_minute != self._last_med_check_minute:
                    self._last_med_check_minute = current_minute
                    self._check_medication_reminders()

                # Process proactive actions from autonomy engine
                proactive = self.autonomy.get_next_action()
                if proactive:
                    if proactive.action_type == "idle_anim":
                        # Silent animation — no speech
                        if proactive.robot_action:
                            self.robot.perform(proactive.robot_action)
                    elif proactive.message:
                        # Don't interrupt if patient spoke recently (within 60s)
                        since_last = time.time() - self._last_interaction
                        if since_last < 60:
                            pass  # skip — patient is actively talking
                        else:
                            if proactive.robot_action:
                                self.robot.perform(proactive.robot_action)
                            self.speech.speak(proactive.message)
                            self._log_to_dashboard("reachy", proactive.message)
                            self._log_activity("proactive_" + proactive.action_type, proactive.message[:80])
                            time.sleep(0.5)
                            self.robot.reset()

                # Check inactivity
                self._check_inactivity()

                self.robot.perform("listen")

                # Set adaptive silence hint based on what Reachy just said
                self.speech._silence_hint = self._get_silence_hint()

                # 1. Listen — if patient just interrupted, continue capturing
                #    their speech seamlessly (no beep, no re-listen)
                if self.speech.interrupted:
                    text = self.speech.listen_after_interrupt()
                else:
                    text = self.speech.listen()
                if not text:
                    continue

                # Reset inactivity timer on any speech
                self._reset_inactivity()
                self.autonomy.notify_interaction()

                # Log what patient said
                self._log_to_dashboard("patient", text)
                self._log_activity("patient_spoke", text[:80])

                # 2. If a session is active, route to it
                response = self._route_active_session(text)
                if response:
                    emotion = self.emotion.detect(text)
                    self.robot.express(emotion)
                    self.speech.speak(response)
                    self._log_to_dashboard("reachy", response)
                    self._update_dashboard_status(mood=emotion)
                    self.robot.reset()
                    continue

                # 3. Detect emotion for robot expression + GPT context
                text_emotion = self.emotion.detect(text)
                face_emotion = ""
                if self.face_detector:
                    face_emotion = self.face_detector.current_emotion
                display_emotion = self._combine_emotions(text_emotion, face_emotion)
                self.robot.express(display_emotion)
                self._update_dashboard_status(mood=display_emotion)
                self.autonomy.notify_mood(display_emotion)

                # Safety check for caregiver alerts (runs in parallel, doesn't block)
                lower = text.lower()
                self._check_safety_alerts(lower, text, display_emotion)

                # 4. Check for commands that NEED code execution
                #    (music playback, interactive sessions, smart home, etc.)
                cmd_response = self._check_command(text)
                if cmd_response:
                    self.speech.speak(cmd_response)
                    self._log_to_dashboard("reachy", cmd_response)
                    self.robot.reset()
                    # Still track in background
                    threading.Thread(
                        target=_bg_track,
                        args=(text, cmd_response, display_emotion, bool(self.brain)),
                        daemon=True,
                    ).start()
                    continue

                # 5. GPT handles everything else — this is the default path
                if self.brain:
                    # Enrich with live data GPT can't know on its own
                    enriched = self._enrich_with_live_data(text)
                    # Stream: GPT generates → TTS plays sentence by sentence
                    sentence_gen = self.brain.think_stream(enriched, text_emotion)
                    response = self.speech.speak_streamed(sentence_gen)
                else:
                    options = RESPONSES.get(text_emotion, RESPONSES["neutral"])
                    response = random.choice(options)
                    self.speech.speak(response)

                self._log_to_dashboard("reachy", response)
                self.robot.reset()

                # Track in background so it doesn't block the next listen
                threading.Thread(
                    target=_bg_track,
                    args=(text, response, display_emotion, bool(self.brain)),
                    daemon=True,
                ).start()

        except KeyboardInterrupt:
            print("\n[INFO] Shutting down...")
        finally:
            # Save session summary to RAG memory
            if self.brain:
                try:
                    summary = self.brain.get_session_summary()
                    self._log_activity("session_summary",
                                       f"Interactions: {summary['interactions']}, "
                                       f"Mood: {summary['dominant_mood']}, "
                                       f"Facts: {summary['facts_learned']}")
                except Exception as e:
                    print(f"[INFO] Could not save session summary: {e}")

            # GPT session summarization — creates a narrative summary
            try:
                import vector_memory as vmem
                if vmem.is_available() and self.brain and self.brain._interaction_count >= 3:
                    # Build conversation turns from brain history
                    turns = []
                    for msg in self.brain.history:
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        if role == "user":
                            # Strip context markers
                            import re
                            clean = re.sub(r'\[.*?\]\s*', '', content).strip()
                            if clean:
                                turns.append(("patient", clean, ""))
                        elif role == "assistant":
                            turns.append(("reachy", content, ""))
                    if turns:
                        summary_text = vmem.summarize_session(turns)
                        if summary_text:
                            print(f"[SESSION] Summary: {summary_text}")
            except Exception as e:
                print(f"[INFO] Session summarization error: {e}")

            # Run final temporal pattern analysis
            try:
                import temporal_patterns as tp
                tp.analyze()
            except Exception:
                pass

            self._log_activity("session_end", "Reachy assistant stopped")
            self.autonomy.stop()
            self.fall_detector.stop()
            self.vitals_monitor.stop()
            self.music.stop()
            self.reminders.stop()
            if self.face_detector:
                self.face_detector.stop()
            if self._camera_server:
                self.robot.stop_camera_stream()
                if self._camera_server is not True:
                    from camera_stream import stop_stream_server
                    stop_stream_server(self._camera_server)
            self.robot.reset()
            self.robot.disconnect()

    def _route_active_session(self, text: str) -> str | None:
        """If a game, check-in, exercise, story, or reminiscence session is active, route input there."""
        lower = text.lower().strip()

        # Stop commands end any active session
        if any(w in lower for w in ["stop", "quit", "enough", "done", "exit"]):
            if self.exercises.is_active:
                return self.exercises.stop()
            if self.stories.is_active:
                return self.stories.stop()
            if self.meditation.is_active:
                return self.meditation.stop()

        # Journal is special — all speech goes into the entry
        from journal import is_active as journal_is_active, add_to_journal, save_journal, cancel_journal
        if journal_is_active():
            if any(w in lower for w in ["save journal", "done journaling", "finish journal"]):
                return save_journal()
            if any(w in lower for w in ["cancel journal", "discard journal"]):
                return cancel_journal()
            return add_to_journal(text)

        if self.checkin.is_active:
            result = self.checkin.process_answer(text)
            if not self.checkin.is_active and self.checkin.results:
                self.caregiver.alert_checkin_concern(self.checkin.results)
                self._post_dashboard("/api/checkin-history",
                                     {"results": self.checkin.results})
            return result

        if self.cognitive.is_active:
            return self.cognitive.play_turn(text)

        if self.exercises.is_active:
            # "next" or any input advances the exercise
            if any(w in lower for w in ["next", "continue", "go on", "keep going", "okay", "ok", "yes"]):
                resp, action = self.exercises.next_step()
                if action:
                    self.robot.perform(action)
                return resp
            # Any other input also advances (they might be responding)
            resp, action = self.exercises.next_step()
            if action:
                self.robot.perform(action)
            return resp

        if self.stories.is_active:
            if any(w in lower for w in ["next", "continue", "go on", "keep going", "okay", "ok", "yes", "more"]):
                return self.stories.next_page()
            return self.stories.next_page()

        if self.meditation.is_active:
            return self.meditation.next_step()

        if self.reminiscence.is_active:
            return self.reminiscence.continue_session(text)

        return None

    def _check_safety_alerts(self, lower: str, text: str, emotion: str):
        """Fire caregiver alerts for safety concerns."""
        crisis_words = ["don't want to live", "want to die", "kill myself",
                        "end it all", "hurt myself", "suicide", "can't go on"]
        emergency_words = ["chest pain", "can't breathe", "stroke", "bleeding",
                           "can't get up", "fell down", "fallen", "emergency"]

        for word in crisis_words:
            if word in lower:
                self.caregiver.alert_crisis(text)
                self._log_activity("crisis_alert", text)
                return
        for word in emergency_words:
            if word in lower:
                self.caregiver.alert_emergency(text)
                self._log_activity("emergency_alert", text)
                return

        if self.brain and hasattr(self.brain, "consecutive_sad"):
            if self.brain.consecutive_sad >= 4:
                self.caregiver.alert_sustained_distress(
                    self.brain.mood_history if hasattr(self.brain, "mood_history") else []
                )
