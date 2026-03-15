# Reachy Mini — Accessibility Assistant

A comprehensive accessibility assistant built on the **Reachy Mini** robot platform, designed to support elderly and disabled individuals through voice interaction, emotional awareness, proactive care, and caregiver coordination.

## Project Structure

```
├── reachy-assist/              # Robot-side Python application
│   ├── run.py                  # Entry point (CLI flags)
│   ├── interaction.py          # Main interaction loop
│   ├── robot.py                # Reachy Mini hardware control
│   ├── speech.py               # Whisper STT + macOS TTS
│   ├── emotion.py              # Text-based emotion detection
│   ├── face_emotion.py         # Webcam facial emotion (hsemotion)
│   ├── brain.py                # LLM conversation with RAG memory
│   ├── memory.py               # RAG memory system (vector store)
│   ├── config.py               # Settings, prompts, thresholds
│   ├── profiles.py             # Elderly vs disabled patient profiles
│   ├── autonomy.py             # Proactive behavior engine
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
│   ├── jokes.py                # Family-friendly joke teller
│   ├── affirmations.py         # Daily affirmations & motivation
│   ├── companion.py            # Conversation topic starters
│   ├── calendar_tracker.py     # Appointment tracking
│   ├── sleep_tracker.py        # Bedtime/wake logging
│   ├── journal.py              # Voice journaling
│   ├── news.py                 # News briefing reader
│   ├── weather.py              # Weather briefing (wttr.in)
│   ├── datetime_helper.py      # Date/time awareness
│   ├── smart_home.py           # Home Assistant integration
│   ├── vitals.py               # Bluetooth vitals monitoring
│   ├── fall_detection.py       # MediaPipe pose-based fall detection
│   ├── patient_model.py        # Cognitive/exercise/med trend tracking
│   ├── camera_stream.py        # MJPEG camera server (port 5556)
│   ├── songs/                  # Song library (MP3/WAV/FLAC files)
│   ├── sounds/                 # Generated WAV files (melodies + SFX)
│   └── tests/                  # 149 unit tests
│
├── caregiver-dashboard/        # Flask web dashboard (PWA)
│   ├── app.py                  # Flask app with auth & REST API
│   ├── db.py                   # SQLite database layer
│   ├── db_postgres.py          # PostgreSQL/Supabase backend
│   ├── i18n.py                 # Multi-language translations
│   ├── static/                 # PWA manifest, service worker, icons
│   └── templates/              # Jinja2 HTML templates (11 pages)
│
├── Dockerfile.dashboard        # Docker image for dashboard
├── docker-compose.yml          # Docker Compose deployment
├── nginx.conf                  # Nginx reverse proxy config
└── .github/workflows/ci.yml    # GitHub Actions CI (test + lint)
```

## Features

### Robot Assistant (reachy-assist)

#### Voice & Conversation
- **Speech recognition** — OpenAI Whisper (small model) with 8-second continuous recording, silence trimming, and mic calibration
- **Text-to-speech** — macOS native `say` command with per-language voice selection and configurable rate; pyttsx3 fallback
- **LLM brain** — OpenAI GPT-4o-mini or Ollama (llama3.2) for natural conversation
- **Emotion-adaptive strategies** — Conversation style changes based on dominant mood (shorter sentences when sad, grounding when fearful, validation when angry)
- **Conversation memory** — Extracts personal facts (family, pets, career, interests) and uses them to personalize responses
- **RAG memory system** — SQLite vector store with OpenAI embeddings (hash-based fallback), cross-session memory recall, session summaries
- **Safety detection** — Crisis keywords, emergency keywords, and sustained distress trigger immediate caregiver alerts

