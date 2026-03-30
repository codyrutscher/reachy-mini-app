"""Follow-up question engine — makes Reachy a better conversationalist
by asking relevant follow-up questions based on what the patient said."""

import random
import os
import re
import datetime
from core.log_config import get_logger

logger = get_logger("followups")

# Try to connect to Supabase for persistence
try:
    import memory.db_supabase as _db
    _db.init_bot_tables()
    _supabase = _db.is_available()
except Exception:
    _supabase = False


FOLLOW_UPS = {
    "family": {
        "triggers": ["daughter", "son", "wife", "husband", "grandchild", "family", "kids"],
        "questions": [
            "How are they doing?",
            "When did you last see them?",
            "What's your favorite memory with them?",
            "Do they live nearby?",
        ],
    },
    "food": {
        "triggers": ["ate", "lunch", "dinner", "breakfast", "cook", "bake", "hungry"],
        "questions": [
            "What did you have?",
            "Was it good?",
            "Do you enjoy cooking?",
            "What's your favorite thing to eat?",
        ],
    },
    "outdoors": {
        "triggers": ["park", "walk", "garden", "outside", "weather", "sun", "rain"],
        "questions": [
            "What was the weather like?",
            "Did you enjoy being outside?",
            "Do you go there often?",
            "That sounds peaceful. What did you see?",
        ],
    },
    "health": {
        "triggers": ["tired", "pain", "hurt", "sleep", "doctor", "medicine", "sick"],
        "questions": [
            "I'm sorry to hear that. How long have you been feeling this way?",
            "Did you sleep okay last night?",
            "Is there anything I can do to help you feel more comfortable?",
            "Have you mentioned this to your caregiver?",
        ],
    },
    "music": {
        "triggers": ["song", "music", "sing", "dance", "radio", "listen"],
        "questions": [
            "What kind of music do you like?",
            "Do you have a favorite song?",
            "Did you ever play an instrument?",
            "Want me to play something for you?",
        ],
    },
    "memories": {
        "triggers": ["remember", "used to", "back when", "years ago", "childhood", "young"],
        "questions": [
            "Tell me more about that. What was it like?",
            "That sounds like a wonderful time. What else do you remember?",
            "How old were you then?",
            "Who were you with?",
        ],
    },
    "pets": {
        "triggers": ["dog", "cat", "pet", "bird", "puppy", "kitten", "animal"],
        "questions": [
            "What's their name?",
            "How long have you had them?",
            "They sound lovely. What are they like?",
            "Do they keep you good company?",
        ],
    },
    "feelings": {
        "triggers": ["happy", "sad", "worried", "scared", "angry", "lonely", "bored"],
        "questions": [
            "Do you want to talk about what's on your mind?",
            "What do you think brought that on?",
            "Is there something I can do to help?",
            "How long have you been feeling that way?",
        ],
    },
}

ACKNOWLEDGMENTS = {
    "family": ["That's so nice to hear!", "Family is everything.", "That sounds wonderful."],
    "food": ["Mmm, that sounds good!", "I love hearing about food.", "That's making me hungry!"],
    "outdoors": ["Fresh air does wonders.", "That sounds like a lovely time.", "Being outside is so good for you."],
    "health": ["I hear you, and I care about how you're feeling.", "Thank you for telling me.", "Your wellbeing matters to me."],
    "music": ["Music is such a gift.", "I love that you enjoy music!", "There's nothing quite like a good song."],
    "memories": ["What a beautiful memory.", "I love hearing your stories.", "Those sound like special times."],
    "pets": ["Animals are the best companions.", "That's so sweet!", "Pets really do make life better."],
    "feelings": ["Thank you for sharing that with me.", "Your feelings are always valid.", "I'm glad you feel comfortable telling me."],
}

_recent_questions = []
_last_topic = "general"

YES_CONTINUATIONS = {
    "family": ["Tell me about them! I'd love to hear.", "Oh wonderful! What are they like?", "That's great. Who are you closest to?"],
    "food": ["Ooh, what's your specialty?", "I bet it's delicious! What do you like to make?", "Nice! What's your go-to comfort food?"],
    "outdoors": ["That's lovely. What do you enjoy most about it?", "Fresh air is the best. Where do you like to go?", "I can see why! What's your favorite spot?"],
    "health": ["I'm glad you're taking care of yourself. Tell me more.", "That's important. How has it been going?", "Good to know. Is there anything I can help with?"],
    "music": ["Oh I'd love to hear about it! What's the song?", "Music is wonderful. Who's your favorite artist?", "That's great! What kind of music moves you?"],
    "memories": ["I'd love to hear the story! Go on.", "Those are the best kind. Tell me more.", "What a treasure. What stands out most?"],
    "pets": ["Oh how sweet! Tell me all about them.", "I bet they're adorable. What are they like?", "Lucky you! What's their personality like?"],
    "feelings": ["I'm here to listen. Take your time.", "Thank you for opening up. What's going on?", "I appreciate you sharing. Tell me more."],
}

