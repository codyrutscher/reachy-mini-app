# Reachy Bot — New Features Spec

Work through these one at a time. Each one teaches a specific Python skill.
Difficulty: 🟢 easy | 🟡 medium | 🔴 hard

---

## 🟦 Caregiver Integration (4 tasks)

- [ ] 1. 🟢 **Caregiver Message Polling** — Reachy checks the dashboard for pending messages and speaks them aloud. The endpoint `/api/messages/pending` already exists but the realtime module never polls it. Add a background thread that checks every 30 seconds and queues messages to speak. (Python — threading, urllib)
  - File: `realtime_conversation.py`
  - Skills: background threads, HTTP requests, JSON parsing

- [ ] 2. 🟡 **Live Mood Streaming to Dashboard** — After each conversation turn, POST the current mood to the dashboard's `/api/status` endpoint so the caregiver sees mood changes in real-time without refreshing. (Python — HTTP POST)
  - File: `realtime_conversation.py`
  - Skills: HTTP POST, JSON, background tasks

- [ ] 3. 🟡 **Caregiver Alert Escalation** — If the patient triggers 3+ alerts in one session (medication requests, help requests, distress), automatically escalate by sending a high-priority "SUSTAINED_DISTRESS" alert to the dashboard. (Python — counter logic, alert thresholds)
  - File: `realtime_conversation.py`
  - Skills: state tracking, conditional logic, API calls

- [ ] 4. 🔴 **Two-Way Dashboard Chat** — Caregiver types a message in the dashboard, Reachy speaks it. Patient responds, caregiver sees the response in real-time via SSE. Full bidirectional communication loop. (Python + JS)
  - Files: `realtime_conversation.py`, `caregiver-dashboard/templates/dashboard.html`
  - Skills: polling, SSE, real-time sync

---

## 🟦 New Activities (6 tasks)

- [ ] 5. 🟢 **Gratitude Practice** — Structured "3 things you're grateful for today" session. Reachy asks 3 times, saves each answer to Supabase as a fact, then gives a warm summary. (Python — new module)
  - File: new `gratitude.py`
  - Skills: session state, Supabase writes, string formatting

- [ ] 6. 🟢 **Daily Affirmation with Context** — Instead of random affirmations, pick one based on the patient's recent mood from Supabase. Sad mood → comforting affirmation. Happy mood → celebratory one. (Python — conditional logic)
  - File: `affirmations.py`
  - Skills: Supabase reads, conditional selection

- [ ] 7. 🟡 **Personalized Daily Quiz** — Generate quiz questions from `bot_patient_facts`. "You told me your daughter's name is Sarah — what city does she live in?" Tests and exercises their memory using their own life. (Python — fact retrieval, question generation)
  - File: new `personal_quiz.py`
  - Skills: database reads, template strings, session management

- [ ] 8. 🟡 **Sing-Along Mode** — Reachy plays a melody and speaks the lyrics line by line with pauses so the patient can sing along. Start with 3-4 classic songs with hardcoded lyrics. (Python — timing, audio)
  - File: new `singalong.py`
  - Skills: timed output, audio playback, session flow

- [ ] 9. 🟡 **Photo Description** — Patient holds up a photo to the camera, says "what do you see", Reachy captures a frame and sends it to GPT-4o vision for description. Great for reminiscence. (Python — camera capture, OpenAI vision API)
  - File: new `vision.py`
  - Skills: camera API, base64 encoding, OpenAI vision, async

- [ ] 10. 🔴 **Interactive Storytelling** — Instead of reading pre-written stories, Reachy and GPT co-create a story with the patient as the main character. Uses their name and known facts. Saves the story to Supabase when done. (Python — LLM prompting, session state)
  - File: new `interactive_story.py`
  - Skills: LLM streaming, context injection, Supabase persistence

---

## 🟦 Safety & Health (5 tasks)

- [ ] 11. 🟢 **Medication Schedule Checker** — At medication times (from `bot_reminders`), Reachy proactively asks "Did you take your 2pm medication?" instead of waiting for the patient to mention it. (Python — time checking, Supabase reads)
  - File: `realtime_conversation.py` or `autonomy.py`
  - Skills: datetime comparison, Supabase queries, proactive messaging

- [ ] 12. 🟡 **Sundowning Detection** — Track if confusion/agitation keywords spike in the evening hours (after 4pm). If detected, switch to calmer conversation style and alert caregiver. (Python — time-based pattern detection)
  - File: new `sundowning.py`
  - Skills: time awareness, keyword tracking, behavioral adaptation

- [ ] 13. 🟡 **Wandering/Confusion Alerts** — Detect when patient says things like "where am I", "I want to go home", "I don't know this place" and alert the caregiver immediately. Different from general confusion — specifically spatial disorientation. (Python — keyword detection, alerts)
  - File: `realtime_conversation.py`
  - Skills: pattern matching, alert escalation

- [ ] 14. 🟡 **Pain Tracking** — When patient mentions pain, ask follow-up questions (where, how bad 1-10, when did it start). Save structured pain reports to Supabase. Caregivers see pain trends over time. (Python — structured data collection)
  - File: new `pain_tracker.py` + Supabase table
  - Skills: multi-step data collection, Supabase schema, structured logging

- [ ] 15. 🔴 **Behavioral Baseline & Anomaly Detection** — Build a baseline of normal conversation patterns (avg words per turn, response time, topic variety, mood distribution). Alert caregiver when today deviates significantly from the baseline. (Python — statistics, pattern analysis)
  - File: new `anomaly_detection.py`
  - Skills: statistical analysis, Supabase aggregation, threshold alerting

---

## 🟦 Conversation Intelligence (5 tasks)

- [ ] 16. 🟢 **Conversation Topic Suggestions** — When conversation stalls (short replies, long pauses), suggest a topic based on what the patient enjoys. Pull favorite topics from `bot_conversation_log` topic counts. (Python — Supabase query, conditional logic)
  - File: `realtime_conversation.py`
  - Skills: database aggregation, fallback behavior

- [ ] 17. 🟡 **"Remember When" Callbacks** — Periodically reference past conversations naturally. "Last Tuesday you told me about your garden — did you plant those tomatoes?" Pull from `bot_conversation_log` and `bot_patient_facts`. (Python — temporal memory, context injection)
  - File: `realtime_conversation.py`
  - Skills: date-based queries, natural language injection

- [ ] 18. 🟡 **Emotion-Adaptive Music** — When sustained sadness is detected (3+ sad turns), automatically offer to play calming music. When joy is detected, offer upbeat music. Integrates mood tracking with the music player. (Python — mood monitoring, music triggers)
  - File: `realtime_conversation.py`
  - Skills: state monitoring, cross-module integration

- [ ] 19. 🟡 **Conversation Pacing** — Detect when the patient is giving very short answers (1-3 words) and adapt: ask simpler yes/no questions, offer activities, or just be quietly present. Detect when they're chatty and ask deeper follow-ups. (Python — response length analysis)
  - File: `realtime_conversation.py`
  - Skills: text analysis, adaptive behavior

- [ ] 20. 🔴 **Multi-Session Story Arc** — Track ongoing "storylines" across sessions. If the patient was talking about their daughter's wedding last time, bring it up naturally next session. Uses knowledge graph relations. (Python — knowledge graph queries, session continuity)
  - File: `realtime_conversation.py` + `knowledge_graph.py`
  - Skills: graph traversal, temporal context, LLM prompting

---

**Total: 20 features**
- 🟢 Easy: 5
- 🟡 Medium: 10
- 🔴 Hard: 5

Pick a number and we'll build it together!
