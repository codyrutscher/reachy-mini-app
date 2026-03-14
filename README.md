# Reachy Mini — Accessibility Assistant

A comprehensive accessibility assistant built on the **Reachy Mini** robot platform, designed to support elderly and disabled individuals through voice interaction, emotional awareness, and caregiver coordination.

## Project Structure

```
├── reachy-assist/          # Robot-side Python application
│   ├── run.py              # Entry point (CLI flags)
│   ├── interaction.py      # Main interaction loop
│   ├── robot.py            # Reachy Mini hardware control
│   ├── speech.py           # Whisper STT + macOS TTS
│   ├── emotion.py          # Text-based emotion detection
│   ├── face_emotion.py     # Webcam facial emotion (hsemotion)
│   ├── brain.py            # LLM conversation (OpenAI / Ollama)
│   ├── config.py           # Settings, prompts, thresholds
│   ├── movements.py        # 22 robot movement patterns
│   ├── music.py            # Melody & sound effect player
│   ├── reminders.py        # Medication & appointment reminders
│   ├── checkin.py          # Daily wellness check-in
│   ├── caregiver.py        # Alert system → dashboard
│   ├── reminiscence.py     # Reminiscence therapy sessions
│   ├── cognitive.py        # Brain games (trivia, word games)
│   ├── exercises.py        # Guided physical exercises
│   ├── stories.py          # Story/audiobook reader
│   ├── jokes.py            # Family-friendly joke teller
│   ├── affirmations.py     # Daily affirmations & motivation
│   ├── companion.py        # Conversation topic starters
│   ├── calendar_tracker.py # Appointment tracking
│   ├── sleep_tracker.py    # Bedtime/wake logging
│   ├── weather.py          # Weather briefing (wttr.in)
│   ├── camera_stream.py    # MJPEG camera server (port 5556)
│   └── sounds/             # WAV files (melodies + SFX)
│
├── caregiver-dashboard/    # Flask web dashboard
│   ├── app.py              # Flask app with auth & REST API
│   ├── db.py               # SQLite database layer
│   └── templates/          # Jinja2 HTML templates
│       ├── _base.html      # Shared layout & navbar
│       ├── dashboard.html  # Main dashboard (alerts, chat, camera)
│       ├── patients.html   # Patient management
│       ├── medications.html# Medication tracking
│       ├── schedule.html   # Scheduled messages
│       ├── history.html    # Mood & check-in history
│       ├── reports.html    # Auto-generated daily reports
│       ├── activity.html   # Activity log
│       ├── facilities.html # Facility management
│       ├── settings.html   # App settings
│       └── login.html      # Authentication
```

## Features

### Robot Assistant (reachy-assist)
- **Voice interaction** — Whisper speech-to-text + macOS native TTS
- **LLM brain** — OpenAI or Ollama for natural conversation with mood tracking
- **Emotion detection** — Text keyword analysis + optional webcam facial emotion
- **22 robot movements** — Dance, greet, celebrate, breathe, stretch, and more
- **Medication management** — Reminders, confirmation tracking, caregiver alerts
- **Daily check-in** — Structured wellness assessment
- **Reminiscence therapy** — Guided memory sharing sessions
- **Cognitive games** — Trivia, word association, categories, memory games
- **Guided exercises** — 7 seated exercises + 4 pre-built routines
- **Story reader** — 5 stories read page-by-page
- **Joke teller** — 25 clean jokes with no-repeat tracking
- **Music player** — 12 melodies + 21 sound effects
- **Weather briefing** — Current weather via wttr.in (no API key)
- **Sleep tracking** — Bedtime/wake time logging with tips
- **Affirmations** — Daily positive messages and motivational quotes
- **Companion chat** — 10 conversation topic categories
- **Calendar** — Appointment tracking with natural language parsing
- **Hydration reminders** — Water intake tracking
- **Inactivity monitoring** — Auto check-in after 30 min idle
- **Camera streaming** — MJPEG server for live video feed
- **Safety detection** — Crisis, emergency, and distress alerts to caregiver

### Caregiver Dashboard (caregiver-dashboard)
- **Real-time alerts** via Server-Sent Events (SSE)
- **Live conversation** feed (patient ↔ Reachy ↔ caregiver)
- **Send messages** through Reachy to the patient
- **Quick action buttons** (medication coming, food coming, comfort, etc.)
- **Emergency SOS button**
- **Live camera feed** from Reachy
- **Patient management** — Add/track multiple patients
- **Medication tracking** — Dosages, schedules, adherence logging
- **Scheduled messages** — Time-based automated messages
- **Mood & check-in history** — Charts and trends
- **Daily reports** — Auto-generated care summaries
- **Activity log** — Timestamped event tracking
- **Facility management** — Multi-site support
- **Authentication** — Session-based login (default: admin/admin)
- **Dark themed UI** — Responsive, mobile-friendly design
- **SQLite persistence** — WAL mode for concurrent access

## Quick Start

### Prerequisites
- Python 3.12+
- Reachy Mini robot (or simulation)
- macOS (for `say` TTS command)
- OpenAI API key (optional, for LLM brain)

### Robot Setup
```bash
cd reachy-assist
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start Reachy simulation (in separate terminal)
GST_PLUGIN_SCANNER="" mjpython $(which reachy-mini-daemon) --sim --deactivate-audio

# Run the assistant
python run.py --brain openai --emotion-backend keywords
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
--brain             openai | ollama
--face              Enable webcam emotion detection
--language          en | es | fr | de | it | pt | zh | ja | ko
```

## Architecture

The robot assistant and caregiver dashboard communicate via REST API:
- Robot → Dashboard: Alerts, conversation logs, status updates, activity events
- Dashboard → Robot: Messages (polled), scheduled messages, medication reminders
- Camera: Separate MJPEG stream on port 5556

## License

MIT