SHORT_YES = ["yes", "yeah", "yep", "sure", "i do", "i did", "of course", "definitely", "absolutely", "uh huh", "mhm"]
SHORT_NO = ["no", "nah", "nope", "not really", "i don't", "i didn't", "never"]

NO_CONTINUATIONS = [
    "That's okay! Is there something else you'd like to talk about?",
    "No worries at all. What's on your mind instead?",
    "That's fine! We can chat about anything you like.",
]

CONVERSATION_STARTERS = {
    "morning": ["Good morning! Did you sleep well?", "Rise and shine! How are you feeling today?", "Morning! Any plans for today?"],
    "afternoon": ["How's your afternoon going so far?", "Having a good day? Tell me about it.", "Afternoon! Have you had lunch yet?"],
    "evening": ["How was your day today?", "Winding down for the evening? How are you feeling?", "Good evening! What was the best part of your day?"],
}

MOOD_ACTIVITIES = {
    "joy": ["Would you like to hear a joke?", "Want to listen to some music?", "How about a fun story?"],
    "sadness": ["Would a calming meditation help?", "Want me to read you a story?", "How about some gentle music?"],
    "anger": ["Let's try some deep breathing together.", "Want to take a moment to relax?", "How about a calming exercise?"],
    "fear": ["You're safe here. Want to do some breathing?", "I'm right here with you. Want to talk?", "How about we do something calming together?"],
    "neutral": ["Want to hear a joke?", "How about a story?", "Want to chat about something fun?"],
}


def handle_short_reply(text: str) -> str:
    """Handle short yes/no replies using context from the last topic discussed."""
    lower = text.strip().lower().rstrip("!.,?")
    if any(y == lower for y in SHORT_YES):
        continuations = YES_CONTINUATIONS.get(_last_topic, [])
        if continuations:
            return random.choice(continuations)
    if any(n == lower for n in SHORT_NO):
        return random.choice(NO_CONTINUATIONS)
    return ""


def get_follow_up(text: str) -> str:
    """Find a relevant follow-up question based on what the patient said."""
    global _last_topic
    lower = text.lower()
    for name, category in FOLLOW_UPS.items():
        for trigger in category["triggers"]:
            if trigger in lower:
                _last_topic = name
                available = [q for q in category["questions"] if q not in _recent_questions]
                if not available:
                    available = category["questions"]
                question = random.choice(available)
                _recent_questions.append(question)
                if len(_recent_questions) > 10:
                    _recent_questions.pop(0)
                return question
    return ""


def get_topic(text: str) -> str:
    """Detect which topic the patient is talking about."""
    lower = text.lower()
    for name, category in FOLLOW_UPS.items():
        for trigger in category["triggers"]:
            if trigger in lower:
                return name
    return "general"


def get_empathetic_follow_up(text: str) -> str:
    topic = get_topic(text)
    question = get_follow_up(text)
    if not question:
        return ""
    acks = ACKNOWLEDGMENTS.get(topic, [])
    if acks:
        return f"{random.choice(acks)} {question}"
    return question


def get_conversation_starter() -> str:
    """Get a time-appropriate conversation starter."""
    from datetime import datetime
    hour = datetime.now().hour
    if hour < 12:
        time_of_day = "morning"
    elif hour < 17:
        time_of_day = "afternoon"
    else:
        time_of_day = "evening"
    return random.choice(CONVERSATION_STARTERS[time_of_day])


_topic_counts = {}

def track_topic(text: str) -> None:
    """Track how often each topic comes up."""
    topic = get_topic(text)
    if topic == "general":
        return
    _topic_counts[topic] = _topic_counts.get(topic, 0) + 1


