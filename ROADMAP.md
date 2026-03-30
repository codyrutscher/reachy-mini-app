# Reachy Care — Roadmap

What we want to build next, organized by category.
Check off items as we complete them.

---

## 🔧 Technical Improvements

### 1. Logging & Observability
- [x] Add structured JSON logging across all modules (replace print statements)
- [x] Add request/response logging middleware to the dashboard (timing, status codes, IP)
- [x] Add request/response logging to the robot webapp API
- [x] Create a `/api/logs` endpoint to view recent logs from the dashboard
- [x] Add a log viewer page in the dashboard (filterable by level, module, time)
- [x] Add health check endpoints with uptime, memory usage, and connection status
- [ ] Add error tracking — count errors per module, alert if spike detected
- [ ] Add conversation analytics logging — words per turn, response times, session duration

### 2. CI/CD Pipeline
- [x] Create a GitHub Actions workflow that runs all tests on push/PR
- [x] Add linting step (ruff) to the CI pipeline
- [x] Add type checking step (mypy) to the CI pipeline
- [x] Add test coverage reporting (pytest-cov) with minimum threshold
- [x] Add Docker build step to verify the container builds cleanly
- [ ] Add auto-deploy to Railway on merge to main
- [x] Add a badge to README showing build status

### 3. Type Hints
- [x] Add type hints to `config.py` (easiest — mostly constants)
- [x] Add type hints to `validators.py`
- [x] Add type hints to `db.py` (all function signatures + return types)
- [x] Add type hints to `webapp.py`
- [x] Add type hints to `robot.py` and `movements.py`
- [ ] Add type hints to `realtime_conversation.py`
- [ ] Add type hints to `brain.py`
- [ ] Add type hints to `app.py` (dashboard)
- [ ] Add a `py.typed` marker and run mypy in CI

---

## 🎵 Radio DJ Mode

Reachy becomes a personal radio DJ — plays music, takes requests, and fills gaps with
commentary, fun facts, and dedications. Uses the existing `music.py` module as a base.

- [x] Build `radio.py` module — manages a playlist queue, shuffle, and playback state
- [x] Add voice commands: "play music", "next song", "play something happy", "stop music"
- [x] Add genre/mood-based playlists (calm, upbeat, nostalgic, classical, oldies)
- [x] Add DJ commentary between songs — "That was Frank Sinatra! Up next, something to get your toes tapping..."
- [x] Add song request handling — "play me some Elvis" triggers a search
- [x] Add time-of-day awareness — calm music in the evening, upbeat in the morning
- [x] Add mood-reactive playlist switching — if patient is sad, gradually shift to uplifting songs
- [x] Add a "dedications" feature — "This next one is for you, Margaret, because you told me you love dancing"
- [x] Add a dashboard page to manage playlists and see what's playing
- [x] Add Spotify/YouTube Music API integration for real song playback (stretch goal)

---

## 🗣️ Voice Cloning

Let Reachy speak in a familiar voice — a family member, a favorite actor, or a comforting
voice the patient already trusts. Reduces the "talking to a machine" feeling.

- [x] Research and integrate a voice cloning API (ElevenLabs, Coqui TTS, or OpenAI TTS)
- [x] Build `voice_clone.py` module — manages voice profiles (upload sample, generate speech)
- [x] Add a dashboard page for family to upload a 30-second voice sample
- [x] Add voice profile selection per patient in settings
- [x] Add fallback to default TTS if cloned voice fails
- [x] Add voice preview — family can hear what it sounds like before enabling
- [x] Add safety guardrails — only approved family members can upload voices
- [x] Store voice profiles in Supabase storage (or local filesystem)

---

## 🎨 Creative Reachy Features

### Photo Album Narrator
Reachy looks at photos through the camera and tells stories about what it sees.
Combined with patient facts, it can say things like "Is that your daughter Sarah?
She looks so happy in this one!"

- [x] Build `photo_album.py` — captures frame, sends to GPT-4o vision, narrates
- [x] Cross-reference descriptions with known patient facts for personalized commentary
- [x] Add a "show me a photo" voice command
- [x] Save narrated photos to the memory book on the dashboard
- [x] Add slideshow mode — patient holds up photos one by one, Reachy narrates each

### Emotion-Reactive Movements
Reachy's body language matches the conversation mood in real-time, not just at
expression triggers. Subtle continuous movement that makes Reachy feel alive.

- [x] Add ambient movement system — Reachy subtly moves while listening (breathing, small tilts)
- [x] Map conversation sentiment to continuous pose adjustments (lean in when interested, droop when sad)
- [x] Add mirroring — if patient laughs, Reachy does a little happy wiggle automatically
- [x] Add "thinking" animation while GPT is generating a response
- [x] Add attention tracking — Reachy looks toward the patient using camera face detection

### Daily Routine Coach
Reachy gently guides the patient through their day — morning routine, meals,
activities, medications, bedtime. Adapts based on how the patient is feeling.

- [x] Build `routine_coach.py` — time-based activity suggestions
- [x] Integrate with existing reminders and medication systems
- [x] Add adaptive pacing — if patient is tired, suggest rest instead of activity
- [x] Add progress tracking — "You've done 3 of your 5 daily activities, great job!"
- [x] Add caregiver-configurable routines from the dashboard

### Video Call Assistant
Help the patient connect with family through video calls. Reachy facilitates
the call, helps if the patient gets confused, and summarizes the call afterward.

