"""Sing-Along Mode — Reachy speaks lyrics line by line so the patient
can sing along.  Classic songs with hardcoded lyrics.

The session is managed turn-by-turn: Reachy speaks a line or two,
waits for the patient to respond (or just say 'next'), then continues.
"""

_SINGALONG_TRIGGERS = [
    "sing along", "let's sing", "sing with me", "sing a song",
    "singalong", "karaoke", "let's do a song", "sing together",
]

SONGS = {
    "you_are_my_sunshine": {
        "title": "You Are My Sunshine",
        "lines": [
            "You are my sunshine, my only sunshine",
            "You make me happy when skies are gray",
            "You'll never know dear, how much I love you",
            "Please don't take my sunshine away",
            "The other night dear, as I lay sleeping",
            "I dreamed I held you in my arms",
            "But when I awoke dear, I was mistaken",
            "So I hung my head and I cried",
        ],
    },
    "what_a_wonderful_world": {
        "title": "What a Wonderful World",
        "lines": [
            "I see trees of green, red roses too",
            "I see them bloom for me and you",
            "And I think to myself, what a wonderful world",
            "I see skies of blue and clouds of white",
            "The bright blessed day, the dark sacred night",
            "And I think to myself, what a wonderful world",
            "The colors of the rainbow, so pretty in the sky",
            "Are also on the faces of people going by",
            "I see friends shaking hands, saying how do you do",
            "They're really saying, I love you",
        ],
    },
    "somewhere_over_the_rainbow": {
        "title": "Somewhere Over the Rainbow",
        "lines": [
            "Somewhere over the rainbow, way up high",
            "There's a land that I heard of once in a lullaby",
            "Somewhere over the rainbow, skies are blue",
            "And the dreams that you dare to dream really do come true",
            "Someday I'll wish upon a star",
            "And wake up where the clouds are far behind me",
            "Where troubles melt like lemon drops",
            "Away above the chimney tops, that's where you'll find me",
        ],
    },
    "moon_river": {
        "title": "Moon River",
        "lines": [
            "Moon river, wider than a mile",
            "I'm crossing you in style some day",
            "Oh, dream maker, you heart breaker",
            "Wherever you're going, I'm going your way",
            "Two drifters, off to see the world",
            "There's such a lot of world to see",
            "We're after the same rainbow's end",
            "Waiting round the bend, my huckleberry friend",
            "Moon river and me",
        ],
    },
}


def is_singalong_trigger(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in _SINGALONG_TRIGGERS)


class SingAlong:
    """Manages a sing-along session."""

    def __init__(self):
        self.active = False
        self._song_key = None
        self._line_index = 0

    def start(self, text: str = "") -> str:
        """Pick a song and return the opening prompt."""
        lower = text.lower() if text else ""

        # Try to match a requested song
        chosen = None
        for key, song in SONGS.items():
            if song["title"].lower() in lower or key.replace("_", " ") in lower:
                chosen = key
                break

        if not chosen:
            # Pick a random one
            import random
            chosen = random.choice(list(SONGS.keys()))

        self._song_key = chosen
        self._line_index = 0
        self.active = True

        song = SONGS[chosen]
        first_lines = song["lines"][0]
        self._line_index = 1

        return (
            f"(Start a sing-along with the patient! The song is '{song['title']}'. "
            f"Say something warm like 'Oh, I love this one! Let's sing together.' "
            f"Then speak the first line slowly and clearly: \"{first_lines}\" "
            f"Pause after the line so they can sing along or repeat it. "
            f"Then say 'Ready for the next line?' or just continue naturally.)"
        )

    def next_line(self) -> str:
        """Return the next line prompt."""
        if not self.active or not self._song_key:
            return ""

        song = SONGS[self._song_key]
        if self._line_index >= len(song["lines"]):
            self.active = False
            return (
                f"(That was the last line of '{song['title']}'! "
                f"Wrap up warmly — say something like 'What a beautiful song! "
                f"You have a lovely voice.' Ask if they'd like to sing another.)"
            )

        line = song["lines"][self._line_index]
        self._line_index += 1
        remaining = len(song["lines"]) - self._line_index

        return (
            f"(Continue the sing-along. Speak the next line clearly: \"{line}\" "
            f"{'Last line coming up!' if remaining == 0 else f'{remaining} lines left.'} "
            f"Keep the energy warm and fun.)"
        )

    def stop(self) -> str:
        title = SONGS.get(self._song_key, {}).get("title", "the song")
        self.active = False
        return (
            f"(The patient wants to stop singing '{title}'. "
            f"Say something kind like 'That was fun! We can sing again anytime.')"
        )

    @property
    def is_active(self) -> bool:
        return self.active