def get_favorite_topic() -> str:
    """Return the topic the patient talks about most."""
    if not _topic_counts:
        return "I haven't learned your favorite topics yet."
    favorite = max(_topic_counts, key=_topic_counts.get)
    count = _topic_counts[favorite]
    return f"You seem to really enjoy talking about {favorite}! We've chatted about it {count} times."


def suggest_activity(mood: str) -> str:
    """Suggest an activity based on the patient's mood."""
    activities = MOOD_ACTIVITIES.get(mood, MOOD_ACTIVITIES["neutral"])
    return random.choice(activities)


def personalized_greeting(name: str = None) -> str:
    """Generate a personalized greeting based on time and name."""
    from datetime import datetime
    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"
    if name:
        return f"{greeting}, {name}! How are you today?"
    return f"{greeting}! How are you today?"


# ── Conversation streak tracking ──────────────────────────────────

_conversation_dates = []

def log_conversation_date() -> None:
    """Log that a conversation happened today."""
    from datetime import date
    today = date.today()
    if today not in _conversation_dates:
        _conversation_dates.append(today)
    if _supabase:
        _db.save_streak_date("default")


def get_streak() -> int:
    """Calculate how many consecutive days the patient has talked."""
    if not _conversation_dates:
        return 0
    from datetime import date, timedelta
    sorted_dates = sorted(_conversation_dates, reverse=True)
    streak = 1
    for i in range(len(sorted_dates) - 1):
        diff = sorted_dates[i] - sorted_dates[i + 1]
        if diff == timedelta(days=1):
            streak += 1
        else:
            break
    return streak


def get_streak_message() -> str:
    """Return a message about the patient's conversation streak."""
    streak = get_streak()
    if streak >= 7:
        return f"Wow! You've talked to me {streak} days in a row! That's amazing!"
    elif streak >= 3:
        return f"Nice! We've chatted {streak} days in a row. Keep it up!"
    elif streak == 1:
        return "Great to talk to you today!"
    else:
        return "I've missed you! Let's chat more often."


# ── Conversation summary ──────────────────────────────────────────

_conversation_log = []

def log_conversation(text: str) -> None:
    """Log what the patient said and what topic it was about."""
    topic = get_topic(text)
    _conversation_log.append((topic, text))
    if _supabase:
        _db.save_conversation(topic, text)


def get_conversation_summary() -> str:
    """Give a summary of what topics were discussed."""
    if not _conversation_log:
        return "We haven't chatted much yet today!"
    topic_counts = {}
    for topic, text in _conversation_log:
        if topic == "general":
            continue
        topic_counts[topic] = topic_counts.get(topic, 0) + 1
    if not topic_counts:
        return "We've been having a nice general chat today!"
    parts = []
    for topic, count in topic_counts.items():
        parts.append(f"{topic} ({count} times)")
    summary = ", ".join(parts)
    return f"Today we talked about: {summary}. It's been a great conversation!"


# ── Mood redirect ─────────────────────────────────────────────────

_mood_log = []

def log_mood(mood: str) -> None:
    """Track the patient's recent moods."""
    _mood_log.append(mood)
    if len(_mood_log) > 5:
        _mood_log.pop(0)
    if _supabase:
        hour = datetime.datetime.now().hour
        day = datetime.datetime.now().strftime("%A")
        _db.save_mood(mood, hour, day)


def is_stuck_negative() -> bool:
    """Check if the patient has been negative for 3+ turns in a row."""
    if len(_mood_log) < 3:
        return False
    negative_moods = ["sadness", "anger", "fear"]
    recent = _mood_log[-3:]
    return all(m in negative_moods for m in recent)

REDIRECTS = [
    "You know what might be nice? Tell me about something that made you smile this week.",
    "Hey, let's switch gears for a moment. What's something you're looking forward to?",
    "I care about you. How about we think of something fun? What's your favorite memory?",
    "Let's take a little break from the heavy stuff. Want to hear a joke or listen to some music?",
]

def get_mood_redirect() -> str:
    """If the patient is stuck negative, suggest a gentle redirect."""
    if is_stuck_negative():
        return random.choice(REDIRECTS)
    return ""


# ── Conversation memory ───────────────────────────────────────────

_patient_mentions = {}

