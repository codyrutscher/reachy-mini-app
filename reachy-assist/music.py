"""Music, melodies, and sound effects for Reachy — plays through Mac speakers.

Supports:
  - Generated melodies (sine wave synthesis)
  - Sound effects (short cues)
  - Song library (MP3/WAV files from a configurable folder)
  - Song search by title, artist, genre, or mood
"""

import json
import math
import os
import sqlite3
import struct
import subprocess
import threading
import wave

SOUNDS_DIR = os.path.join(os.path.dirname(__file__), "sounds")
SONGS_DIR = os.environ.get("REACHY_SONGS_DIR", os.path.join(os.path.dirname(__file__), "songs"))
SONGS_DB = os.path.join(os.path.dirname(__file__), "songs.db")

# ── Note frequencies ────────────────────────────────────────────────
_NOTES = {
    "C3": 130.81, "D3": 146.83, "E3": 164.81, "F3": 174.61,
    "G3": 196.00, "A3": 220.00, "B3": 246.94,
    "C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23,
    "G4": 392.00, "A4": 440.00, "B4": 493.88,
    "C5": 523.25, "D5": 587.33, "E5": 659.25, "F5": 698.46,
    "G5": 783.99, "A5": 880.00,
    "R": 0,
}

def n(name):
    return _NOTES.get(name, 0)

