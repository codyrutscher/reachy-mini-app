# Reachy Bot — Proposed Improvements

Everything below is based on reading the actual codebase. The bot already works great —
these are targeted upgrades to make it smarter, safer, and more useful for caregivers.

---

## 1. GPT Session Summary Saved to Supabase (visible on dashboard)

**What exists now:** `vector_memory.summarize_session()` generates a GPT summary at shutdown
and stores it as a vector embedding in `bot_memory_vectors`. But it's only used for semantic
search — caregivers never see it. The `bot_session_summaries` table only stores raw stats
(interaction count, dominant mood, topics list).

**The change:** Add a `summary_text` column to `bot_session_summaries`. At shutdown, call
`summarize_session()` and save the GPT narrative alongside the stats. Expose it via the
existing `/api/bot/sessions` endpoint. Update the history page to display it.

**Files:** `db_supabase.py`, `realtime_conversation.py`, `caregiver-dashboard/templates/history.html`

---

## 2. Caregiver Message Polling (BOT_FEATURES #1)

**What exists now:** The dashboard has `/api/messages/pending` but the bot never checks it.
Caregivers can write messages that go nowhere.

**The change:** Add a background thread in `RealtimeConversation` that polls every 30 seconds.
When a pending message is found, inject it into the conversation as a system message so Reachy
speaks it naturally to the patient.

**Files:** `realtime_conversation.py`

---

## 3. Context-Aware Affirmations (BOT_FEATURES #6)

**What exists now:** `affirmations.py` picks a random affirmation from a hardcoded list.
No awareness of the patient's current mood.

**The change:** Query the last few moods from `bot_mood_journal` via Supabase. If recent mood
is sad → pick from comforting affirmations. If happy → celebratory ones. If anxious → calming.
Falls back to random if no mood data.

**Files:** `affirmations.py`

---

## 4. Conversation Topic Suggestions When Stalling (BOT_FEATURES #16)

**What exists now:** If the patient gives short replies, nothing special happens. The bot
just keeps going with whatever GPT generates.

**The change:** Track response lengths in `_process_user_transcript`. After 3 consecutive
short replies (< 5 words), query `bot_conversation_log` for the patient's most-discussed
topics and inject a topic suggestion into the next system prompt. "You mentioned your garden
a lot — want to talk about that?"

**Files:** `realtime_conversation.py`

---

## 5. Medication Schedule Checker (BOT_FEATURES #11)

**What exists now:** `bot_reminders` table has medication reminders with times, but the bot
only checks reminders if the patient asks. No proactive medication prompts.

**The change:** In the autonomy loop or a new background thread, check `bot_reminders` where
`reminder_type='medication'` and compare against current time. If it's within 15 minutes of
a medication time, inject a gentle prompt: "It's about time for your 2pm medication — did you
take it?"

**Files:** `realtime_conversation.py` or `autonomy.py`, `db_supabase.py`

---

## 6. Wandering/Confusion Alerts (BOT_FEATURES #13)

**What exists now:** Crisis and emergency keywords are detected. But spatial disorientation
phrases like "where am I", "I want to go home", "I don't know this place" are not specifically
tracked.

**The change:** Add a `_WANDERING_KEYWORDS` list to `realtime_conversation.py`. When detected,
send a specific `WANDERING_ALERT` to the caregiver dashboard with severity "high". Different
from general confusion — this is a safety concern.

**Files:** `realtime_conversation.py`

---

## 7. Pain Tracking (BOT_FEATURES #14)

**What exists now:** No structured pain tracking. If a patient says "my back hurts", it might
get saved as a fact but there's no follow-up or structured data.

**The change:** New `pain_tracker.py` module. When pain keywords are detected, Reachy asks
follow-ups: where, severity (1-10), when it started. Saves structured pain reports to a new
`bot_pain_reports` table. Caregivers see pain trends on the dashboard.

**Files:** new `pain_tracker.py`, `db_supabase.py`, `realtime_conversation.py`

---

## 8. Emotion-Adaptive Music (BOT_FEATURES #18)

**What exists now:** `music.py` can play melodies. Mood is tracked per turn. But there's no
automatic connection — the patient has to ask for music.

**The change:** After 3+ consecutive sad turns, automatically offer calming music. After
sustained joy, offer upbeat music. Simple check in `_process_user_transcript` that calls
into the existing music module.

**Files:** `realtime_conversation.py`

---

## 9. "Remember When" Callbacks (BOT_FEATURES #17)

**What exists now:** Vector memory can recall similar past conversations, but it only fires
when the patient says something similar. No proactive "hey, remember last Tuesday?"

**The change:** Every 10 interactions, pull a random interesting fact or conversation from
`bot_conversation_log` (older than 2 days, emotion != neutral) and inject it as context:
"Last Tuesday you told me about your garden — did you plant those tomatoes?"

**Files:** `realtime_conversation.py`

---

## 10. Gratitude Practice (BOT_FEATURES #5)

**What exists now:** No gratitude module.

**The change:** New `gratitude.py` module. Reachy asks "What are 3 things you're grateful for
today?" one at a time. Saves each answer as a fact to Supabase. Gives a warm summary at the
end. Can be triggered by voice command or offered during evening sessions.

**Files:** new `gratitude.py`, `realtime_conversation.py` (to wire it up)

---

## Order of implementation

| # | Improvement | Difficulty | Impact |
|---|------------|-----------|--------|
| 1 | ✅ GPT Session Summary | 🟢 Easy | High — caregivers finally see what happened |
| 2 | ✅ Caregiver Message Polling | 🟢 Easy | High — connects dashboard to bot |
| 3 | ✅ Context-Aware Affirmations | 🟢 Easy | Medium — smarter emotional support |
| 4 | ✅ Topic Suggestions | 🟢 Easy | Medium — keeps conversations flowing |
| 5 | ✅ Medication Checker | 🟢 Easy | High — patient safety |
| 6 | ✅ Wandering Alerts | 🟢 Easy | High — patient safety |
| 7 | ✅ Pain Tracking | 🟡 Medium | High — structured health data |
| 8 | ✅ Emotion-Adaptive Music | 🟡 Medium | Medium — nice quality of life |
| 9 | ✅ Remember When Callbacks | 🟡 Medium | Medium — makes bot feel alive |
| 10 | ✅ Gratitude Practice | 🟡 Medium | Medium — new activity |