MENTION_PATTERNS = {
    "people": ["my daughter", "my son", "my wife", "my husband", "my friend",
               "my brother", "my sister", "my neighbor", "my mother", "my father",
               "my mom", "my dad", "my grandma", "my grandmother", "my grandpa",
               "my grandfather", "my grandson", "my granddaughter", "my grandchild",
               "my aunt", "my uncle", "my cousin", "my niece", "my nephew",
               "my partner", "my boyfriend", "my girlfriend", "my fiancé",
               "my caregiver", "my nurse", "my doctor",
               "a daughter", "a son", "a wife", "a husband", "a friend",
               "a brother", "a sister", "have a son", "have a daughter",
               "have a brother", "have a sister", "have a friend",
               "son named", "daughter named", "wife named", "husband named",
               "friend named", "brother named", "sister named"],
    "places": ["the park", "the store", "the hospital", "the church", "the garden",
               "my house", "the library", "the beach", "the lake", "the mall",
               "the school", "the restaurant", "the cafe", "the market",
               "the pharmacy", "the gym", "the pool", "the museum",
               "my apartment", "my room", "my neighborhood", "my town",
               "my city", "back home", "grew up in", "live in", "lived in",
               "moved to", "visited"],
    "activities": ["cooking", "reading", "walking", "gardening", "painting",
                   "knitting", "watching tv", "playing cards", "fishing",
                   "baking", "sewing", "singing", "dancing", "writing",
                   "drawing", "puzzles", "crossword", "bird watching",
                   "playing piano", "playing guitar", "swimming", "hiking",
                   "photography", "woodworking", "volunteering", "chess",
                   "listening to music", "watching movies", "yoga",
                   "i love to", "i like to", "i enjoy", "i used to"],
    "pets": ["my dog", "my cat", "my bird", "my pet", "my rabbit",
             "my fish", "my parrot", "a dog", "a cat", "have a dog",
             "have a cat", "have a pet", "pet named", "dog named", "cat named"],
    "food": ["favorite food", "favorite meal", "love to eat", "love eating",
             "favorite recipe", "best dish", "comfort food", "love cooking",
             "favorite restaurant"],
    "health": ["my medication", "my medicine", "my pills", "my doctor",
               "my therapy", "my surgery", "my diagnosis", "my condition",
               "i have diabetes", "i have arthritis", "blood pressure",
               "heart condition", "back pain", "knee pain"],
}

def remember_mention(text: str) -> None:
    """Scan what the patient said and remember key mentions."""
    lower = text.lower()
    for category, patterns in MENTION_PATTERNS.items():
        for pattern in patterns:
            if pattern in lower:
                if category not in _patient_mentions:
                    _patient_mentions[category] = []
                if pattern not in _patient_mentions[category]:
                    _patient_mentions[category].append(pattern)
                    if _supabase:
                        _db.save_mention(category, pattern)


def smart_extract_mentions(text: str) -> None:
    """Use the LLM to extract entities that pattern matching might miss.
    Call this from the interaction loop after the brain responds."""
    try:
        from openai import OpenAI
        import json as _json
        client = OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "Extract personal entities from what an elderly patient said. "
                    "Return JSON with these keys (use empty lists if none found): "
                    "people (names or relationships like 'my son', 'Sarah'), "
                    "places (locations mentioned), "
                    "activities (hobbies or things they do), "
                    "pets (animals they have), "
                    "food (foods or meals they mention), "
                    "health (conditions, medications, symptoms). "
                    "Only extract what's clearly stated. Keep values short."
                )},
                {"role": "user", "content": text},
            ],
            max_tokens=200,
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
        extracted = _json.loads(raw)
        for category, items in extracted.items():
            if not isinstance(items, list):
                continue
            for item in items:
                item = str(item).lower().strip()
                if not item or len(item) < 2:
                    continue
                if category not in _patient_mentions:
                    _patient_mentions[category] = []
                if item not in _patient_mentions[category]:
                    _patient_mentions[category].append(item)
                    if _supabase:
                        _db.save_mention(category, item)
    except Exception as e:
        # Silently fail — this is a nice-to-have, not critical
        logger.debug("Smart extract skipped: %s", e)


def recall_memory() -> str:
    """Bring up something the patient mentioned before."""
    if not _patient_mentions:
        return ""
    filled = [cat for cat in _patient_mentions if len(_patient_mentions[cat]) > 0]
    if not filled:
        return ""
    category = random.choice(filled)
    mention = random.choice(_patient_mentions[category])
    responses = {
        "people": f"You mentioned {mention} earlier. How are they doing?",
        "places": f"You talked about {mention} before. Do you go there often?",
        "activities": f"I remember you mentioned {mention}. Do you still enjoy that?",
    }
    return responses.get(category, "")


