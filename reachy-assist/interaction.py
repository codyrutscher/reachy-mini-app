"""Main interaction loop — ties everything together: speech, emotion,
brain, face detection, reminders, check-in, cognitive games,
reminiscence therapy, caregiver alerts, weather, camera, inactivity
monitoring, and medication confirmation."""

import random
import time
import os
import json
import urllib.request
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
        self.cognitive = CognitiveExercises()
        self.music = MusicPlayer()
        self.exercises = GuidedExercises()
        self.stories = StoryReader()
        self.meditation = MeditationGuide()

        # Autonomy engine (proactive behaviors)
        from autonomy import AutonomyEngine
        self.autonomy = AutonomyEngine(profile_config=self.profile.get("autonomy", {}))

        self._pending_reminder = None
        self._dashboard_url = os.environ.get("DASHBOARD_URL", "http://localhost:5555")
        self._last_interaction = time.time()
        self._inactivity_threshold = 30 * 60  # 30 minutes
        self._inactivity_warned = False
        self._weather_city = os.environ.get("WEATHER_CITY", "auto")
        self._greeted_today = False

    # ── Reminder callback (called from background thread) ───────────

    def _on_reminder(self, message: str):
        self._pending_reminder = message

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
        """Check if the user is asking for a specific feature."""
        lower = text.lower().strip()

        # ── Weather ────────────────────────────────────────────────
        if any(w in lower for w in ["weather", "what's the weather", "temperature",
                                     "how's the weather", "is it cold", "is it hot",
                                     "is it raining"]):
            return self._handle_weather()

        # ── Good morning (weather + greeting) ──────────────────────
        if any(w in lower for w in ["good morning", "rise and shine"]):
            self.robot.perform("wake up")
            if not self._greeted_today:
                self._greeted_today = True
                from weather import weather_briefing
                briefing = weather_briefing(self._weather_city)
                return f"Good morning! I hope you slept well. {briefing} What would you like to do today?"
            return "Good morning! Ready for a new day!"

        # ── Check-in ───────────────────────────────────────────────
        if any(w in lower for w in ["check-in", "check in", "checkin", "how am i doing", "daily check"]):
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

        # ── Reminders ──────────────────────────────────────────────
        if any(w in lower for w in ["remind me", "add reminder", "set reminder", "medication", "medicine"]):
            return self._handle_reminder_add(lower)
        if any(w in lower for w in ["my reminders", "list reminders", "what reminders", "show reminders"]):
            return self.reminders.list_reminders()
        if any(w in lower for w in ["add appointment", "schedule appointment", "doctor appointment"]):
            return self._handle_appointment_add(lower)

        # ── Reminiscence ───────────────────────────────────────────
        if any(w in lower for w in ["memory lane", "reminisce", "memories", "tell me about the past",
                                     "remember when", "old times", "good old days"]):
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

        # ── Jokes ──────────────────────────────────────────────────
        if any(w in lower for w in ["tell me a joke", "joke", "make me laugh",
                                     "something funny", "funny", "another joke"]):
            from jokes import tell_joke
            self.robot.perform("wiggle")
            self._log_activity("joke", "Told a joke")
            return tell_joke()

        # ── Sleep tracking ─────────────────────────────────────────
        if any(w in lower for w in ["going to bed", "going to sleep", "bedtime",
                                     "goodnight", "good night", "time to sleep"]):
            from sleep_tracker import log_bedtime
            self.robot.perform("sleepy")
            self._log_activity("bedtime", "Patient going to sleep")
            return log_bedtime()
        if any(w in lower for w in ["just woke up", "i'm awake", "i am awake",
                                     "woke up", "morning"]) and "good morning" not in lower:
            from sleep_tracker import log_wake_time
            self._log_activity("wake_up", "Patient woke up")
            return log_wake_time()
        if any(w in lower for w in ["sleep report", "how did i sleep", "sleep quality",
                                     "sleep tracking", "my sleep"]):
            from sleep_tracker import sleep_report
            return sleep_report()

        # ── Affirmations & motivation ──────────────────────────────
        if any(w in lower for w in ["affirmation", "motivate me", "motivation",
                                     "inspire me", "something positive", "cheer me up",
                                     "i need encouragement", "encourage me"]):
            from affirmations import get_affirmation
            self.robot.express("joy")
            return get_affirmation()
        if any(w in lower for w in ["quote", "wisdom", "motivational quote"]):
            from affirmations import get_motivation
            self.robot.express("neutral")
            return get_motivation()
        if any(w in lower for w in ["grateful", "gratitude", "thankful"]):
            from affirmations import get_gratitude_prompt
            return get_gratitude_prompt()

        # ── Calendar / appointments ────────────────────────────────
        if any(w in lower for w in ["add appointment", "schedule appointment",
                                     "doctor appointment", "i have an appointment",
                                     "dentist", "doctor visit"]):
            from calendar_tracker import parse_appointment
            return parse_appointment(text)
        if any(w in lower for w in ["my appointments", "list appointments",
                                     "what appointments", "upcoming appointments",
                                     "calendar", "my schedule"]):
            from calendar_tracker import list_appointments
            return list_appointments()

        # ── Companion chat topics ──────────────────────────────────
        if any(w in lower for w in ["let's chat", "talk to me", "i'm bored",
                                     "i am bored", "conversation", "chat with me",
                                     "tell me something", "what should we talk about"]):
            from companion import get_conversation_starter
            self.robot.perform("curious")
            return get_conversation_starter()
        if any(w in lower for w in ["what can we talk about", "topics", "chat topics"]):
            from companion import list_topics
            return list_topics()

        # ── Hydration reminder ─────────────────────────────────────
        if any(w in lower for w in ["water", "thirsty", "hydration", "drink water",
                                     "need a drink"]) and "bring" not in lower:
            self._log_activity("hydration", "Patient mentioned water/thirst")
            return "Staying hydrated is so important! Try to drink a glass of water every hour. Would you like me to set a water reminder?"
        if "water reminder" in lower or "hydration reminder" in lower:
            # Schedule hourly water reminders via dashboard
            self._post_dashboard("/api/scheduled", {
                "text": "Time to drink some water! Stay hydrated!",
                "time": "09:00", "repeat": "daily",
            })
            self._log_activity("hydration_reminder", "Set up water reminders")
            return "I've set up a daily water reminder for you. I'll remind you to drink water throughout the day!"

        # ── News ───────────────────────────────────────────────────
        if any(w in lower for w in ["news", "headlines", "what's happening",
                                     "what's going on in the world", "read me the news",
                                     "today's news"]):
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

        # ── Voice journal ──────────────────────────────────────────
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

        # ── Date / time ───────────────────────────────────────────
        if any(w in lower for w in ["what time is it", "what's the time", "tell me the time",
                                     "current time"]):
            from datetime_helper import get_time_response
            return get_time_response()
        if any(w in lower for w in ["what day is it", "what's the date", "what date",
                                     "today's date", "what is today"]):
            from datetime_helper import get_date_response
            return get_date_response()
        if any(w in lower for w in ["what day of the week", "is it monday", "is it friday"]):
            from datetime_helper import get_day_response
            return get_day_response()

        # ── Breathing exercise ─────────────────────────────────────
        if any(w in lower for w in ["breathing", "breathe", "calm down", "relax", "anxiety exercise"]):
            self.robot.perform("breathe")
            return self._breathing_exercise()

        # ── Music ──────────────────────────────────────────────────
        if any(w in lower for w in ["play music", "play a song", "music", "sing",
                                     "play something", "melody", "lullaby"]):
            return self._handle_music(lower)
        if any(w in lower for w in ["stop music", "stop playing", "quiet", "silence"]):
            self.music.stop()
            return "Okay, music stopped."

        # ── Movement commands ──────────────────────────────────────
        movement_triggers = {
            "dance": ["dance", "dancing", "boogie", "move to the music"],
            "greet": ["say hello", "greet", "wave"],
            "goodbye": ["say goodbye", "bye bye", "see you"],
            "bow": ["bow", "take a bow"],
            "stretch": ["stretch", "stretching", "let's stretch"],
            "celebrate": ["celebrate", "party", "hooray", "woohoo"],
            "wiggle": ["wiggle", "be silly", "be funny", "make me laugh"],
            "look around": ["look around", "scan the room", "what do you see"],
            "curious": ["curious", "what's that", "interesting"],
            "think": ["think", "thinking", "hmm", "let me think"],
            "sleepy": ["sleepy", "tired", "goodnight", "bedtime"],
            "wake up": ["wake up"],
            "nod": ["nod", "agree"],
            "shake": ["shake your head", "disagree"],
            "rock": ["rock", "soothe", "calm me"],
        }
        for action, triggers in movement_triggers.items():
            if any(t in lower for t in triggers):
                self.robot.perform(action)
                move_responses = {
                    "dance": "How's that for some moves?",
                    "greet": "Hello there! Great to see you!",
                    "goodbye": "See you soon! Take care of yourself.",
                    "bow": "At your service!",
                    "stretch": "That felt good! Stretching is so important. Want to try together?",
                    "celebrate": "Woohoo! What are we celebrating?",
                    "wiggle": "Hehe, did that make you smile?",
                    "look around": "Just checking things out!",
                    "curious": "Hmm, that is interesting!",
                    "think": "Let me think about that...",
                    "sleepy": "Getting sleepy... rest is important. Goodnight!",
                    "wake up": "Good morning! Ready for a new day!",
                    "nod": "Yes, I agree!",
                    "shake": "Hmm, I'm not so sure about that.",
                    "rock": "There we go... nice and calm.",
                }
                return move_responses.get(action, "There you go!")

        # ── Smart home control ──────────────────────────────────────
        from smart_home import parse_smart_home_command
        sh_response, sh_handled = parse_smart_home_command(text)
        if sh_handled:
            self._log_activity("smart_home", text[:80])
            return sh_response

        # ── Vitals check ──────────────────────────────────────────
        if any(w in lower for w in ["my vitals", "check my vitals", "heart rate",
                                     "blood pressure", "oxygen level", "temperature",
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
                "- 'memory lane' — reminiscence therapy\n"
                "- 'play a game' — brain games\n"
                "- 'exercise' — guided physical exercises\n"
                "- 'meditate' — guided meditation\n"
                "- 'read me a story' — story time\n"
                "- 'tell me a joke' — jokes\n"
                "- 'news' — today's headlines\n"
                "- 'journal' — voice journaling\n"
                "- 'affirmation' — positive messages\n"
                "- 'let's chat' — conversation topics\n"
                "- 'add appointment' — track appointments\n"
                "- 'breathing exercise' — relaxation\n"
                "- 'play music' — melodies\n"
                "- 'weather' — current weather\n"
                "- 'what time is it' / 'what day is it'\n"
                "- 'good morning' / 'goodnight'\n"
                "- 'took my medication' — confirm meds\n"
                "- 'water reminder' — hydration\n"
                "- 'check my vitals' — health readings\n"
                "- 'lights on/off' — smart home control\n"
                "- 'set temperature' — thermostat\n"
                "- 'open/close blinds' — curtains\n"
                "- 'bedtime mode' — smart home scene\n"
                "- 'dance' / 'stretch' / 'celebrate' / 'wiggle'\n"
                "- 'stop' — end any active session\n"
                "- 'help' — show this menu"
            )

        return None

    # ── Feature handlers ────────────────────────────────────────────

    def _handle_weather(self) -> str:
        """Fetch and speak weather."""
        from weather import weather_briefing
        self._log_activity("weather_check", "Patient asked for weather")
        return weather_briefing(self._weather_city)

    def _handle_med_confirmation(self, text: str) -> str:
        """Patient confirms they took medication."""
        self._log_activity("med_confirmed", text)
        self._post_dashboard("/api/activity", {
            "action": "med_confirmed",
            "details": f"Patient confirmed: {text}",
        })
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
        except Exception:
            pass

    # ── Main loop ───────────────────────────────────────────────────

    def start(self):
        """Run the main interaction loop."""
        self.robot.connect()
        self.reminders.start()

        # Start camera stream server
        try:
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

        mode_info = []
        if self.brain:
            mode_info.append("LLM brain")
        if self.face_detector:
            mode_info.append("face detection")
        if self._camera_server:
            mode_info.append("camera stream")
        mode_str = " + ".join(mode_info) if mode_info else "basic mode"

        print(f"\n=== Reachy Accessibility Assistant ({mode_str}) ===")
        print(f"Profile: {self.profile['name']} ({self.profile_name})")
        print("Say 'help' to see what I can do. Press Ctrl+C to quit.\n")

        self._log_activity("session_start", "Reachy assistant started")
        self._last_med_check_minute = ""

        # Start autonomy engine
        self.autonomy.start()

        try:
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

                # Check for caregiver messages
                cg_messages = self._check_caregiver_messages()
                for cg_msg in cg_messages:
                    text = cg_msg.get("text", "")
                    if text:
                        self.robot.express("joy")
                        prefix = "Message from your caregiver: "
                        self.speech.speak(prefix + text)
                        self._log_to_dashboard("reachy", prefix + text)
                        time.sleep(0.5)
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

                # 1. Listen
                text = self.speech.listen()
                if not text:
                    self.speech.speak("I didn't catch that. Could you try again?")
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
                    time.sleep(0.5)
                    self.robot.reset()
                    continue

                # 3. Check for commands
                cmd_response = self._check_command(text)
                if cmd_response:
                    self.robot.express("neutral")
                    self.speech.speak(cmd_response)
                    self._log_to_dashboard("reachy", cmd_response)
                    time.sleep(0.5)
                    self.robot.reset()
                    continue

                # 4. Normal conversation flow
                text_emotion = self.emotion.detect(text)

                face_emotion = ""
                if self.face_detector:
                    face_emotion = self.face_detector.current_emotion

                emotion = self._combine_emotions(text_emotion, face_emotion)
                self.robot.express(emotion)
                self._update_dashboard_status(mood=emotion)
                self.autonomy.notify_mood(emotion)

                # Safety check for caregiver alerts
                lower = text.lower()
                self._check_safety_alerts(lower, text, emotion)

                if self.brain:
                    response = self.brain.think(text, emotion)
                else:
                    options = RESPONSES.get(emotion, RESPONSES["neutral"])
                    response = random.choice(options)

                self.speech.speak(response)
                self._log_to_dashboard("reachy", response)
                time.sleep(0.5)
                self.robot.reset()

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

            self._log_activity("session_end", "Reachy assistant stopped")
            self.autonomy.stop()
            self.music.stop()
            self.reminders.stop()
            if self.face_detector:
                self.face_detector.stop()
            if self._camera_server:
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