- [ ] Build WebRTC video call system through the dashboard
- [x] Add voice command: "call my daughter" → looks up contact, initiates call
- [x] Add call facilitation — Reachy reminds patient who they're talking to if confused
- [x] Add post-call summary saved to the dashboard
- [x] Add scheduled call reminders — "Your son usually calls on Sundays"

### Collaborative Drawing Prompts
Reachy suggests drawing prompts and encourages the patient. Good for
fine motor skills and creative expression.

- [x] Build `drawing.py` — themed drawing prompts (nature, family, seasons, memories)
- [x] Add encouragement responses while patient draws
- [x] Add camera capture of finished drawings saved to memory book
- [x] Add "art gallery" section on the dashboard showing captured drawings

### Adaptive Trivia Game
Trivia that adjusts difficulty based on how the patient is doing. Uses their
interests and life history to make questions personal and engaging.

- [x] Enhance existing `cognitive.py` with adaptive difficulty scaling
- [x] Add personalized questions from patient facts ("What year were you married?")
- [x] Add category selection — history, music, nature, sports, personal
- [x] Add streak tracking and gentle encouragement
- [ ] Add multiplayer mode — two patients or patient + family member

### Gait & Movement Analysis
Use the camera to detect changes in how the patient moves. Early warning
for fall risk or mobility decline.

- [x] Build `gait_analysis.py` — uses camera + pose estimation (MediaPipe)
- [x] Track walking speed, steadiness, and posture over time
- [x] Alert caregiver if significant changes detected
- [x] Add a mobility trends chart on the dashboard
- [x] Integrate with fall detection system already in place

### Speech Pattern Analysis
Track changes in speech patterns over time — word finding difficulty,
repetition, vocabulary shrinkage. Early indicators of cognitive decline.

- [x] Build `speech_analysis.py` — analyzes transcripts for linguistic markers
- [x] Track vocabulary diversity, sentence complexity, word-finding pauses
- [x] Compare weekly baselines and flag significant changes
- [x] Add speech health trends to the doctor report
- [x] Integrate with existing anomaly detection system

### Hydration & Nutrition Companion
Reachy reminds the patient to drink water and eat meals. Tracks intake
through conversation ("I just had lunch" → logs it).

- [x] Build `nutrition.py` — meal and hydration tracking through conversation
- [x] Add proactive reminders based on time of day
- [x] Add intake logging to Supabase
- [x] Add nutrition dashboard widget showing daily intake
- [x] Add caregiver alerts if patient hasn't eaten/drunk in X hours

### Night Companion Mode
Special low-stimulation mode for nighttime. Reachy speaks softly, offers
sleep stories, plays white noise, and monitors for distress.

- [x] Build `night_mode.py` — activates automatically after bedtime
- [x] Add sleep stories (gentle narration to help fall asleep)
- [x] Add white noise / ambient sound playback
- [x] Add nighttime distress detection (calling out, confusion)
- [x] Add sleep quality logging based on nighttime interactions
- [x] Integrate with existing sleep tracker

---

## ✅ Already Completed

For reference — things we've already built:

- [x] Unit tests (334 tests passing)
- [x] Supabase RLS policies (migration 001)
- [x] Dashboard API tests
- [x] Input validation on all POST endpoints
- [x] Database migrations (002 — teleop, robot events, care plans, incidents)
- [x] Role-based navbar with seed users
- [x] Teleoperation system (webapp + dashboard UI + Xbox controller)
- [x] MuJoCo simulation testing
- [x] Memory book page

---

## 🎮 Interactive Entertainment

- [x] Play Chess — set up a chessboard in front of the camera; Reachy recognizes the board state, comments on openings, and verbally states its next move
- [x] Freestyle Rapper — generate and perform freestyle raps about specific topics, with antennas acting as instruments to change beat or tone
- [x] Dance & Emote — queue up complex dance routines where Reachy bobs its head, waves antennas, and rotates body in sync with music
- [ ] Radio Controller — use the right antenna as a physical tuner to browse and listen to different radio stations

---

## 🤖 AI-Powered Assistance

- [x] Vision-Aware Buddy — ask Reachy what it sees; identify objects, read text on signs, and describe what is happening in the room
- [x] Home Monitor — monitor a room, recognize unusual situations, and send update alerts to caregivers
- [x] Personal Translator — bridge language barriers with real-time translation between French, English, and Chinese
- [x] Hand Tracker — follow hand movements in real-time, making Reachy feel like a responsive digital pet

---

## 🎨 Creative Development

- [x] Custom Personalities — download different personality profiles from Hugging Face Hub or code your own using LLMs to change how Reachy speaks and reacts
- [x] Sketch-to-Render — take a hand-drawn sketch via camera and use AI models to generate a full rendering
- [ ] Physical Customization — 3D print and add accessories like costumes or custom-painted shells (hardware guide)

---

## 📚 Educational & Practical Apps

- [x] Metronome — turn Reachy ticking antennas into a visual and auditory metronome for music practice
- [x] Stargazing Buddy — companion for astronomical observation, identifying constellations and sharing facts
- [ ] Learn Robotics — DIY kit tutorials for physical assembly to advanced Python SDK programming and MuJoCo simulation

---

## 🧑‍💻 Coding Assistant

- [x] Build coding_assistant.py — voice-to-code via GPT, patient says what they want to build and Reachy generates code
- [x] Add a /code-pad dashboard page — live code display with syntax highlighting, copy button, and language selector
- [x] Add voice commands: "write a function that...", "help me code...", "explain this code"
- [x] Add code explanation mode — Reachy reads code aloud and explains it line by line
- [x] Wire into realtime_conversation.py for voice trigger handling
