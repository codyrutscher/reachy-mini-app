"""Daily Journal — auto-generates a warm journal entry from each day's
conversations for family members to read.

At the end of a session (or on demand), pulls the day's conversation log,
session summaries, moods, and facts learned, then uses GPT to write a
short, warm journal entry in the patient's voice.

Entries are stored in Supabase (daily_journal table) with local JSON fallback.
"""

import json
import os
import time
from datetime import datetime, date
from core.log_config import get_logger

logger = get_logger("daily_journal")

_JOURNAL_PROMPT = """You are writing a daily journal entry for an elderly person based on their conversations with a companion robot today.

Write as if the patient is telling their family about their day. Use first person ("I").

Given the conversation excerpts, mood data, and topics below, write a warm 3-5 sentence journal entry that captures the highlights and emotional tone of the day.

Rules:
- Write in first person, warm and natural ("Today I had a lovely chat about...")
- Mention specific topics, people, or memories that came up
- Reflect the overall mood (happy day, quiet day, nostalgic day, etc.)
- Keep it short — family should be able to read it in 30 seconds
- Never invent details that weren't in the conversations
- If the day was quiet with few interactions, say so gently"""


def _get_client():
    """Get OpenAI client if available."""
    try:
        from openai import OpenAI
        if not os.environ.get("OPENAI_API_KEY"):
            return None
        return OpenAI()
    except ImportError:
        return None


def _gather_today_data(patient_id: str = "default") -> dict:
    """Gather today's conversation data for journal generation."""
    data = {"conversations": [], "moods": [], "topics": [], "facts": [],
            "summary": "", "duration": 0, "interactions": 0}
    try:
        from memory import db_supabase as db
        if not db.is_available():
            return data

        # Recent conversations (today's)
        convos = db.get_conversations(patient_id, limit=100)
        today_str = date.today().isoformat()
        for c in convos:
            created = str(c.get("created_at", ""))
            if today_str in created:
                speaker = c.get("speaker", "")
                text = c.get("text", "")
                emotion = c.get("emotion", "")
                data["conversations"].append(
                    f"[{speaker}] {text}" + (f" ({emotion})" if emotion else "")
                )

        # Today's moods
        moods = db.get_moods(patient_id, limit=50)
        for m in moods:
            created = str(m.get("created_at", ""))
            if today_str in created:
                data["moods"].append(m.get("mood", "neutral"))

        # Session summaries from today
        summaries = db.get_session_summaries(patient_id, limit=5)
        for s in summaries:
            created = str(s.get("created_at", ""))
            if today_str in created:
                data["summary"] = s.get("summary_text", "") or s.get("summary", "")
                data["duration"] += s.get("duration_minutes", 0)
                data["interactions"] += s.get("interactions", 0)
                topics = s.get("topics_discussed", "[]")
                if isinstance(topics, str):
                    topics = json.loads(topics)
                data["topics"].extend(topics)
                facts = s.get("facts_learned", "[]")
                if isinstance(facts, str):
                    facts = json.loads(facts)
                data["facts"].extend(facts)
    except Exception as e:
        logger.debug("Failed to gather today's data: %s", e)

    return data


def _format_journal_input(data: dict) -> str:
    """Format gathered data into text for the LLM."""
    parts = []
    if data["conversations"]:
        # Take a sample — don't send 100 lines
        sample = data["conversations"][:30]
        parts.append("Conversations today:\n" + "\n".join(sample))
    if data["moods"]:
        from collections import Counter
        mood_counts = Counter(data["moods"])
        parts.append("Moods today: " + ", ".join(f"{m} ({c}x)" for m, c in mood_counts.most_common()))
    if data["topics"]:
        parts.append("Topics discussed: " + ", ".join(set(data["topics"][:10])))
    if data["facts"]:
        parts.append("New things learned: " + "; ".join(data["facts"][:5]))
    if data["summary"]:
        parts.append("Session summary: " + data["summary"])
    if data["duration"]:
        parts.append(f"Total conversation time: {data['duration']:.0f} minutes")
    return "\n\n".join(parts)


