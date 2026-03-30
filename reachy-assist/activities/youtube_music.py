"""YouTube music streaming for Reachy — search and play real songs via yt-dlp.

Uses yt-dlp to search YouTube, extract audio URLs, and download/cache audio
files for playback through the existing MusicPlayer.play_file() system.

Requirements:
    pip install yt-dlp

Usage:
    from activities.youtube_music import YouTubeMusic
    yt = YouTubeMusic()
    result = yt.search_and_play("Frank Sinatra Fly Me To The Moon", player)
    # result = {"title": "...", "artist": "...", "duration": 180, "url": "..."}
"""

import os
import re
import threading
import time
from typing import Any, Optional

from core.log_config import get_logger

logger = get_logger("youtube_music")

# Cache downloaded audio files here
CACHE_DIR = os.path.join(os.path.dirname(__file__), "yt_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Max cached files before cleanup
MAX_CACHE_FILES = 50
# Max song duration in seconds (skip very long videos)
MAX_DURATION = 600  # 10 minutes


def _sanitize_filename(text: str) -> str:
    """Make a string safe for use as a filename."""
    return re.sub(r'[^\w\s-]', '', text).strip()[:80]


def _cleanup_cache() -> None:
    """Remove oldest cached files if we exceed the limit."""
    try:
        files = []
        for f in os.listdir(CACHE_DIR):
            fp = os.path.join(CACHE_DIR, f)
            if os.path.isfile(fp):
                files.append((os.path.getmtime(fp), fp))
        if len(files) <= MAX_CACHE_FILES:
            return
        files.sort()
        for _, fp in files[:len(files) - MAX_CACHE_FILES]:
            os.remove(fp)
            logger.debug("Cache cleanup: removed %s", os.path.basename(fp))
    except Exception as e:
        logger.warning("Cache cleanup error: %s", e)


class YouTubeMusic:
    """Search YouTube and play audio through the existing MusicPlayer."""

    def __init__(self) -> None:
        self._available = False
        self._current_title: Optional[str] = None
        self._current_artist: Optional[str] = None
        self._download_lock = threading.Lock()
        try:
            import yt_dlp  # noqa: F401
            self._available = True
            logger.info("yt-dlp available — YouTube music enabled")
        except ImportError:
            logger.warning("yt-dlp not installed — YouTube music disabled. pip install yt-dlp")

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def current_title(self) -> Optional[str]:
        return self._current_title

    @property
    def current_artist(self) -> Optional[str]:
        return self._current_artist

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Search YouTube for songs. Returns list of {title, artist, duration, video_id, url}."""
        if not self._available:
            return []
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "default_search": "ytsearch" + str(max_results),
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
                results = []
                for entry in (info or {}).get("entries", []):
                    if not entry:
                        continue
                    duration = entry.get("duration") or 0
                    if duration > MAX_DURATION:
                        continue
                    # Try to split "Artist - Title" from the video title
                    title = entry.get("title", "Unknown")
                    artist = entry.get("uploader", "Unknown")
                    if " - " in title:
                        parts = title.split(" - ", 1)
                        artist = parts[0].strip()
                        title = parts[1].strip()
                    results.append({
                        "title": title,
                        "artist": artist,
                        "duration": duration,
                        "video_id": entry.get("id", ""),
                        "url": entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                    })
                return results
        except Exception as e:
            logger.error("YouTube search error: %s", e)
            return []

    def download_audio(self, query: str) -> Optional[dict]:
        """Search YouTube and download the best audio match. Returns song info dict with file_path."""
        if not self._available:
            return None

        # Check cache first
        cache_key = _sanitize_filename(query)
        for ext in (".m4a", ".webm", ".mp3", ".opus"):
            cached = os.path.join(CACHE_DIR, cache_key + ext)
            if os.path.exists(cached):
                logger.info("Cache hit: %s", cache_key)
                return {"title": cache_key, "artist": "", "file_path": cached, "cached": True}

        import yt_dlp

        output_template = os.path.join(CACHE_DIR, cache_key + ".%(ext)s")

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "default_search": "ytsearch",
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": output_template,
            "noplaylist": True,
            "max_downloads": 1,
            # Don't download huge files
            "match_filter": yt_dlp.utils.match_filter_func("duration < 600"),
        }

        try:
            with self._download_lock:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"ytsearch:{query}", download=True)
                    entries = info.get("entries", [info]) if info else []
                    if not entries:
                        return None
                    entry = entries[0] if isinstance(entries, list) else entries

                    title = entry.get("title", query)
                    artist = entry.get("uploader", "Unknown")
                    duration = entry.get("duration", 0)

                    if " - " in title:
                        parts = title.split(" - ", 1)
                        artist = parts[0].strip()
                        title = parts[1].strip()

                    # Find the downloaded file
                    file_path = None
                    for ext in (".m4a", ".webm", ".mp3", ".opus", ".wav"):
                        candidate = os.path.join(CACHE_DIR, cache_key + ext)
                        if os.path.exists(candidate):
                            file_path = candidate
                            break

                    if not file_path:
                        # yt-dlp might have used the video title as filename
                        for f in os.listdir(CACHE_DIR):
                            fp = os.path.join(CACHE_DIR, f)
                            if os.path.isfile(fp) and os.path.getmtime(fp) > time.time() - 30:
                                file_path = fp
                                break

                    if not file_path:
                        logger.error("Download succeeded but file not found")
                        return None

                    _cleanup_cache()

                    result = {
                        "title": title,
                        "artist": artist,
                        "duration": duration,
                        "file_path": file_path,
                        "cached": False,
                    }
                    logger.info("Downloaded: %s by %s (%ds)", title, artist, duration)
                    return result

        except Exception as e:
            logger.error("YouTube download error: %s", e)
            return None

    def search_and_play(self, query: str, player: Any) -> Optional[dict]:
        """Search YouTube, download audio, and play it through the MusicPlayer.
        Returns song info dict or None if failed."""
        result = self.download_audio(query)
        if not result or not result.get("file_path"):
            return None

        self._current_title = result.get("title")
        self._current_artist = result.get("artist")
        player.play_file(result["file_path"])
        return result

    def search_and_play_async(self, query: str, player: Any,
                               callback: Optional[Any] = None) -> None:
        """Same as search_and_play but in a background thread.
        callback(result) is called when done (result may be None on failure)."""
        def _worker():
            result = self.search_and_play(query, player)
            if callback:
                try:
                    callback(result)
                except Exception:
                    pass
        threading.Thread(target=_worker, daemon=True).start()
