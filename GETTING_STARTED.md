# Reachy Care — Getting Started

A quick guide to what this project does, what models it uses, and how to run it.

---

## What Is This?

Reachy Care is an AI companion built on the **Reachy Mini** robot. It talks to elderly and disabled patients through natural voice conversation, moves expressively, plays games, reads stories, plays music, tracks health, and keeps caregivers informed through a web dashboard.

The robot has a head that tilts/nods/turns, two antennas that wiggle, a camera, a speaker, and a microphone — all controlled by our code.

---

## Models & APIs Used

| Model | What It Does | Cost |
|---|---|---|
| **OpenAI Realtime API** (gpt-4o-realtime-preview) | Full-duplex voice conversation — listens and talks simultaneously | ~$0.30/min |
| **GPT-4o** | Vision tasks (object detection, room scanning, fall detection, art appreciation) | ~$0.01/image |
| **GPT-4o** | Brain fallback for text-mode conversation, code generation, story writing | ~$0.01/response |
| **Whisper** | Speech-to-text transcription (built into Realtime API) | Included |
| **ElevenLabs** (optional) | Voice cloning — Reachy speaks in a family member's voice | Separate API key |
| **MediaPipe** | Face detection, head pose estimation, hand tracking (runs locally, free) | Free |
| **Supabase PostgreSQL** | Cloud database for conversation history, mood tracking, patient facts | Free tier available |

---

## Features Summary

### Voice & Conversation
- Full-duplex voice through Reachy's built-in speaker and mic
- 22 conversational intelligence features: humor learning, emotional repair, engagement scoring, topic avoidance, name detection, celebration detection, mood shift detection, conversation pacing, energy tracking, and more
- Remembers patient across sessions (name, facts, preferences, favorite topics)
- Adapts personality based on mood, time of day, and conversation history
- Voice speed and volume control ("speak slower", "speak louder")

### Robot Body
- Expressive movements matching conversation mood (happy wiggle, sad droop, curious tilt)
- Head mirroring — Reachy copies your head movements in real-time
- Body awareness — patient can say "wiggle your antennas" or "do a dance"
- Custom move teaching — physically pose Reachy, it records and replays the move
- Sound direction tracking — turns toward whoever is speaking
- Bump detection — reacts when touched ("That tickles!")

### Games & Activities
- Emotion charades (Reachy acts, patient guesses)
- Sound guessing game (animal sounds, instruments, nature)
- Simon-style sound memory game
- Rhythm game (clap along to Reachy's beat)
- Reaction time game
- Adaptive trivia with personalized questions
- Interactive storytelling (patient makes choices)
- Sing-along mode
- Chess (camera-based board recognition)
- Freestyle rap mode

### Sound & Music
- 11 procedural sound effects (ding, buzzer, applause, drumroll, etc.)
- 7 ambient soundscapes (rain, ocean, birds, fireplace, wind, creek, night)
- 4 lullabies (Twinkle Twinkle, Brahms, Rock-a-bye, Moonlight)
- Musical instrument mode (antennas play notes)
- Radio DJ mode with playlists
- Doorbell detection
- Ambient noise monitoring (auto-adjusts volume)

### Camera Intelligence
- Object show-and-tell ("what am I holding?")
- Room scanning with narration
- Facial expression reading
- Clothing compliments
- Fall detection (alerts caregiver)
- Meal detection (logs to nutrition tracker)
- Pet detection
- Smile counting
- Distance awareness
- Light/brightness detection

### Health & Care
- Medication reminders
- Pain tracking
- Sleep quality logging
- Nutrition/hydration tracking
- Gait analysis
- Speech pattern analysis (cognitive decline indicators)
- Sundowning detection (evening confusion)
- Night companion mode (soft voice, sleep stories, distress detection)
- Daily routine coaching
- Anomaly detection (behavioral changes)

### Dashboard (Web UI)
- Live conversation view
- Mood charts and trends
- Session history with quality scores
- Conversation analytics (engagement, humor patterns, topic avoidance)
- Patient facts and weekly reports
- Caregiver notes and shift handoffs
- Medication tracking
- Teleoperation (control robot remotely)
- Radio control
- Settings and voice profile management

---

## Quick Start

### Prerequisites
- macOS (tested on Apple Silicon)
- Python 3.12
- Reachy Mini robot (connected via USB)
- OpenAI API key with credits ($10+ recommended)
- Supabase project (free tier works)

### 1. Set up environment

Copy `.env.example` files and fill in your keys:

```bash
# Robot bot
cp reachy-assist/.env.example reachy-assist/.env
# Edit reachy-assist/.env and add:
#   OPENAI_API_KEY=sk-...
#   SUPABASE_DB_URL=postgresql://...
#   WEATHER_CITY=Kansas City

# Dashboard
cp caregiver-dashboard/.env.example caregiver-dashboard/.env
# Edit caregiver-dashboard/.env and add:
#   SUPABASE_DB_URL=postgresql://...
```

### 2. Install dependencies

```bash
# Robot bot
cd reachy-assist
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Dashboard
cd ../caregiver-dashboard
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 3. Run it

Open three terminal windows:

**Terminal 1 — Robot daemon** (connects to hardware):
```bash
reachy-assist/.venv/bin/reachy-mini-daemon
```
Wait for "Daemon started successfully".

**Terminal 2 — Voice bot** (the AI brain):
```bash
reachy-assist/.venv/bin/python reachy-assist/run.py --realtime
```
Wait for "Conversation started — just talk!"

**Terminal 3 — Dashboard** (web UI):
```bash
caregiver-dashboard/.venv/bin/python caregiver-dashboard/app.py
```
Open http://localhost:5555 — login: `admin` / `admin`

### 4. Talk to Reachy

Just speak naturally. Try these:
- "How are you?"
- "Tell me a joke"
- "Play a guessing game"
- "Read me a story"
- "Wiggle your antennas"
- "Mirror me" (copies your head movements)
- "Play rain sounds"
- "Speak slower"

### 5. Stop everything

Press Ctrl+C in each terminal (bot first, then daemon).

---

## Running Without the Robot

If you don't have a Reachy Mini plugged in, the bot runs in simulation mode automatically. Skip Terminal 1 and just run:

```bash
reachy-assist/.venv/bin/python reachy-assist/run.py --realtime
```

Voice works through your computer's mic and speakers instead.

For text-only mode (cheapest, no audio costs):

```bash
reachy-assist/.venv/bin/python reachy-assist/run.py --brain openai --text
```

---

## Running Tests

```bash
reachy-assist/.venv/bin/python -m pytest reachy-assist/tests/ -q
```

416 tests, runs in ~6 seconds.

---

## Project Structure

```
reachy-assist/          # Robot AI brain (Python)
  run.py                # Entry point
  config.py             # System prompt, settings
  realtime_conversation.py  # Main conversation engine (5000+ lines)
  brain.py              # LLM conversation with memory
  robot.py              # Hardware control
  movements.py          # 40+ expressive movements
  sound_effects.py      # Sound engine (SFX, ambient, games, lullabies, instruments)
  camera_intelligence.py # Vision features (GPT-4o)
  webapp.py             # Robot API server (port 5557)
  db_supabase.py        # Database persistence
  tests/                # 416 unit tests
  sounds/               # Generated WAV files
  custom_moves/         # Patient-taught moves

caregiver-dashboard/    # Web dashboard (Flask)
  app.py                # Main server (port 5555)
  templates/            # 20 HTML pages
  db.py                 # SQLite database
  db_postgres.py        # Supabase database

tasks.md                # 100 planned features (52 done)
ROADMAP.md              # Feature roadmap
```