# ── Melodies (longer, for listening) ────────────────────────────────
MELODIES = {
    "calm": [
        (n("C4"), 1.0, 0.4), (n("E4"), 1.0, 0.4), (n("G4"), 1.5, 0.4),
        (n("R"), 0.3, 0), (n("E4"), 0.8, 0.35), (n("C4"), 1.2, 0.35),
        (n("R"), 0.5, 0),
        (n("F4"), 1.0, 0.4), (n("A4"), 1.0, 0.4), (n("G4"), 2.0, 0.35),
        (n("R"), 0.5, 0),
        (n("E4"), 1.0, 0.3), (n("D4"), 1.0, 0.3), (n("C4"), 2.5, 0.3),
    ],
    "happy": [
        (n("C4"), 0.3, 0.5), (n("E4"), 0.3, 0.5), (n("G4"), 0.3, 0.5),
        (n("C5"), 0.5, 0.5), (n("R"), 0.15, 0),
        (n("G4"), 0.3, 0.5), (n("C5"), 0.5, 0.55), (n("R"), 0.2, 0),
        (n("E4"), 0.3, 0.5), (n("G4"), 0.3, 0.5), (n("C5"), 0.3, 0.5),
        (n("E5"), 0.6, 0.5), (n("D5"), 0.3, 0.45), (n("C5"), 0.8, 0.5),
    ],
    "lullaby": [
        (n("E4"), 0.8, 0.3), (n("D4"), 0.4, 0.3), (n("C4"), 1.0, 0.3),
        (n("R"), 0.3, 0),
        (n("E4"), 0.8, 0.3), (n("D4"), 0.4, 0.3), (n("C4"), 1.0, 0.3),
        (n("R"), 0.3, 0),
        (n("G4"), 0.6, 0.3), (n("F4"), 0.6, 0.3), (n("E4"), 0.6, 0.3),
        (n("D4"), 0.6, 0.3), (n("C4"), 2.0, 0.25),
    ],
    "morning": [
        (n("G4"), 0.4, 0.45), (n("A4"), 0.4, 0.45), (n("B4"), 0.4, 0.45),
        (n("C5"), 0.8, 0.5), (n("R"), 0.2, 0),
        (n("E5"), 0.4, 0.5), (n("D5"), 0.4, 0.5), (n("C5"), 0.8, 0.5),
        (n("R"), 0.3, 0),
        (n("G4"), 0.3, 0.45), (n("C5"), 0.3, 0.5), (n("E5"), 0.5, 0.5),
        (n("G5"), 1.0, 0.45),
    ],
    "celebration": [
        (n("C4"), 0.2, 0.5), (n("C4"), 0.2, 0.5), (n("C4"), 0.2, 0.5),
        (n("E4"), 0.5, 0.55), (n("R"), 0.1, 0),
        (n("D4"), 0.2, 0.5), (n("D4"), 0.2, 0.5), (n("D4"), 0.2, 0.5),
        (n("F4"), 0.5, 0.55), (n("R"), 0.1, 0),
        (n("E4"), 0.3, 0.5), (n("G4"), 0.3, 0.5), (n("C5"), 0.8, 0.6),
    ],
    "thinking": [
        (n("E4"), 0.6, 0.3), (n("R"), 0.3, 0),
        (n("G4"), 0.6, 0.3), (n("R"), 0.3, 0),
        (n("F4"), 0.8, 0.3), (n("E4"), 0.4, 0.3),
        (n("D4"), 1.0, 0.3), (n("R"), 0.5, 0),
        (n("C4"), 0.6, 0.3), (n("E4"), 0.6, 0.3), (n("D4"), 1.5, 0.25),
    ],
    "gentle": [
        (n("C4"), 1.5, 0.25), (n("R"), 0.5, 0),
        (n("E4"), 1.5, 0.25), (n("R"), 0.5, 0),
        (n("G4"), 1.5, 0.25), (n("R"), 0.5, 0),
        (n("E4"), 1.5, 0.2), (n("R"), 0.5, 0), (n("C4"), 2.5, 0.2),
    ],
    "waltz": [
        (n("C4"), 0.5, 0.45), (n("E4"), 0.25, 0.4), (n("E4"), 0.25, 0.4),
        (n("D4"), 0.5, 0.45), (n("F4"), 0.25, 0.4), (n("F4"), 0.25, 0.4),
        (n("E4"), 0.5, 0.45), (n("G4"), 0.25, 0.4), (n("G4"), 0.25, 0.4),
        (n("F4"), 0.5, 0.45), (n("A4"), 0.25, 0.4), (n("A4"), 0.25, 0.4),
        (n("G4"), 0.75, 0.45), (n("R"), 0.25, 0), (n("C5"), 1.0, 0.4),
    ],
    "nostalgic": [
        (n("E4"), 1.0, 0.35), (n("D4"), 0.5, 0.35), (n("C4"), 0.5, 0.35),
        (n("D4"), 1.0, 0.35), (n("R"), 0.3, 0),
        (n("G3"), 0.8, 0.3), (n("C4"), 0.8, 0.35), (n("E4"), 1.2, 0.35),
        (n("R"), 0.3, 0),
        (n("D4"), 0.8, 0.3), (n("C4"), 0.8, 0.3), (n("G3"), 2.0, 0.25),
    ],
    "playful": [
        (n("G4"), 0.2, 0.5), (n("A4"), 0.2, 0.5), (n("G4"), 0.2, 0.5),
        (n("E4"), 0.4, 0.5), (n("R"), 0.1, 0),
        (n("G4"), 0.2, 0.5), (n("A4"), 0.2, 0.5), (n("G4"), 0.2, 0.5),
        (n("E5"), 0.4, 0.5), (n("R"), 0.1, 0),
        (n("D5"), 0.2, 0.5), (n("C5"), 0.2, 0.5), (n("A4"), 0.2, 0.5),
        (n("G4"), 0.6, 0.5),
    ],
    "rain": [
        (n("E5"), 0.3, 0.2), (n("R"), 0.2, 0), (n("D5"), 0.3, 0.2),
        (n("R"), 0.3, 0), (n("C5"), 0.4, 0.2), (n("R"), 0.2, 0),
        (n("B4"), 0.3, 0.2), (n("R"), 0.4, 0), (n("A4"), 0.5, 0.2),
        (n("R"), 0.3, 0), (n("G4"), 0.4, 0.2), (n("R"), 0.2, 0),
        (n("E4"), 0.6, 0.2), (n("R"), 0.5, 0), (n("C4"), 2.0, 0.15),
    ],
    "sunset": [
        (n("G4"), 1.2, 0.3), (n("E4"), 0.8, 0.3), (n("C4"), 1.5, 0.3),
        (n("R"), 0.5, 0),
        (n("A4"), 1.0, 0.3), (n("F4"), 0.8, 0.3), (n("D4"), 1.5, 0.25),
        (n("R"), 0.5, 0),
        (n("G4"), 0.8, 0.25), (n("E4"), 0.8, 0.25), (n("C4"), 3.0, 0.2),
    ],
}