#### Proactive Autonomy Engine
- **Morning routine** — Weather briefing + affirmation + medication reminder (7-9 AM)
- **Midday check-in** — Activity suggestions, lunch/hydration reminder (12-2 PM)
- **Evening wind-down** — Bedtime story/music offer, medication check (8-10 PM)
- **Silence detection** — Gentle check after 10 min idle, conversation starter after 30 min
- **Hydration reminders** — Hourly water nudges during waking hours
- **Exercise suggestions** — Every 2 hours during the day
- **Wellness check-in** — Every 4 hours, structured 6-question assessment
- **Mood comfort** — Proactive support after 3+ consecutive sad interactions
- **Idle animations** — Subtle movements so Reachy looks alive

#### Activities & Entertainment
- **Cognitive games** — Trivia, word association, categories, memory game, story builder
- **Guided exercises** — 7 seated exercises + 4 pre-built routines (morning, afternoon, evening, gentle)
- **Guided meditation** — Breathing, body scan, peaceful place, loving kindness
- **Reminiscence therapy** — Guided memory sharing across 8 themes
- **Story reader** — 5 stories read page-by-page
- **Joke teller** — 25 clean jokes with no-repeat tracking
- **Voice journaling** — Dictate diary entries, save/cancel
- **Companion chat** — 10 conversation topic categories with starters
- **News briefing** — Headlines reader
- **Affirmations** — Daily positive messages, motivational quotes, gratitude prompts

#### Music
- **Song library** — SQLite database, auto-scans `songs/` folder for MP3/WAV/M4A/OGG/FLAC
- **Natural language requests** — "Play Frank Sinatra", "play something calm", "play happy music"
- **Search** — By title, artist, genre, or mood
- **Playlists** — Create and manage playlists
- **12 generated melodies** — Calm, happy, lullaby, morning, celebration, thinking, gentle, waltz, nostalgic, playful, rain, sunset
- **21 sound effects** — Chimes, alerts, game sounds, breathing cues
- **Mood-based fallback** — Falls back to matching generated melody when no songs found

#### Health & Safety
- **Medication management** — Reminders, confirmation tracking, caregiver alerts
- **Daily check-in** — Sleep, pain, mood, eating, social, movement assessment
- **Fall detection** — MediaPipe pose estimation (sudden hip drops, lying posture, head-below-hips)
- **Vitals monitoring** — Heart rate, SpO2, blood pressure, temperature (BLE devices or simulated)
- **Patient model** — Tracks cognitive decline, exercise compliance, medication adherence over time
- **Sleep tracking** — Bedtime/wake time logging with quality tips
- **Hydration tracking** — Water intake reminders and logging
- **Emergency alerts** — Crisis, emergency, medication, food, and help requests sent to caregiver

#### Smart Home
- **Home Assistant integration** — REST API control (or simulated mode)
- **Devices** — Lights (on/off/dim), thermostat, TV, blinds/curtains, fan
- **Scene presets** — Bedtime, morning, movie, relax, bright
- **Natural language** — "Turn on the lights", "set temperature to 72", "bedtime mode"

#### Robot Control
- **22 movement patterns** — Dance, greet, celebrate, breathe, stretch, bow, wiggle, rock, and more
- **Facial expressions** — Joy, sadness, anger, fear, surprise, neutral
- **Camera streaming** — MJPEG server on port 5556
- **Patient profiles** — Elderly vs disabled with different TTS rates, care responses, and autonomy configs

### Caregiver Dashboard (caregiver-dashboard)

#### Core
- **Real-time alerts** via Server-Sent Events (SSE) with audio notifications
- **Live conversation** feed (patient ↔ Reachy ↔ caregiver)
- **Send messages** through Reachy to the patient
- **Quick action buttons** — Medication coming, food coming, comfort, etc.
- **Emergency SOS button**
- **Live camera feed** from Reachy

#### Patient Care
- **Patient management** — Add/track multiple patients with conditions and emergency contacts
- **Medication tracking** — Dosages, schedules, adherence logging, today's med log
- **Mood charts** — Bar chart + summary with emoji indicators
- **Vitals dashboard** — Heart rate + SpO2 line chart, latest readings
- **Medication adherence** — Donut chart showing taken vs missed
- **Check-in history** — Timestamped wellness assessment results
- **Mood timeline** — Chronological mood entries

