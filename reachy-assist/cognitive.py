"""Cognitive exercises — word games, memory games, and trivia
to keep the mind active and engaged."""

import random


class CognitiveExercises:
    """Simple cognitive games suitable for elderly users."""

    def __init__(self, on_game_end=None):
        self.active_game = None
        self.game_state = {}
        self._on_game_end = on_game_end

    @property
    def is_active(self) -> bool:
        return self.active_game is not None

    def list_games(self) -> str:
        return (
            "I have a few fun brain games we can play:\n"
            "1. Word association — I say a word, you say the first thing that comes to mind\n"
            "2. Trivia — I'll ask you some fun questions\n"
            "3. Story builder — we take turns adding to a story\n"
            "4. Categories — name as many things as you can in a category\n"
            "5. Memory game — I'll give you a list and see what you remember\n\n"
            "Which one sounds fun? Just say the name or number."
        )

    def start_game(self, choice: str) -> str:
        """Start a game based on user's choice."""
        lower = choice.lower()
        if "word" in lower or "1" in lower or "association" in lower:
            return self._start_word_association()
        elif "trivia" in lower or "2" in lower or "question" in lower:
            return self._start_trivia()
        elif "story" in lower or "3" in lower:
            return self._start_story()
        elif "categor" in lower or "4" in lower:
            return self._start_categories()
        elif "memory" in lower or "5" in lower or "remember" in lower:
            return self._start_memory()
        else:
            return "I didn't catch which game. Could you say 'word association', 'trivia', 'story', 'categories', or 'memory game'?"

    def play_turn(self, user_input: str) -> str:
        """Process a turn in the active game."""
        if not self.active_game:
            return ""

        handlers = {
            "word_association": self._play_word_association,
            "trivia": self._play_trivia,
            "story": self._play_story,
            "categories": self._play_categories,
            "memory": self._play_memory,
        }
        handler = handlers.get(self.active_game)
        if handler:
            return handler(user_input)
        return ""

    def stop_game(self) -> str:
        self.active_game = None
        self.game_state = {}
        return "That was fun! We can play again anytime."

    def _report_score(self, game_type, score, max_score):
        """Notify listener of a completed game score."""
        if self._on_game_end:
            self._on_game_end(game_type, score, max_score)

    # ── Word Association ────────────────────────────────────────────

    _WORD_STARTERS = [
        "sunshine", "garden", "music", "ocean", "kitchen", "family",
        "morning", "flower", "book", "travel", "rain", "birthday",
        "chocolate", "summer", "friend", "dance", "home", "star",
    ]

    _WORD_RESPONSES = {
        "sunshine": ["warmth", "happiness", "morning", "yellow"],
        "garden": ["flowers", "green", "peaceful", "growing"],
        "music": ["dancing", "singing", "joy", "memories"],
        "ocean": ["waves", "blue", "calm", "beach"],
        "kitchen": ["cooking", "family", "warmth", "delicious"],
    }

    def _start_word_association(self) -> str:
        self.active_game = "word_association"
        word = random.choice(self._WORD_STARTERS)
        self.game_state = {"turns": 0, "last_word": word}
        return f"Let's play word association! I'll say a word, and you say the first thing that comes to mind. Ready?\n\nMy word is: {word}"

    def _play_word_association(self, user_input: str) -> str:
        self.game_state["turns"] += 1
        if self.game_state["turns"] >= 8:
            self._report_score("word_association", self.game_state["turns"], 8)
            self.active_game = None
            return "Great one! That was a fun round — you came up with some really creative connections. Want to play again or try something else?"

        # Use their word to generate a response
        words = user_input.strip().split()
        their_word = words[0] if words else "interesting"
        # Pick a loosely related word
        next_words = ["memory", "color", "feeling", "place", "sound",
                      "taste", "moment", "dream", "light", "warmth",
                      "story", "smile", "journey", "wonder", "peace"]
        my_word = random.choice(next_words)
        self.game_state["last_word"] = my_word
        return f"Nice! \"{their_word}\" makes me think of... \"{my_word}\". Your turn!"

    # ── Trivia ──────────────────────────────────────────────────────

    _TRIVIA = [
        {"q": "What color are emeralds?", "a": "green", "hint": "Think of grass and trees."},
        {"q": "In what country is the Eiffel Tower?", "a": "france", "hint": "It's in Paris!"},
        {"q": "What animal is known as man's best friend?", "a": "dog", "hint": "It barks and wags its tail."},
        {"q": "How many days are in a week?", "a": "seven", "hint": "Start counting from Monday..."},
        {"q": "What do bees make?", "a": "honey", "hint": "It's sweet and golden."},
        {"q": "What is the largest ocean on Earth?", "a": "pacific", "hint": "It's between Asia and the Americas."},
        {"q": "What fruit is traditionally used to make wine?", "a": "grape", "hint": "They grow on vines."},
        {"q": "What season comes after winter?", "a": "spring", "hint": "Flowers start to bloom."},
        {"q": "What instrument has 88 keys?", "a": "piano", "hint": "Black and white keys."},
        {"q": "What is the opposite of hot?", "a": "cold", "hint": "Think of ice and snow."},
    ]

    def _start_trivia(self) -> str:
        self.active_game = "trivia"
        random.shuffle(self._TRIVIA)
        self.game_state = {"index": 0, "score": 0, "gave_hint": False}
        q = self._TRIVIA[0]["q"]
        return f"Let's play some trivia! No pressure — it's just for fun.\n\n{q}"

    def _play_trivia(self, user_input: str) -> str:
        idx = self.game_state["index"]
        if idx >= len(self._TRIVIA):
            return self._end_trivia()

        current = self._TRIVIA[idx]
        lower = user_input.lower()

        if current["a"] in lower:
            self.game_state["score"] += 1
            self.game_state["index"] += 1
            self.game_state["gave_hint"] = False
            if self.game_state["index"] >= min(5, len(self._TRIVIA)):
                return self._end_trivia()
            next_q = self._TRIVIA[self.game_state["index"]]["q"]
            return f"That's right! Well done. 🎉\n\n{next_q}"
        elif not self.game_state["gave_hint"]:
            self.game_state["gave_hint"] = True
            return f"Not quite, but good try! Here's a hint: {current['hint']}"
        else:
            self.game_state["index"] += 1
            self.game_state["gave_hint"] = False
            answer = current["a"].capitalize()
            if self.game_state["index"] >= min(5, len(self._TRIVIA)):
                return f"The answer was {answer}. No worries! {self._end_trivia()}"
            next_q = self._TRIVIA[self.game_state["index"]]["q"]
            return f"The answer was {answer}. No worries at all! Let's try another one.\n\n{next_q}"

    def _end_trivia(self) -> str:
        score = self.game_state["score"]
        total = self.game_state["index"]
        self._report_score("trivia", score, total)
        self.active_game = None
        if score == total:
            return f"You got all {total} right! What a sharp mind you have!"
        elif score > total // 2:
            return f"You got {score} out of {total}! That's really good. Want to play again?"
        else:
            return f"You got {score} out of {total}. That was fun! The important thing is we exercised our brains a little."

    # ── Story Builder ───────────────────────────────────────────────

    _STORY_STARTERS = [
        "Once upon a time, in a cozy little village, there lived a kind old cat named Whiskers.",
        "One sunny morning, a curious bird landed on the windowsill and said hello.",
        "In a garden full of flowers, a tiny ladybug set off on a big adventure.",
        "There was once a baker who made the most magical bread in the whole town.",
    ]

    def _start_story(self) -> str:
        self.active_game = "story"
        starter = random.choice(self._STORY_STARTERS)
        self.game_state = {"story": [starter], "turns": 0}
        return f"Let's build a story together! I'll start, then you add the next part.\n\n{starter}\n\nWhat happens next?"

    def _play_story(self, user_input: str) -> str:
        self.game_state["story"].append(user_input)
        self.game_state["turns"] += 1

        if self.game_state["turns"] >= 5:
            self.active_game = None
            full_story = " ".join(self.game_state["story"])
            return f"What a wonderful story we made together! Here it is:\n\n\"{full_story}\"\n\nThat was really creative!"

        # Add a continuation
        continuations = [
            "And then, something unexpected happened...",
            "Just at that moment, they heard a sound...",
            "That gave them an idea...",
            "And do you know what they found?",
            "That reminded them of something important...",
        ]
        my_part = random.choice(continuations)
        self.game_state["story"].append(my_part)
        return f"I love that! {my_part} What happened next?"

    # ── Categories ──────────────────────────────────────────────────

    _CATEGORIES = [
        "fruits", "animals", "colors", "countries", "flowers",
        "things in a kitchen", "types of music", "things that are round",
        "things that make you smile", "things you'd find at a beach",
    ]

    def _start_categories(self) -> str:
        self.active_game = "categories"
        cat = random.choice(self._CATEGORIES)
        self.game_state = {"category": cat, "answers": [], "turns": 0}
        return f"Let's play categories! The category is: {cat}. Name as many as you can, one at a time. Say 'done' when you're finished."

    def _play_categories(self, user_input: str) -> str:
        if "done" in user_input.lower() or "stop" in user_input.lower():
            count = len(self.game_state["answers"])
            self._report_score("categories", count, count)
            self.active_game = None
            if count >= 5:
                return f"Wow, you named {count}! That's impressive. Your mind is sharp!"
            elif count > 0:
                return f"You named {count} — nice job! Every one counts."
            return "That's okay! We can try a different category next time."

        self.game_state["answers"].append(user_input.strip())
        self.game_state["turns"] += 1
        count = len(self.game_state["answers"])

        encouragements = [
            "Good one!", "Nice!", "That's a great answer!",
            "Oh, I like that one!", "Keep going!", "You're on a roll!",
        ]
        return f"{random.choice(encouragements)} That's {count} so far. Any more?"

    # ── Memory Game ─────────────────────────────────────────────────

    _MEMORY_LISTS = [
        ["apple", "chair", "sunshine", "book", "cat"],
        ["blue", "garden", "music", "bread", "star"],
        ["hat", "river", "clock", "flower", "smile"],
        ["cup", "bird", "window", "cake", "moon"],
    ]

    def _start_memory(self) -> str:
        self.active_game = "memory"
        items = random.choice(self._MEMORY_LISTS)
        self.game_state = {"items": items, "phase": "memorize"}
        items_str = ", ".join(items)
        return f"I'm going to give you a list of 5 words. Try to remember as many as you can!\n\nHere they are: {items_str}\n\nTake a moment to remember them, then tell me what you recall."

    def _play_memory(self, user_input: str) -> str:
        items = self.game_state["items"]
        lower = user_input.lower()
        remembered = [item for item in items if item in lower]
        forgot = [item for item in items if item not in lower]

        self._report_score("memory", len(remembered), len(items))
        self.active_game = None
        count = len(remembered)

        if count == len(items):
            return f"You remembered all {count}! That's amazing — what a great memory!"
        elif count >= 3:
            return f"You got {count} out of {len(items)} — that's really good! The ones you missed were: {', '.join(forgot)}. Great job!"
        elif count > 0:
            return f"You remembered {count}: {', '.join(remembered)}. The others were: {', '.join(forgot)}. That's okay — this is just exercise for the brain!"
        else:
            return f"That's alright! The words were: {', '.join(items)}. Memory games get easier with practice. Want to try again?"