# ── Sound effects (short cues) ──────────────────────────────────────
SOUND_EFFECTS = {
    "reminder_chime": [
        (n("E5"), 0.15, 0.5), (n("G5"), 0.15, 0.5), (n("E5"), 0.15, 0.5),
        (n("R"), 0.05, 0), (n("G5"), 0.3, 0.5),
    ],
    "alert": [
        (n("A4"), 0.2, 0.6), (n("R"), 0.1, 0),
        (n("A4"), 0.2, 0.6), (n("R"), 0.1, 0), (n("A4"), 0.3, 0.6),
    ],
    "success": [
        (n("C4"), 0.15, 0.5), (n("E4"), 0.15, 0.5), (n("G4"), 0.15, 0.5),
        (n("C5"), 0.4, 0.55),
    ],
    "error": [(n("E3"), 0.3, 0.4), (n("R"), 0.05, 0), (n("E3"), 0.5, 0.4)],
    "happy_ding": [(n("C5"), 0.1, 0.45), (n("E5"), 0.1, 0.45), (n("G5"), 0.25, 0.5)],
    "sad_tone": [(n("E4"), 0.4, 0.3), (n("D4"), 0.4, 0.3), (n("C4"), 0.8, 0.25)],
    "surprise_pop": [(n("R"), 0.05, 0), (n("C5"), 0.08, 0.6), (n("G5"), 0.2, 0.5)],
    "thinking_hum": [(n("D4"), 0.5, 0.2), (n("E4"), 0.5, 0.2), (n("D4"), 0.8, 0.15)],
    "comfort_tone": [(n("C4"), 0.6, 0.25), (n("E4"), 0.6, 0.25), (n("G4"), 1.0, 0.2)],
    "game_start": [(n("G4"), 0.15, 0.5), (n("C5"), 0.15, 0.5), (n("E5"), 0.3, 0.55)],
    "game_correct": [(n("E4"), 0.1, 0.5), (n("G4"), 0.1, 0.5), (n("C5"), 0.3, 0.55)],
    "game_wrong": [(n("E3"), 0.2, 0.35), (n("C3"), 0.4, 0.3)],
    "game_over": [
        (n("C5"), 0.2, 0.5), (n("G4"), 0.2, 0.5), (n("E4"), 0.2, 0.5),
        (n("C4"), 0.5, 0.45),
    ],
    "checkin_start": [(n("C4"), 0.2, 0.4), (n("E4"), 0.2, 0.4), (n("G4"), 0.3, 0.45)],
    "checkin_done": [
        (n("G4"), 0.15, 0.45), (n("A4"), 0.15, 0.45), (n("B4"), 0.15, 0.45),
        (n("C5"), 0.4, 0.5),
    ],
    "hello": [
        (n("C4"), 0.15, 0.45), (n("E4"), 0.15, 0.45), (n("G4"), 0.15, 0.45),
        (n("C5"), 0.3, 0.5),
    ],
    "goodbye": [
        (n("C5"), 0.2, 0.4), (n("G4"), 0.2, 0.4), (n("E4"), 0.2, 0.4),
        (n("C4"), 0.6, 0.35),
    ],
    "wake_up": [
        (n("G4"), 0.2, 0.4), (n("A4"), 0.2, 0.4), (n("B4"), 0.2, 0.4),
        (n("C5"), 0.15, 0.45), (n("E5"), 0.3, 0.5),
    ],
    "goodnight": [
        (n("E4"), 0.4, 0.3), (n("D4"), 0.4, 0.3), (n("C4"), 0.4, 0.25),
        (n("G3"), 1.0, 0.2),
    ],
    "breathe_in": [(n("C4"), 2.0, 0.15), (n("E4"), 2.0, 0.18)],
    "breathe_out": [(n("E4"), 2.0, 0.18), (n("C4"), 2.5, 0.12)],
}


