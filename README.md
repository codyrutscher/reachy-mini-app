# Reachy Mini — Accessibility Assistant

[![CI](https://github.com/codyrutscher/reachy-mini-app/actions/workflows/ci.yml/badge.svg)](https://github.com/codyrutscher/reachy-mini-app/actions/workflows/ci.yml)

A comprehensive accessibility assistant built on the **Reachy Mini** robot platform, designed to support elderly and disabled individuals through voice interaction, emotional awareness, proactive care, and caregiver coordination.

---

## Quick Start

### Prerequisites

- macOS (required for `afplay` audio playback and `say` TTS fallback)
- Python 3.12+
- A microphone (built-in or USB)
- Speakers or headphones
- An OpenAI API key (for the brain, voice, and memory features)
- A Supabase account (free tier — for cloud database + vector memory)

### 1. Robot Setup (reachy-assist)

```bash
cd reachy-assist
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `reachy-assist/.env`:

```env
OPENAI_API_KEY=sk-proj-YOUR_KEY_HERE
SUPABASE_DB_URL=postgresql://postgres.YOURREF:YOURPASSWORD@aws-0-us-west-2.pooler.supabase.com:6543/postgres
REACHY_VOICE=nova
DASHBOARD_URL=http://localhost:5555
WEATHER_CITY=auto
```

Test in text mode first:
```bash
python run.py --text --brain openai
```

Run with voice (mic + speaker):
```bash
python run.py --brain openai
```

### 2. Dashboard Setup (caregiver-dashboard)

Open a second terminal:

```bash
cd caregiver-dashboard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `caregiver-dashboard/.env`:

```env
SUPABASE_DB_URL=postgresql://postgres.YOURREF:YOURPASSWORD@aws-0-us-west-2.pooler.supabase.com:6543/postgres
```

Start the dashboard:
```bash
python app.py
```

Open http://localhost:5555 — login: `admin` / `admin`

### 3. Connect Them

Run both at the same time in separate terminals:

| Terminal 1 (Dashboard) | Terminal 2 (Robot) |
|---|---|
| `cd caregiver-dashboard && source .venv/bin/activate && python app.py` | `cd reachy-assist && source .venv/bin/activate && python run.py --brain openai` |

The robot automatically connects to the dashboard at `http://localhost:5555`. Type a message in the dashboard chat → Reachy speaks it aloud. Talk to Reachy → conversation appears in the dashboard.

---

## Where to Get API Keys

| Variable | Where to find it |
|---|---|
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys → Create new secret key |
| `SUPABASE_DB_URL` | Supabase Dashboard → Project Settings → Database → Connection string → URI. Use the "Transaction" pooler (port 6543). URL-encode special characters in the password (e.g. `@` becomes `%40`). |

---

## Supabase Database Setup

Supabase gives you a free PostgreSQL database with vector search. This powers all the smart memory features.

### Create a project

1. Go to https://supabase.com and sign up (free)
2. Click "New Project", set a database password, pick a region
3. Wait ~1 minute for it to spin up

### Create the tables

Go to the SQL Editor in Supabase and run this:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS bot_conversation_log (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    speaker TEXT DEFAULT 'unknown', message TEXT NOT NULL,
    emotion TEXT DEFAULT 'neutral', created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_mood_log (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    mood TEXT NOT NULL, created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_mentions (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    category TEXT NOT NULL, mention TEXT NOT NULL, created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_topics (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    topic TEXT NOT NULL, created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_conversation_dates (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    date TEXT NOT NULL UNIQUE, created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_streaks (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    streak_date TEXT NOT NULL, created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_patient_facts (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    fact TEXT NOT NULL, created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_patient_profile (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default' UNIQUE,
    name TEXT, favorite_topic TEXT, personality_notes TEXT,
    updated_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_cognitive_scores (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    game TEXT NOT NULL, score INTEGER NOT NULL, total INTEGER,
    created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_exercise_log (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    exercise TEXT NOT NULL, duration_sec INTEGER, created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_sleep_log (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    event TEXT NOT NULL, created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_session_summaries (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    summary TEXT NOT NULL, mood TEXT, topics TEXT,
    interaction_count INTEGER, created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_weekly_reports (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    report TEXT NOT NULL, week_start TEXT, week_end TEXT,
    created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_reminders (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    reminder TEXT NOT NULL, time TEXT, active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_caregiver_alerts (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    alert_type TEXT NOT NULL, message TEXT NOT NULL,
    acknowledged BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_memory_vectors (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    content TEXT NOT NULL, embedding vector(1536),
    speaker TEXT DEFAULT 'patient', emotion TEXT DEFAULT 'neutral',
    emotion_weight REAL DEFAULT 1.0, topic TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_knowledge_entities (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    name TEXT NOT NULL, entity_type TEXT NOT NULL,
    attributes JSONB DEFAULT '{}', created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_knowledge_relations (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    subject TEXT NOT NULL, relation TEXT NOT NULL, object TEXT NOT NULL,
    confidence REAL DEFAULT 1.0, created_at TIMESTAMP DEFAULT NOW());

CREATE TABLE IF NOT EXISTS bot_temporal_patterns (
    id SERIAL PRIMARY KEY, patient_id TEXT DEFAULT 'default',
    pattern_type TEXT NOT NULL, description TEXT NOT NULL,
    severity TEXT DEFAULT 'info', data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW());

CREATE INDEX IF NOT EXISTS idx_memory_vectors_embedding
    ON bot_memory_vectors USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

After running, you should see 18 tables in the Table Editor. They fill up automatically as you talk to Reachy.

---

## CLI Reference

```bash
# Text mode (testing, no mic/speaker needed)
python run.py --text --brain openai

# Voice mode with OpenAI brain (recommended)
python run.py --brain openai

# Voice mode with local Ollama (no API key needed)
python run.py --brain ollama

# Voice mode, no brain (preset responses only)
python run.py

# Spanish language
python run.py --brain openai --language es

# Disabled patient profile
python run.py --brain openai --profile disabled

# Enable webcam facial emotion detection
python run.py --brain openai --face

# All flags
python run.py --brain openai --face --language en --profile elderly
```

| Flag | Options | Default |
|---|---|---|
| `--text` | (flag) | off (uses mic/speaker) |
| `--brain` | `openai`, `ollama`, `none` | `none` |
| `--emotion-backend` | `keywords`, `model` | `keywords` |
| `--face` | (flag) | off |
| `--language` | `en`, `es`, `fr`, `de`, `it`, `pt`, `zh`, `ja`, `ko` | `en` |
| `--profile` | `elderly`, `disabled` | `elderly` |

---

## Conversation Commands

| Say this | What happens |
|---|---|
| `help` | Lists all available commands |
| `play music` / `play [song]` | Music player |
| `tell me a joke` | Random joke |
| `let's play a game` | Cognitive games menu |
| `exercise` / `let's stretch` | Guided exercises |
| `meditate` / `breathing exercise` | Guided meditation |
| `tell me a story` | Story reader |
| `remind me to [X] at [time]` | Set a reminder |
| `check in` / `how am I doing` | Wellness check-in |
| `weather` | Weather briefing |
| `news` | News headlines |
| `journal` | Voice diary entry |
| `what day is it` | Date and time |
| `goodnight` | Bedtime routine |
| `I need help` / `emergency` | Triggers caregiver alert |
| `turn on the lights` | Smart home control |

---

## Project Structure

```
├── reachy-assist/              # Robot-side Python application
│   ├── run.py                  # Entry point (CLI flags)
│   ├── interaction.py          # Main interaction loop
│   ├── speech.py               # Whisper STT + OpenAI TTS
│   ├── brain.py                # LLM conversation with RAG memory
│   ├── emotion.py              # Text-based emotion detection
│   ├── face_emotion.py         # Webcam facial emotion (hsemotion)
│   ├── config.py               # Settings, prompts, thresholds
│   ├── profiles.py             # Elderly vs disabled patient profiles
│   ├── db_supabase.py          # Supabase database functions (18 tables)
│   ├── vector_memory.py        # pgvector embeddings + semantic search
│   ├── knowledge_graph.py      # GPT-powered entity/relationship extraction
│   ├── temporal_patterns.py    # Mood trends, topic changes, health detection
│   ├── followups.py            # Mention tracking + GPT smart extraction
│   ├── autonomy.py             # Proactive behavior engine
│   ├── robot.py                # Reachy Mini hardware control
│   ├── movements.py            # 22 robot movement patterns
│   ├── music.py                # Song library + melody/SFX player
│   ├── reminders.py            # Medication & appointment reminders
│   ├── checkin.py              # Daily wellness check-in
│   ├── caregiver.py            # Alert system → dashboard
│   ├── reminiscence.py         # Reminiscence therapy sessions
│   ├── cognitive.py            # Brain games (trivia, word games)
│   ├── exercises.py            # Guided physical exercises
│   ├── stories.py              # Story/audiobook reader
│   ├── meditation.py           # Guided meditation sessions
│   ├── companion.py            # Conversation topic starters
│   ├── sleep_tracker.py        # Bedtime/wake logging
│   ├── vitals.py               # Bluetooth vitals monitoring
│   ├── fall_detection.py       # MediaPipe pose-based fall detection
│   ├── smart_home.py           # Home Assistant integration
│   ├── camera_stream.py        # MJPEG camera server (port 5556)
│   ├── memory.py               # Local RAG memory (SQLite fallback)
│   ├── patient_model.py        # Cognitive/exercise/med trend tracking
│   ├── sounds/                 # 33 WAV files (melodies + SFX)
│   └── tests/                  # 149 unit tests
│
├── caregiver-dashboard/        # Flask web dashboard (PWA)
│   ├── app.py                  # Flask app with auth & REST API
│   ├── db.py                   # SQLite database layer
│   ├── db_postgres.py          # PostgreSQL/Supabase backend
│   ├── i18n.py                 # Multi-language translations (en/es/fr/de)
│   ├── static/                 # PWA manifest, service worker, icons
│   └── templates/              # 12 Jinja2 HTML pages
│       ├── _base.html          # Nav, SSE, global styles
│       ├── dashboard.html      # Main view: alerts, camera, chat
│       ├── patients.html       # Patient management
│       ├── medications.html    # Medication scheduling
│       ├── schedule.html       # Scheduled messages + timeline
│       ├── history.html        # Mood + vitals charts
│       ├── reports.html        # Analytics + generated reports
│       ├── activity.html       # Activity log with filters
│       ├── camera.html         # Full-screen camera view
│       ├── facilities.html     # Facility management
│       ├── family.html         # Family portal (send messages, see mood)
│       ├── settings.html       # Notifications, database, about
│       └── login.html          # Authentication
│
├── Dockerfile.dashboard        # Docker image for dashboard
├── docker-compose.yml          # Docker Compose deployment
├── nginx.conf                  # Nginx reverse proxy config
└── .github/workflows/ci.yml    # GitHub Actions CI (test + lint)
```

---

## Features

### Robot Assistant

**Voice & Conversation**
- OpenAI Whisper (small model) for speech-to-text with voice-activity detection
- OpenAI TTS (tts-1) for natural speech — configurable voice (nova, alloy, echo, fable, onyx, shimmer)
- GPT-4o-mini or Ollama (llama3.2) for natural conversation
- Emotion-adaptive responses — style changes based on detected mood
- 0.6s post-speech pause prevents mic echo pickup
- 2.5s silence timeout for natural conversation pacing

**Memory & Intelligence (Supabase)**
- Vector embeddings (pgvector, 1536-dim) — semantic search across all past conversations
- Emotion-weighted memory — sad/fearful moments rank higher in recall
- Knowledge graph — GPT extracts entities (people, places, things) and relationships
- Temporal pattern detection — mood trends, topic changes, health mention spikes, engagement drops
- Smart mention extraction — 100+ regex patterns + GPT-4o-mini fallback for entity capture
- Session summaries — GPT writes narrative notes at session end, stored as high-weight vectors
- Patient profile — name, favorite topics, personality notes, updated over time
- Conversation streaks — tracks consecutive days of interaction

**Proactive Autonomy Engine**
- Morning routine (7-9 AM): weather + affirmation + medication reminder
- Midday check-in (12-2 PM): activity suggestions, lunch/hydration
- Evening wind-down (8-10 PM): bedtime story/music, medication check
- Silence detection: gentle check after 10 min, conversation starter after 30 min
- Hourly hydration reminders, exercise suggestions every 2 hours
- Mood comfort after 3+ consecutive sad interactions
- Idle animations so Reachy looks alive

**Activities & Entertainment**
- Cognitive games: trivia, word association, categories, memory, story builder
- Guided exercises: 7 seated exercises + 4 routines (morning, afternoon, evening, gentle)
- Guided meditation: breathing, body scan, peaceful place, loving kindness
- Reminiscence therapy: guided memory sharing across 8 themes
- Story reader, joke teller, voice journaling, news briefing, weather
- Music: song library with natural language search, 12 melodies, 21 sound effects

**Health & Safety**
- Fall detection via MediaPipe pose estimation
- Vitals monitoring (heart rate, SpO2, BP, temperature)
- Medication reminders with confirmation tracking
- Daily wellness check-in (6-question assessment)
- Crisis/emergency keyword detection → instant caregiver alerts
- Sleep tracking (bedtime/wake logging)

**Smart Home**
- Home Assistant integration (or simulated mode)
- Lights, thermostat, TV, blinds, fan control
- Scene presets: bedtime, morning, movie, relax, bright

### Caregiver Dashboard

**Real-time**
- SSE-powered live alerts with audio notifications
- Live conversation feed (patient ↔ Reachy ↔ caregiver)
- Send messages through Reachy (polled every 3 seconds)
- Emergency SOS button
- Live camera feed from Reachy

**Patient Care**
- Patient management with conditions and emergency contacts
- Medication scheduling with adherence tracking
- Mood charts, vitals dashboard, check-in history
- Activity log with date grouping and filters

**Caregiver Tools**
- Shift handoff reports
- Caregiver notes per patient
- Auto-generated daily reports
- CSV/text export
- Scheduled messages with timeline view

**Family Portal**
- Send messages that Reachy reads aloud
- See current mood, last active time, vitals
- Quick message buttons ("I love you", "See you soon")
- Character counter on messages

**Infrastructure**
- Authentication with bcrypt, session-based login, remember me
- Multi-language (English, Spanish, French, German)
- PWA — installable on mobile with push notifications
- SQLite (default) or PostgreSQL/Supabase
- Docker + nginx deployment ready
- Dark themed responsive UI across 12 pages

### Testing & CI
- 149 unit tests across 10 test files
- GitHub Actions CI: test + lint (ruff)
- All tests pass in < 1 second

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Patient                                │
│                    (speaks to Reachy)                         │
└──────────────────────┬───────────────────────────────────────┘
                       │ voice
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                   reachy-assist (Robot)                        │
│                                                               │
│  Whisper STT ──→ Emotion Detection ──→ GPT-4o-mini Brain     │
│       │                                      │                │
│       │         ┌────────────────────────────┤                │
│       │         │  Vector Memory (pgvector)   │                │
│       │         │  Knowledge Graph (GPT)      │                │
│       │         │  Temporal Patterns           │                │
│       │         │  Mention Tracking            │                │
│       │         └────────────────────────────┘                │
│       │                                      │                │
│       │                              OpenAI TTS (nova)        │
│       │                                      │                │
│       ▼                                      ▼                │
│   [mic input]                          [speaker output]       │
│                                                               │
│   Polls dashboard ←──── REST API ────→ Pushes alerts/convo   │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP (localhost:5555)
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              caregiver-dashboard (Flask Web App)               │
│                                                               │
│  Real-time alerts (SSE)    │  Send messages to patient        │
│  Live conversation feed    │  Medication scheduling           │
│  Patient management        │  Scheduled messages              │
│  Mood/vitals charts        │  Family portal                   │
│  Activity log              │  Reports & export                │
│  Facility management       │  Settings & user management      │
│                                                               │
│  SQLite (local) or PostgreSQL/Supabase (cloud)               │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    Supabase (Cloud DB)                         │
│                                                               │
│  18 tables: conversation log, mood, mentions, topics,         │
│  facts, profile, cognitive scores, exercises, sleep,          │
│  session summaries, weekly reports, reminders, alerts,         │
│  vector memory (1536-dim embeddings), knowledge graph          │
│  (entities + relations), temporal patterns                     │
└──────────────────────────────────────────────────────────────┘
```

**Robot → Dashboard:** Alerts, conversation logs, status updates, activity events, vitals
**Dashboard → Robot:** Messages (polled every 3s), scheduled messages, medication reminders
**Camera:** Separate MJPEG stream on port 5556
**Database:** SQLite (default) or PostgreSQL/Supabase (via env var)

---

## What Each Supabase Table Stores

| Table | What goes in it | When |
|---|---|---|
| `bot_conversation_log` | Every sentence patient and Reachy say | Every interaction |
| `bot_mood_log` | Detected emotion (joy, sadness, anger, etc.) | Every interaction |
| `bot_mentions` | People, places, activities, pets, food, health | Pattern matching + GPT |
| `bot_topics` | Conversation topics | Every interaction |
| `bot_conversation_dates` | Dates the patient talked to Reachy | Daily |
| `bot_streaks` | Consecutive days of conversation | Daily |
| `bot_patient_facts` | Personal facts ("has a daughter named Sarah") | GPT extraction |
| `bot_patient_profile` | Name, favorite topic, personality notes | Updated over time |
| `bot_cognitive_scores` | Game scores (trivia, word games) | After each game |
| `bot_exercise_log` | Exercises completed and duration | After each exercise |
| `bot_sleep_log` | Bedtime and wake-up events | Goodnight/good morning |
| `bot_session_summaries` | GPT-written session notes | On session end (Ctrl+C) |
| `bot_weekly_reports` | Auto-generated weekly care reports | Weekly |
| `bot_reminders` | Patient reminders | When patient sets one |
| `bot_caregiver_alerts` | Crisis, emergency, distress alerts | Safety triggers |
| `bot_memory_vectors` | 1536-dim conversation embeddings | Every interaction |
| `bot_knowledge_entities` | People, places, things GPT identifies | GPT extraction |
| `bot_knowledge_relations` | Relationships between entities | GPT extraction |
| `bot_temporal_patterns` | Mood trends, topic changes, health spikes | Every 10 interactions |

---

## Environment Variables

### reachy-assist/.env

| Variable | Required | Description | Default |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | OpenAI API key for brain + voice + embeddings | none |
| `SUPABASE_DB_URL` | Recommended | Supabase PostgreSQL connection string | none |
| `REACHY_VOICE` | No | TTS voice: alloy, echo, fable, nova, onyx, shimmer | `nova` |
| `DASHBOARD_URL` | No | Dashboard URL for robot communication | `http://localhost:5555` |
| `WEATHER_CITY` | No | City for weather briefings | `auto` |
| `OPENAI_MODEL` | No | GPT model name | `gpt-4o-mini` |
| `OLLAMA_MODEL` | No | Ollama model name | `llama3.2` |
| `HOME_ASSISTANT_URL` | No | Home Assistant URL | none (simulated) |
| `HOME_ASSISTANT_TOKEN` | No | Home Assistant access token | none |

### caregiver-dashboard/.env

| Variable | Required | Description | Default |
|---|---|---|---|
| `SUPABASE_DB_URL` | No | Supabase PostgreSQL connection string | none (uses SQLite) |
| `DATABASE_URL` | No | Alternative PostgreSQL connection string | none |
| `SECRET_KEY` | No | Flask session secret | auto-generated |

---

## Running on Separate Machines

If the dashboard runs on a different computer (e.g. a tablet at the nurse's station):

1. Find the dashboard machine's IP: `ifconfig | grep inet`
2. On the robot machine, set in `.env`: `DASHBOARD_URL=http://192.168.1.XXX:5555`
3. Both machines must be on the same network

---

## Docker Deployment

```bash
docker-compose up -d
# Dashboard at http://localhost:5555

# With nginx reverse proxy:
docker-compose --profile production up -d
```

---

## Running Tests

```bash
cd reachy-assist
source .venv/bin/activate
python -m pytest tests/ -v
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `No module named 'openai'` | `source .venv/bin/activate && pip install openai` |
| Mic not working | System Preferences → Security → Microphone → allow Terminal |
| No audio from Reachy | Check volume. Test: `afplay /System/Library/Sounds/Tink.aiff` |
| Dashboard "Reconnecting..." | Make sure `python app.py` is running |
| Robot can't reach dashboard | Both on same machine, or set `DASHBOARD_URL` to correct IP |
| Supabase connection fails | Check password is URL-encoded, use port 6543 (not 5432) |
| Whisper slow on first run | Downloads ~500MB model. Subsequent runs are fast. |

---

## License

MIT
