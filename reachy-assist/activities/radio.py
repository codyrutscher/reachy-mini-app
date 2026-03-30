"""Radio DJ Mode — Reachy becomes a personal radio station.

Manages a playlist queue, plays music, and fills gaps with DJ commentary,
fun facts, dedications, and mood-aware song selection.

Usage:
    from activities.radio import RadioDJ
    dj = RadioDJ(music_player)
    dj.start()           # begin broadcasting
    dj.request("play something happy")
    dj.skip()            # next track
    dj.stop()            # end broadcast
"""

import random
import threading
import time
from typing import Any, Optional

from core.log_config import get_logger
from activities.music import MusicPlayer, MELODIES

logger = get_logger("radio")

# ── DJ commentary templates ─────────────────────────────────────────

DJ_INTROS: list[str] = [
    "You're listening to Radio Reachy, your personal companion station.",
    "Welcome back to Radio Reachy. Let's keep the good vibes going.",
    "This is DJ Reachy, spinning tunes just for you.",
    "Radio Reachy here. I picked this next one especially for you.",
    "Hey there, it's your favorite robot DJ. Here's what's coming up.",
]

DJ_TRANSITIONS: list[str] = [
    "That was a nice one. Here's another you might enjoy.",
    "Hope you liked that. Let's keep the music flowing.",
    "Up next, something a little different.",
    "And now, for your listening pleasure...",
    "Let's switch it up a bit. Here we go.",
    "One more coming your way.",
    "I think you'll like this next one.",
]

DJ_DEDICATIONS: list[str] = [
    "This next one goes out to you, {name}. Because you deserve something special.",
    "I'm dedicating this one to {name}. Enjoy.",
    "{name}, this one's for you. I hope it makes you smile.",
    "A little something for {name}, with love from your robot DJ.",
]

DJ_FUN_FACTS: list[str] = [
    "Did you know? Music can lower your heart rate and reduce anxiety.",
    "Fun fact: listening to music releases dopamine, the feel-good chemical in your brain.",
    "Here's something neat: your brain processes music in both hemispheres at once.",
    "Did you know? Singing along to music can improve your breathing and posture.",
    "Music trivia: the world's oldest known musical instrument is a 40,000-year-old flute.",
    "Fun fact: plants grow faster when you play them music. Maybe we should try that here.",
    "Did you know? Your heartbeat actually syncs up with the tempo of the music you listen to.",
    "Here's a good one: babies can recognize music they heard in the womb.",
    "Music fact: the chills you get from a great song are caused by a dopamine rush.",
    "Did you know? Playing music can strengthen the connection between the two halves of your brain.",
]

DJ_TIME_COMMENTS: dict[str, list[str]] = {
    "morning": [
        "Good morning. Let's start the day with something bright.",
        "Rise and shine. Here's some music to wake up to.",
        "Morning time. I've got the perfect soundtrack for breakfast.",
    ],
    "afternoon": [
        "Afternoon vibes coming your way.",
        "Perfect time for some music. Let's enjoy the afternoon.",
        "Midday tunes to keep your spirits up.",
    ],
    "evening": [
        "Evening time. Let's wind down with something nice.",
        "The sun's going down, and the music gets mellow.",
        "Time to relax. Here's something soothing for the evening.",
    ],
    "night": [
        "Late night radio. Just you and me and some gentle tunes.",
        "Quiet hours. Let's keep it soft and peaceful.",
        "Nighttime. Here's something to help you drift off.",
    ],
}

# ── Mood to melody/genre mapping ────────────────────────────────────

MOOD_PLAYLISTS: dict[str, list[str]] = {
    "happy": ["happy", "celebration", "playful", "morning"],
    "calm": ["calm", "gentle", "lullaby", "rain", "sunset"],
    "sad": ["nostalgic", "gentle", "rain", "sunset"],
    "energetic": ["happy", "celebration", "playful", "waltz"],
    "nostalgic": ["nostalgic", "waltz", "sunset", "gentle"],
    "sleepy": ["lullaby", "calm", "gentle", "rain"],
    "neutral": ["calm", "morning", "thinking", "waltz", "gentle"],
}