def generate_entry(patient_id: str = "default", for_date: str = "") -> dict | None:
    """Generate a daily journal entry from today's conversations.

    Returns dict with 'date', 'entry', 'mood', 'topics', 'generated_at'
    or None on failure.
    """
    entry_date = for_date or date.today().isoformat()
    data = _gather_today_data(patient_id)
    input_text = _format_journal_input(data)

    if not input_text.strip():
        logger.info("No conversation data for journal entry")
        return None

    client = _get_client()
    if client:
        try:
            resp = client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
                messages=[
                    {"role": "system", "content": _JOURNAL_PROMPT},
                    {"role": "user", "content": input_text},
                ],
                max_tokens=300,
                temperature=0.7,
            )
            entry_text = resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error("GPT journal generation failed: %s", e)
            entry_text = _fallback_entry(data)
    else:
        entry_text = _fallback_entry(data)

    # Determine dominant mood
    dominant_mood = "neutral"
    if data["moods"]:
        from collections import Counter
        dominant_mood = Counter(data["moods"]).most_common(1)[0][0]

    entry = {
        "date": entry_date,
        "entry": entry_text,
        "mood": dominant_mood,
        "topics": list(set(data["topics"][:10])),
        "interactions": data["interactions"],
        "duration_minutes": round(data["duration"], 1),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "patient_id": patient_id,
    }

    _save_entry(patient_id, entry)
    logger.info("Daily journal entry generated for %s on %s", patient_id, entry_date)
    return entry


def _fallback_entry(data: dict) -> str:
    """Generate a simple journal entry without GPT."""
    parts = []
    n = data["interactions"]
    dur = data["duration"]

    if n > 0:
        parts.append(f"Today I had {n} exchanges with Reachy over about {dur:.0f} minutes.")
    else:
        parts.append("It was a quiet day today.")

    if data["topics"]:
        topics = ", ".join(data["topics"][:3])
        parts.append(f"We talked about {topics}.")

    if data["moods"]:
        from collections import Counter
        top_mood = Counter(data["moods"]).most_common(1)[0][0]
        parts.append(f"Overall I was feeling {top_mood}.")

    if data["facts"]:
        parts.append(f"I shared something new: {data['facts'][0]}.")

    return " ".join(parts)


# ── Storage ───────────────────────────────────────────────────────

def _save_entry(patient_id: str, entry: dict) -> None:
    """Persist a journal entry."""
    try:
        from memory import db_supabase as db
        if db.is_available():
            db._execute(
                """INSERT INTO daily_journal (patient_id, entry_date, entry, mood, topics,
                   interactions, duration_minutes)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (patient_id, entry_date)
                   DO UPDATE SET entry = EXCLUDED.entry, mood = EXCLUDED.mood,
                   topics = EXCLUDED.topics, interactions = EXCLUDED.interactions,
                   duration_minutes = EXCLUDED.duration_minutes""",
                (patient_id, entry["date"], entry["entry"], entry["mood"],
                 json.dumps(entry["topics"]), entry["interactions"],
                 entry["duration_minutes"]),
            )
            return
    except Exception:
        pass

    # Fallback: local JSON
    path = os.path.join(os.path.dirname(__file__), "..", "daily_journal.json")
    try:
        existing = []
        if os.path.exists(path):
            with open(path) as f:
                existing = json.load(f)
        # Replace if same date+patient exists
        existing = [e for e in existing
                    if not (e.get("patient_id") == patient_id and e.get("date") == entry["date"])]
        existing.append(entry)
        # Keep last 90 days
        existing = existing[-90:]
        with open(path, "w") as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        logger.error("Failed to save journal locally: %s", e)


def get_entries(patient_id: str = "default", limit: int = 30) -> list[dict]:
    """Get recent journal entries for a patient."""
    try:
        from memory import db_supabase as db
        if db.is_available():
            rows = db._execute(
                "SELECT entry_date, entry, mood, topics, interactions, duration_minutes, created_at "
                "FROM daily_journal WHERE patient_id=%s ORDER BY entry_date DESC LIMIT %s",
                (patient_id, limit), fetch=True,
            )
            if rows:
                results = []
                for r in rows:
                    topics = r.get("topics", "[]")
                    if isinstance(topics, str):
                        topics = json.loads(topics)
                    results.append({
                        "date": str(r["entry_date"]),
                        "entry": r["entry"],
                        "mood": r.get("mood", "neutral"),
                        "topics": topics,
                        "interactions": r.get("interactions", 0),
                        "duration_minutes": r.get("duration_minutes", 0),
                    })
                return results
    except Exception:
        pass

    # Fallback: local JSON
    path = os.path.join(os.path.dirname(__file__), "..", "daily_journal.json")
    try:
        if os.path.exists(path):
            with open(path) as f:
                entries = json.load(f)
            patient_entries = [e for e in entries if e.get("patient_id") == patient_id]
            return patient_entries[-limit:]
    except Exception:
        pass

    return []


def get_entry(patient_id: str = "default", for_date: str = "") -> dict | None:
    """Get a single journal entry for a specific date."""
    entry_date = for_date or date.today().isoformat()
    entries = get_entries(patient_id, limit=60)
    for e in entries:
        if e.get("date") == entry_date:
            return e
    return None