#### Caregiver Tools
- **Shift handoff** — Auto-generated reports from today's alerts, moods, meds, notes
- **Caregiver notes** — Add/delete observations per patient
- **Daily reports** — Auto-generated care summaries
- **Activity log** — Timestamped event tracking
- **CSV export** — Activity log and alerts exportable
- **Text export** — Daily reports downloadable

#### Family Portal
- **Send messages** — Family members can send messages that Reachy reads aloud
- **Patient summary** — Current mood, last active time, dominant mood
- **Mood display** — Recent mood entries with emoji
- **Vitals display** — Latest heart rate, SpO2, blood pressure, temperature

#### Infrastructure
- **Authentication** — bcrypt password hashing (sha256 fallback), session-based login
- **User management** — CRUD API for users, password change, role-based access
- **Multi-language** — i18n translations (English, Spanish, French, German)
- **PWA** — Installable on mobile, offline caching, push notifications for critical alerts
- **SQLite** — WAL mode for concurrent access (default)
- **PostgreSQL/Supabase** — Optional backend via `DATABASE_URL` or `SUPABASE_DB_URL` env var
- **Docker** — Dockerfile + docker-compose with nginx reverse proxy
- **Dark themed UI** — Responsive design with 11 pages
- **Scheduled messages** — Time-based automated messages with repeat options
- **Facility management** — Multi-site support
- **Trend APIs** — Mood, activity, and medication trends by day

### Testing & CI
- **149 unit tests** across 10 test files (brain, autonomy, checkin, cognitive, emotion, helpers, memory, profiles, reminders, dashboard API)
- **GitHub Actions CI** — 3 jobs: test-reachy-assist (pytest + coverage), test-dashboard (API tests), lint (ruff)
- **All tests pass in < 1 second**

## Quick Start

### Prerequisites
- Python 3.12+
- Reachy Mini robot (or simulation)
- macOS (for `say` TTS command)
- OpenAI API key (optional, for LLM brain + embeddings)

### Robot Setup
```bash
cd reachy-assist
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start Reachy simulation (separate terminal)
GST_PLUGIN_SCANNER="" mjpython $(which reachy-mini-daemon) --sim --deactivate-audio

# Run the assistant
python run.py --brain openai --profile elderly
```

### Dashboard Setup
```bash
cd caregiver-dashboard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
# Open http://localhost:5555 — login: admin / admin
```

### CLI Flags
```
--text              Text mode (no mic/speaker)
--emotion-backend   keywords | transformers
--brain             openai | ollama | none
--face              Enable webcam emotion detection
--language          en | es | fr | de | it | pt | zh | ja | ko
--profile           elderly | disabled
```

### Adding Songs
Drop MP3/WAV/M4A/OGG/FLAC files into `reachy-assist/songs/`. Reachy auto-discovers them on startup.

Name files as `Artist - Title.mp3` for automatic metadata parsing. Organize into subfolders by genre (e.g. `songs/jazz/`, `songs/classical/`).

### Supabase/PostgreSQL Setup
```bash
# Install the Postgres driver in the dashboard venv
pip install psycopg2-binary

# Set your connection string
export SUPABASE_DB_URL="postgresql://postgres:yourpassword@db.xxxxx.supabase.co:5432/postgres"
# or
export DATABASE_URL="postgresql://user:pass@host:port/dbname"

# Start the dashboard — it auto-detects Postgres
python app.py
```

### Docker Deployment
```bash
docker-compose up -d
# Dashboard at http://localhost:5555
# Add nginx profile for reverse proxy: docker-compose --profile production up -d
```

### Running Tests
```bash
cd reachy-assist
source .venv/bin/activate
python -m pytest tests/ -v
```