TIME_MOODS: dict[str, str] = {
    "morning": "energetic",
    "afternoon": "neutral",
    "evening": "calm",
    "night": "sleepy",
}


def _get_time_of_day() -> str:
    """Return 'morning', 'afternoon', 'evening', or 'night'."""
    hour = time.localtime().tm_hour
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    return "night"


class RadioDJ:
    """Personal radio station powered by Reachy's music system."""

    def __init__(self, player: MusicPlayer, patient_name: str = "friend") -> None:
        self.player: MusicPlayer = player
        self.patient_name: str = patient_name
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._queue: list[str] = []  # melody names queued up
        self._current: Optional[str] = None
        self._current_artist: Optional[str] = None
        self._current_source: str = "melody"  # "melody" or "youtube"
        self._mood: str = "neutral"
        self._songs_played: int = 0
        self._skip_event: threading.Event = threading.Event()
        self._stop_event: threading.Event = threading.Event()
        self._speak_fn: Optional[Any] = None  # callback to speak DJ commentary

        # YouTube music integration
        self._youtube = None
        try:
            from activities.youtube_music import YouTubeMusic
            yt = YouTubeMusic()
            if yt.is_available:
                self._youtube = yt
                logger.info("YouTube music enabled for Radio DJ")
        except Exception as e:
            logger.debug("YouTube music not available: %s", e)

    def set_speak_fn(self, fn: Any) -> None:
        """Set a callback function for DJ commentary. fn(text) -> None."""
        self._speak_fn = fn

    def set_mood(self, mood: str) -> None:
        """Update the current mood — affects song selection."""
        if mood in MOOD_PLAYLISTS:
            self._mood = mood
            logger.info("DJ mood set to: %s", mood)

    def set_patient_name(self, name: str) -> None:
        """Update the patient name for dedications."""
        self.patient_name = name

    def _say(self, text: str) -> None:
        """Speak DJ commentary through the configured callback, or log it."""
        logger.info("DJ: %s", text)
        if self._speak_fn:
            try:
                self._speak_fn(text)
            except Exception as e:
                logger.warning("DJ speak error: %s", e)

    def _pick_melody(self) -> str:
        """Pick the next melody based on mood and what's been played."""
        pool = MOOD_PLAYLISTS.get(self._mood, MOOD_PLAYLISTS["neutral"])
        # Filter to melodies that actually exist
        available = [m for m in pool if m in MELODIES]
        if not available:
            available = list(MELODIES.keys())
        # Avoid repeating the last played
        if self._current and self._current in available and len(available) > 1:
            available = [m for m in available if m != self._current]
        return random.choice(available)

    def _pick_commentary(self) -> str:
        """Pick what the DJ says between songs."""
        self._songs_played += 1
        # First song — intro
        if self._songs_played == 1:
            tod = _get_time_of_day()
            return random.choice(DJ_TIME_COMMENTS.get(tod, DJ_INTROS))
        # Every 4th song — fun fact
        if self._songs_played % 4 == 0:
            return random.choice(DJ_FUN_FACTS)
        # Every 3rd song — dedication
        if self._songs_played % 3 == 0:
            template = random.choice(DJ_DEDICATIONS)
            return template.format(name=self.patient_name)
        # Default — transition
        return random.choice(DJ_TRANSITIONS)

    def request(self, text: str) -> str:
        """Handle a song request from the patient. Returns response text."""
        lower = text.lower().strip()

        # Try YouTube first for specific song/artist requests
        if self._youtube:
            # Check if this looks like a specific song/artist request (not just a mood)
            specific_prefixes = [
                "play me some ", "play some ", "play ", "put on ",
                "i want to hear ", "can you play ", "how about ",
                "i'd like to hear ", "let's listen to ",
            ]
            for prefix in specific_prefixes:
                if prefix in lower:
                    query = lower.split(prefix, 1)[1].strip().rstrip("?.,!")
                    if query and not self._is_mood_word(query):
                        result = self._youtube.search_and_play(query, self.player)
                        if result:
                            self._current = result.get("title", query)
                            self._current_artist = result.get("artist", "")
                            self._current_source = "youtube"
                            self._songs_played += 1
                            title = result.get("title", "that song")
                            artist = result.get("artist", "")
                            if artist and artist != "Unknown":
                                return f"Now playing: {title} by {artist}."
                            return f"Now playing: {title}."

        # Try the music player's built-in request handler (local song library)
        result, played = self.player.get_song_for_request(text)
        if played and result:
            self._songs_played += 1
            self._current_source = "local"
            return result

        # Mood-based requests
        mood_keywords: dict[str, str] = {
            "happy": "happy", "cheerful": "happy", "upbeat": "happy",
            "calm": "calm", "relaxing": "calm", "peaceful": "calm", "chill": "calm",
            "sad": "sad", "melancholy": "sad", "blue": "sad",
            "energetic": "energetic", "lively": "energetic", "dance": "energetic",
            "sleepy": "sleepy", "bedtime": "sleepy", "lullaby": "sleepy",
            "nostalgic": "nostalgic", "classic": "nostalgic", "oldies": "nostalgic",
        }
        for keyword, mood in mood_keywords.items():
            if keyword in lower:
                self.set_mood(mood)
                # Try YouTube for mood-based search
                if self._youtube:
                    yt_query = self._mood_to_youtube_query(mood)
                    result = self._youtube.search_and_play(yt_query, self.player)
                    if result:
                        self._current = result.get("title", mood)
                        self._current_artist = result.get("artist", "")
                        self._current_source = "youtube"
                        self._songs_played += 1
                        title = result.get("title", "a song")
                        return f"Switching to {mood} mode. Now playing: {title}."
                # Fallback to synthesized melody
                melody = self._pick_melody()
                self.player.play_melody(melody)
                self._current = melody
                self._current_artist = None
                self._current_source = "melody"
                self._songs_played += 1
                return f"Switching to {mood} mode. Here's a {melody} melody for you."

        # Specific melody requests
        for mel_name in MELODIES:
            if mel_name in lower:
                self.player.play_melody(mel_name)
                self._current = mel_name
                self._current_artist = None
                self._current_source = "melody"
                self._songs_played += 1
                return f"Playing the {mel_name} melody."

        # Generic "play music" / "play something" — try YouTube with a nice query
        if any(w in lower for w in ["play", "music", "song", "tune", "radio"]):
            if self._youtube:
                yt_query = self._mood_to_youtube_query(self._mood)
                result = self._youtube.search_and_play(yt_query, self.player)
                if result:
                    self._current = result.get("title", "a song")
                    self._current_artist = result.get("artist", "")
                    self._current_source = "youtube"
                    self._songs_played += 1
                    return f"Here's {result.get('title', 'a song')} for you."
            # Fallback
            melody = self._pick_melody()
            self.player.play_melody(melody)
            self._current = melody
            self._current_artist = None
            self._current_source = "melody"
            self._songs_played += 1
            return f"Here's a {melody} tune for you."

        return ""

    @staticmethod
    def _is_mood_word(text: str) -> bool:
        """Check if the text is just a mood keyword (not a specific song/artist)."""
        mood_only = {
            "happy", "sad", "calm", "relaxing", "energetic", "sleepy",
            "nostalgic", "cheerful", "peaceful", "lively", "chill",
            "upbeat", "melancholy", "something", "music", "a song",
        }
        return text.strip().lower() in mood_only

    @staticmethod
    def _mood_to_youtube_query(mood: str) -> str:
        """Convert a mood to a good YouTube search query for elderly-friendly music."""
        queries = {
            "happy": "feel good oldies classic happy songs",
            "calm": "relaxing instrumental peaceful music",
            "sad": "beautiful nostalgic classic ballads",
            "energetic": "upbeat classic rock and roll oldies",
            "nostalgic": "greatest hits 1950s 1960s classic songs",
            "sleepy": "gentle lullaby relaxing sleep music",
            "neutral": "easy listening classic hits",
        }
        return queries.get(mood, "classic easy listening music")

    def skip(self) -> str:
        """Skip to the next track."""
        self.player.stop()
        self._skip_event.set()
        return "Skipping to the next track."

    def start(self) -> str:
        """Start the radio broadcast in a background thread."""
        if self._running:
            return "Radio Reachy is already on the air."
        self._running = True
        self._stop_event.clear()
        self._skip_event.clear()
        self._songs_played = 0

        # Set mood based on time of day
        tod = _get_time_of_day()
        self._mood = TIME_MOODS.get(tod, "neutral")

        self._thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self._thread.start()
        logger.info("Radio started (mood=%s, time=%s)", self._mood, tod)
        return f"Radio Reachy is on the air. {random.choice(DJ_INTROS)}"

    def stop(self) -> str:
        """Stop the radio broadcast."""
        if not self._running:
            return "Radio is already off."
        self._running = False
        self._stop_event.set()
        self._skip_event.set()  # unblock any wait
        self.player.stop()
        logger.info("Radio stopped after %d songs", self._songs_played)
        return f"Radio Reachy signing off. We played {self._songs_played} songs today. See you next time."

    @property
    def is_on(self) -> bool:
        return self._running

    def get_status(self) -> dict:
        """Return current radio state for the dashboard."""
        return {
            "on_air": self._running,
            "current_track": self._current,
            "current_artist": self._current_artist,
            "source": self._current_source,
            "mood": self._mood,
            "songs_played": self._songs_played,
            "time_of_day": _get_time_of_day(),
            "youtube_available": self._youtube is not None,
        }

    def _broadcast_loop(self) -> None:
        """Main radio loop — plays songs with DJ commentary between them."""
        while self._running and not self._stop_event.is_set():
            # DJ commentary
            commentary = self._pick_commentary()
            self._say(commentary)

            # Small pause after commentary
            if self._stop_event.wait(timeout=2.0):
                break

            # Try YouTube first, fall back to synthesized melody
            played_yt = False
            if self._youtube:
                try:
                    yt_query = self._mood_to_youtube_query(self._mood)
                    result = self._youtube.search_and_play(yt_query, self.player)
                    if result:
                        self._current = result.get("title", "a song")
                        self._current_artist = result.get("artist", "")
                        self._current_source = "youtube"
                        played_yt = True
                        logger.info("Now playing (YT): %s by %s",
                                    self._current, self._current_artist)
                except Exception as e:
                    logger.warning("YouTube playback error, falling back to melody: %s", e)

            if not played_yt:
                melody = self._pick_melody()
                self._current = melody
                self._current_artist = None
                self._current_source = "melody"
                self.player.play_melody(melody)
                logger.info("Now playing (melody): %s", melody)

            # Wait for the song to finish
            # YouTube songs can be longer (up to ~5 min), melodies are ~10s
            max_wait = 360 if played_yt else 20
            for _ in range(max_wait):
                if self._stop_event.is_set() or self._skip_event.is_set():
                    break
                if not self.player.is_playing:
                    break
                time.sleep(1.0)

            self._skip_event.clear()

            # Brief pause between songs
            if not self._stop_event.is_set():
                self._stop_event.wait(timeout=random.uniform(2.0, 4.0))

        self._running = False
        self._current = None
        self._current_artist = None
        logger.info("Broadcast loop ended")