class MusicPlayer:
    def __init__(self):
        self._process = None
        self._cache = {}
        self._song_db_ready = False
        os.makedirs(SOUNDS_DIR, exist_ok=True)
        os.makedirs(SONGS_DIR, exist_ok=True)
        self._init_song_db()
        print("[MUSIC] Ready")

    def _init_song_db(self):
        """Initialize the song library database and scan for files."""
        try:
            conn = sqlite3.connect(SONGS_DB)
            conn.row_factory = sqlite3.Row
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS songs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    artist TEXT DEFAULT 'Unknown',
                    genre TEXT DEFAULT '',
                    mood TEXT DEFAULT '',
                    era TEXT DEFAULT '',
                    duration_seconds REAL DEFAULT 0,
                    file_path TEXT NOT NULL UNIQUE,
                    play_count INTEGER DEFAULT 0,
                    last_played TEXT DEFAULT '',
                    added_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS playlist_songs (
                    playlist_id INTEGER,
                    song_id INTEGER,
                    position INTEGER DEFAULT 0,
                    FOREIGN KEY (playlist_id) REFERENCES playlists(id),
                    FOREIGN KEY (song_id) REFERENCES songs(id),
                    UNIQUE(playlist_id, song_id)
                );
            """)
            conn.commit()
            conn.close()
            self._song_db_ready = True
            # Scan for new files on startup
            self.scan_songs_folder()
        except Exception as e:
            print(f"[MUSIC] Song DB init error: {e}")

    def scan_songs_folder(self):
        """Scan the songs directory and add any new audio files to the database."""
        if not os.path.isdir(SONGS_DIR):
            return 0
        extensions = (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac")
        added = 0
        conn = sqlite3.connect(SONGS_DB)
        for root, _dirs, files in os.walk(SONGS_DIR):
            for fname in files:
                if not fname.lower().endswith(extensions):
                    continue
                fpath = os.path.join(root, fname)
                # Check if already in DB
                existing = conn.execute(
                    "SELECT id FROM songs WHERE file_path=?", (fpath,)
                ).fetchone()
                if existing:
                    continue
                # Parse title from filename: "Artist - Title.mp3" or just "Title.mp3"
                name_no_ext = os.path.splitext(fname)[0]
                if " - " in name_no_ext:
                    artist, title = name_no_ext.split(" - ", 1)
                else:
                    artist, title = "Unknown", name_no_ext
                # Try to guess mood/genre from folder structure
                rel = os.path.relpath(root, SONGS_DIR)
                genre = rel if rel != "." else ""
                conn.execute(
                    "INSERT INTO songs (title, artist, genre, file_path) VALUES (?,?,?,?)",
                    (title.strip(), artist.strip(), genre, fpath),
                )
                added += 1
        conn.commit()
        conn.close()
        if added:
            print(f"[MUSIC] Scanned songs folder: {added} new songs added")
        return added

    def add_song(self, file_path, title=None, artist="Unknown", genre="",
                 mood="", era=""):
        """Manually add a song to the library."""
        if not os.path.exists(file_path):
            return None
        if not title:
            title = os.path.splitext(os.path.basename(file_path))[0]
        conn = sqlite3.connect(SONGS_DB)
        try:
            conn.execute(
                "INSERT INTO songs (title, artist, genre, mood, era, file_path) VALUES (?,?,?,?,?,?)",
                (title, artist, genre, mood, era, file_path),
            )
            conn.commit()
            sid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.close()
            return sid
        except sqlite3.IntegrityError:
            conn.close()
            return None

    def search_songs(self, query="", mood="", genre="", limit=10):
        """Search the song library by text, mood, or genre."""
        conn = sqlite3.connect(SONGS_DB)
        conn.row_factory = sqlite3.Row
        conditions = []
        params = []
        if query:
            conditions.append("(title LIKE ? OR artist LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        if mood:
            conditions.append("mood LIKE ?")
            params.append(f"%{mood}%")
        if genre:
            conditions.append("genre LIKE ?")
            params.append(f"%{genre}%")
        where = " AND ".join(conditions) if conditions else "1=1"
        rows = conn.execute(
            f"SELECT * FROM songs WHERE {where} ORDER BY play_count DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_song_count(self):
        """Get total number of songs in the library."""
        conn = sqlite3.connect(SONGS_DB)
        count = conn.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
        conn.close()
        return count

    def play_song(self, song_id=None, title=None, query=None):
        """Play a song from the library by ID, title, or search query."""
        conn = sqlite3.connect(SONGS_DB)
        conn.row_factory = sqlite3.Row
        song = None
        if song_id:
            song = conn.execute("SELECT * FROM songs WHERE id=?", (song_id,)).fetchone()
        elif title:
            song = conn.execute(
                "SELECT * FROM songs WHERE title LIKE ? LIMIT 1", (f"%{title}%",)
            ).fetchone()
        elif query:
            song = conn.execute(
                "SELECT * FROM songs WHERE title LIKE ? OR artist LIKE ? LIMIT 1",
                (f"%{query}%", f"%{query}%"),
            ).fetchone()
        if not song:
            conn.close()
            return None
        # Update play count
        from datetime import datetime
        conn.execute(
            "UPDATE songs SET play_count=play_count+1, last_played=? WHERE id=?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), song["id"]),
        )
        conn.commit()
        conn.close()
        self.play_file(song["file_path"])
        return dict(song)

    def play_by_mood(self, mood):
        """Play a random song matching the given mood."""
        import random as _rand
        conn = sqlite3.connect(SONGS_DB)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM songs WHERE mood LIKE ?", (f"%{mood}%",)
        ).fetchall()
        conn.close()
        if not rows:
            return None
        song = _rand.choice(rows)
        return self.play_song(song_id=song["id"])

    def get_song_for_request(self, text):
        """Parse a natural language song request and try to play it.
        Returns (response_text, played_bool)."""
        lower = text.lower()
        # Try direct title/artist search
        for prefix in ["play ", "put on ", "i want to hear ", "can you play "]:
            if prefix in lower:
                query = lower.split(prefix, 1)[1].strip().rstrip("?.,!")
                if query:
                    song = self.play_song(query=query)
                    if song:
                        return (f"Now playing: {song['title']} by {song['artist']}.", True)
                    return (f"I couldn't find '{query}' in my song library. "
                            f"I have {self.get_song_count()} songs. "
                            f"Try asking for a genre or mood instead!", False)

        # Mood-based requests
        mood_map = {
            "happy": ["happy", "cheerful", "upbeat", "fun"],
            "calm": ["calm", "relaxing", "peaceful", "soothing", "chill"],
            "sad": ["sad", "melancholy", "blue"],
            "energetic": ["energetic", "lively", "dance", "party"],
            "nostalgic": ["nostalgic", "old", "classic", "retro", "oldies"],
            "romantic": ["romantic", "love", "sweet"],
            "spiritual": ["spiritual", "hymn", "gospel", "church"],
        }
        for mood, triggers in mood_map.items():
            if any(t in lower for t in triggers):
                song = self.play_by_mood(mood)
                if song:
                    return (f"Here's something {mood}: {song['title']} by {song['artist']}.", True)
                # Fall back to a matching generated melody
                melody_fallback = {"happy": "happy", "calm": "calm", "sad": "nostalgic",
                                   "energetic": "celebration", "nostalgic": "nostalgic",
                                   "romantic": "gentle", "spiritual": "gentle"}
                mel = melody_fallback.get(mood, "gentle")
                self.play_melody(mel)
                return (f"I don't have {mood} songs in my library yet, "
                        f"but here's a {mel} melody for you.", True)

        return None, False

    # ── Playlist management ─────────────────────────────────────────

    def create_playlist(self, name, description=""):
        conn = sqlite3.connect(SONGS_DB)
        try:
            conn.execute(
                "INSERT INTO playlists (name, description) VALUES (?,?)",
                (name, description),
            )
            conn.commit()
            pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.close()
            return pid
        except sqlite3.IntegrityError:
            conn.close()
            return None

    def add_to_playlist(self, playlist_name, song_id):
        conn = sqlite3.connect(SONGS_DB)
        pl = conn.execute(
            "SELECT id FROM playlists WHERE name=?", (playlist_name,)
        ).fetchone()
        if not pl:
            conn.close()
            return False
        pos = conn.execute(
            "SELECT COALESCE(MAX(position),0)+1 FROM playlist_songs WHERE playlist_id=?",
            (pl[0],),
        ).fetchone()[0]
        try:
            conn.execute(
                "INSERT INTO playlist_songs (playlist_id, song_id, position) VALUES (?,?,?)",
                (pl[0], song_id, pos),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        conn.close()
        return True

    def list_playlists(self):
        conn = sqlite3.connect(SONGS_DB)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM playlists ORDER BY name").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @property
    def is_playing(self):
        if self._process and self._process.poll() is None:
            return True
        return False

    def stop(self):
        if self._process and self._process.poll() is None:
            self._process.terminate()
            self._process = None

    def play_file(self, path):
        if not os.path.exists(path):
            print(f"[MUSIC] File not found: {path}")
            return
        self.stop()
        self._process = subprocess.Popen(
            ["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print(f"[MUSIC] Playing: {os.path.basename(path)}")

    def play_melody(self, name):
        notes = MELODIES.get(name)
        if not notes:
            print(f"[MUSIC] Unknown melody: {name}")
            return
        self._play_notes(f"melody_{name}", notes)

    def play_sound(self, name):
        notes = SOUND_EFFECTS.get(name)
        if not notes:
            print(f"[MUSIC] Unknown sound: {name}")
            return
        self._play_notes(f"sfx_{name}", notes)

    def list_melodies(self):
        return list(MELODIES.keys())

    def list_sounds(self):
        return list(SOUND_EFFECTS.keys())

    def _play_notes(self, cache_key, notes):
        if cache_key not in self._cache:
            path = os.path.join(SOUNDS_DIR, f"{cache_key}.wav")
            if not os.path.exists(path):
                _write_wav(path, notes)
            self._cache[cache_key] = path
        self.play_file(self._cache[cache_key])


def _write_wav(path, notes, sample_rate=44100):
    samples = []
    for freq, dur, vol in notes:
        n_samples = int(sample_rate * dur)
        fade = int(sample_rate * 0.02)
        for i in range(n_samples):
            t = i / sample_rate
            envelope = 1.0
            if i < fade:
                envelope = i / fade
            elif i > n_samples - fade:
                envelope = (n_samples - i) / fade
            if freq > 0:
                val = (
                    math.sin(2 * math.pi * freq * t) * 0.7
                    + math.sin(2 * math.pi * freq * 2 * t) * 0.2
                    + math.sin(2 * math.pi * freq * 3 * t) * 0.1
                )
                samples.append(val * vol * envelope)
            else:
                samples.append(0.0)
    peak = max(abs(s) for s in samples) if samples else 1.0
    if peak > 0:
        samples = [s / peak * 0.8 for s in samples]
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for s in samples:
            wf.writeframes(struct.pack("<h", int(s * 32767)))
    print(f"[MUSIC] Generated: {os.path.basename(path)}")