def load_from_supabase() -> None:
    """Load past data from Supabase into memory so Reachy remembers."""
    if not _supabase:
        return

    # Load mentions
    saved_mentions = _db.get_mentions()
    for category, items in saved_mentions.items():
        _patient_mentions[category] = items

    # Load recent moods into _mood_log
    saved_moods = _db.get_moods(limit=5)
    for entry in saved_moods:
        _mood_log.append(entry["mood"])

    # Load streak
    streak = _db.get_streak()

    loaded = len(_patient_mentions) + len(_mood_log)
    if loaded > 0:
        logger.info("Loaded %d items from Supabase (streak: %d days)", loaded, streak)


def get_daily_insight() -> str:
    """Generate a personalized insight from Supabase history."""
    if not _supabase:
        return ""

    moods = _db.get_moods(limit=20)
    if len(moods) < 3:
        return ""

    # Count positive vs negative moods
    positive = sum(1 for m in moods if m["mood"] in ("joy", "neutral"))
    negative = sum(1 for m in moods if m["mood"] in ("sadness", "anger", "fear"))

    # Check streak
    streak = _db.get_streak()

    # Check mentions for personalization
    mentions = _db.get_mentions()
    people = mentions.get("people", [])

    parts = []

    if streak >= 3:
        parts.append(f"We've chatted {streak} days in a row!")

    if positive > negative * 2:
        parts.append("You've been in really good spirits lately.")
    elif negative > positive:
        parts.append("It's been a bit of a tough stretch. I'm here for you.")

    if people:
        person = random.choice(people)
        parts.append(f"By the way, you mentioned {person} before — how are they?")

    if parts:
        return " ".join(parts)
    return ""


class MoodJournal:
    """Tracks mood over time and finds patterns."""

    def __init__(self):
        self._entries = []

    def record(self, mood: str) -> None:
        hour = datetime.datetime.now().hour
        day = datetime.datetime.now().strftime("%A")
        self._entries.append({"mood": mood, "hour": hour, "day": day})
        if _supabase:
            _db.save_mood(mood, hour, day)
    
    def get_time_pattern(self) -> str:
        """Find which time of day the patient tends to be happiest."""
        if len(self._entries) < 3:
            return "I need a few more conversations to spot patterns."

        # Group moods by time of day
        time_moods = {"morning": [], "afternoon": [], "evening": []}
        for entry in self._entries:
            hour = entry["hour"]
            if hour < 12:
                time_moods["morning"].append(entry["mood"])
            elif hour < 17:
                time_moods["afternoon"].append(entry["mood"])
            else:
                time_moods["evening"].append(entry["mood"])

        # Count joy per time period
        best_time = None
        best_joy = 0
        for period, moods in time_moods.items():
            if not moods:
                continue
            joy_count = sum(1 for m in moods if m == "joy")
            if joy_count > best_joy:
                best_joy = joy_count
                best_time = period

        if best_time and best_joy > 0:
            return f"I've noticed you tend to be happiest in the {best_time}!"
        return "I'm still learning your patterns. Let's keep chatting!"

    def get_day_pattern(self) -> str:
        """Find which day of the week tends to be toughest."""
        if len(self._entries) < 5:
            return "I need more data to spot weekly patterns."

        day_moods = {}
        for entry in self._entries:
            day = entry["day"]
            if day not in day_moods:
                day_moods[day] = []
            day_moods[day].append(entry["mood"])

        # Find the day with the most sadness
        worst_day = None
        worst_count = 0
        for day, moods in day_moods.items():
            sad_count = sum(1 for m in moods if m in ("sadness", "fear", "anger"))
            if sad_count > worst_count:
                worst_count = sad_count
                worst_day = day

        if worst_day and worst_count > 1:
            return f"{worst_day}s seem a bit tough for you. I'll make sure to check in extra on those days."
        return "Your mood seems pretty steady across the week. That's great!"

    def get_summary(self) -> str:
        """Get an overall mood summary."""
        if not self._entries:
            return "We haven't tracked any moods yet."
        mood_counts = {}
        for entry in self._entries:
            mood = entry["mood"]
            mood_counts[mood] = mood_counts.get(mood, 0) + 1
        dominant = max(mood_counts, key=mood_counts.get)
        total = len(self._entries)
        return f"Over {total} check-ins, your most common mood has been {dominant}. {self.get_time_pattern()}"