## Architecture

```
┌─────────────────────┐     REST API      ┌──────────────────────┐
│   Reachy Mini Robot  │ ───────────────── │  Caregiver Dashboard │
│                      │                   │                      │
│  Whisper STT         │  → Alerts         │  Flask + SQLite/PG   │
│  macOS TTS           │  → Conversation   │  SSE real-time       │
│  OpenAI/Ollama LLM   │  → Status         │  PWA (installable)   │
│  Emotion detection   │  → Activity log   │  11 pages            │
│  RAG memory          │                   │  Auth + i18n         │
│  Autonomy engine     │  ← Messages       │  Family portal       │
│  22 movements        │  ← Med schedule   │  Shift handoffs      │
│  Song library        │  ← Scheduled msgs │  Vitals + charts     │
│  Smart home          │                   │  CSV/text export     │
│  Fall detection      │                   │                      │
│  Vitals monitoring   │  Camera (5556)    │  Live camera feed    │
└─────────────────────┘ ─────────────────  └──────────────────────┘
                                                     │
                                              ┌──────┴──────┐
                                              │ Family Portal│
                                              │ (phone/web)  │
                                              └─────────────┘
```

- Robot → Dashboard: Alerts, conversation logs, status updates, activity events, vitals
- Dashboard → Robot: Messages (polled), scheduled messages, medication reminders
- Camera: Separate MJPEG stream on port 5556
- Database: SQLite (default) or PostgreSQL/Supabase (via env var)

## Roadmap

### Integration (built, needs wiring)
- [ ] Start fall detection monitor in the main interaction loop
- [ ] Start vitals monitor background thread in the main loop
- [ ] Log cognitive game scores to patient_model from interaction loop
- [ ] Log exercise completions to patient_model
- [ ] Log medication adherence events to patient_model
- [ ] Inject i18n translations into dashboard templates (currently hardcoded English)

### Features
- [ ] Multi-patient support — switch between patients, per-patient profiles and data
- [ ] Voice cloning / custom TTS voices — more natural than macOS `say`
- [ ] Video call integration — family video chat through Reachy
- [ ] Medication OCR — photo of pill bottle → auto-add to schedule
- [ ] Activity recognition from camera — detect eating, sleeping, watching TV
- [ ] Emergency contact auto-dial — call 911 or family on crisis detection
- [ ] Photo album viewer — show family photos on a connected screen
- [ ] Birthday/holiday awareness — special greetings and themed activities
- [ ] Pet companion mode — virtual pet the patient can "care for"
- [ ] Card/board games — interactive games with the patient
- [ ] Spotify/Apple Music integration — stream real music

### Developer & Infrastructure
- [ ] Tests for smart_home, vitals, patient_model, fall_detection, music song library
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Rate limiting on dashboard API
- [ ] HTTPS setup with Let's Encrypt certificates
- [ ] CI/CD auto-deploy for dashboard Docker container
- [ ] Structured logging and error tracking
- [ ] Dashboard mobile responsiveness polish

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key for LLM + embeddings | (none) |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4o-mini` |
| `OLLAMA_MODEL` | Ollama model name | `llama3.2` |
| `DASHBOARD_URL` | Dashboard URL for robot → dashboard comms | `http://localhost:5555` |
| `WEATHER_CITY` | City for weather briefing | `auto` |
| `DATABASE_URL` | PostgreSQL connection string | (none, uses SQLite) |
| `SUPABASE_DB_URL` | Supabase PostgreSQL connection string | (none) |
| `SECRET_KEY` | Flask session secret key | `reachy-care-secret-key-change-me` |
| `HOME_ASSISTANT_URL` | Home Assistant base URL | (none, simulated) |
| `HOME_ASSISTANT_TOKEN` | Home Assistant long-lived access token | (none) |
| `REACHY_SONGS_DIR` | Path to song library folder | `reachy-assist/songs/` |

## License

MIT
