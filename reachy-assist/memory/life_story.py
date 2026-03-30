"""Life Story Builder — compiles conversations into a structured life narrative.

Pulls facts, entities, relations, and session summaries from existing data stores
and uses GPT to organize them into themed chapters that grow over time.

Chapters: childhood, family, career, hobbies, places, milestones, wisdom.
Each session can add new details to existing chapters.
"""

import json
import os
import time
from core.log_config import get_logger

logger = get_logger("life_story")

CHAPTERS = [
    "childhood",
    "family",
    "career",
    "hobbies",
    "places",
    "milestones",
    "wisdom",
]

_COMPILE_PROMPT = """You are compiling a life story for an elderly person based on facts gathered from conversations with a companion robot.

Given the raw facts, entities, relationships, and conversation excerpts below, organize them into a structured life narrative.

Return JSON with this structure:
{
  "name": "patient's name if known, else empty string",
  "chapters": {
    "childhood": "paragraph about their childhood, or empty string if no info",
    "family": "paragraph about family members and relationships",
    "career": "paragraph about their work life",
    "hobbies": "paragraph about interests and hobbies",
    "places": "paragraph about places they've lived or visited",
    "milestones": "paragraph about key life events (wedding, retirement, etc.)",
    "wisdom": "paragraph of advice, sayings, or wisdom they've shared"
  }
}

Rules:
- Write in third person ("Margaret grew up in Vermont...")
- Be warm and respectful
- Only include information that was actually mentioned — never invent
- If a chapter has no relevant info, use an empty string
- Keep each chapter to 2-4 sentences max
- Merge duplicate info naturally"""

_UPDATE_PROMPT = """You are updating an existing life story with new information from recent conversations.

Here is the current life story:
{current_story}

Here are NEW facts and conversation excerpts gathered since the last update:
{new_data}

Update the life story by merging the new information into the existing chapters. Add new details, correct anything that's been clarified, but don't remove existing content unless it's contradicted.

Return the same JSON structure:
{{
  "name": "patient's name",
  "chapters": {{
    "childhood": "...",
    "family": "...",
    "career": "...",
    "hobbies": "...",
    "places": "...",
    "milestones": "...",
    "wisdom": "..."
  }}
}}

Rules:
- Preserve existing content, weave in new details naturally
- Write in third person
- Keep each chapter to 2-6 sentences
- Only add what's actually stated in the new data"""


def _get_client():
    """Get OpenAI client if available."""
    try:
        from openai import OpenAI
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            return None
        return OpenAI()
    except ImportError:
        return None


def _gather_raw_data(patient_id: str = "default") -> dict:
    """Gather all available data about a patient from existing stores."""
    data = {"facts": [], "entities": [], "relations": [], "summaries": []}

    try:
        from memory import db_supabase as db
        if db.is_available():
            facts = db.get_facts(patient_id)
            data["facts"] = [f"{f.get('category', '')}: {f.get('fact', '')}" for f in facts]

            entities = db.get_all_entities(patient_id)
            data["entities"] = [
                f"{e['name']} ({e['entity_type']})"
                + (f" — {json.dumps(e['attributes'])}" if e.get("attributes") else "")
                for e in entities
            ]

            relations = db.get_all_relations(patient_id)
            data["relations"] = [
                f"{r['subject']} {r['relation']} {r['object']}"
                for r in relations
            ]

            summaries = db.get_session_summaries(patient_id, limit=20)
            data["summaries"] = [s.get("summary", "") for s in summaries if s.get("summary")]

            profile = db.get_profile(patient_id)
            if profile and profile.get("user_name"):
                data["name"] = profile["user_name"]
    except Exception as e:
        logger.debug("Supabase data gather failed: %s", e)

    return data


def _format_raw_data(data: dict) -> str:
    """Format gathered data into a text block for the LLM."""
    parts = []
    if data.get("name"):
        parts.append(f"Patient name: {data['name']}")
    if data.get("facts"):
        parts.append("Facts:\n" + "\n".join(f"- {f}" for f in data["facts"][:40]))
    if data.get("entities"):
        parts.append("Entities:\n" + "\n".join(f"- {e}" for e in data["entities"][:30]))
    if data.get("relations"):
        parts.append("Relations:\n" + "\n".join(f"- {r}" for r in data["relations"][:30]))
    if data.get("summaries"):
        parts.append("Session summaries:\n" + "\n".join(f"- {s}" for s in data["summaries"][:10]))
    return "\n\n".join(parts)


def _parse_response(raw: str) -> dict | None:
    """Parse LLM JSON response, handling markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error("Failed to parse life story JSON")
        return None


def compile_story(patient_id: str = "default") -> dict | None:
    """Compile a full life story from all available data.

    Returns dict with 'name', 'chapters', 'compiled_at' or None on failure.
    """
    client = _get_client()
    if not client:
        logger.warning("No OpenAI client — cannot compile life story")
        return None

    data = _gather_raw_data(patient_id)
    raw_text = _format_raw_data(data)

    if not raw_text.strip():
        logger.info("No data available to compile life story")
        return None

    try:
        resp = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            messages=[
                {"role": "system", "content": _COMPILE_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            max_tokens=1200,
            temperature=0.3,
        )
        result = _parse_response(resp.choices[0].message.content)
        if result:
            result["compiled_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            result["patient_id"] = patient_id
            _save_story(patient_id, result)
            logger.info("Life story compiled for %s", patient_id)
        return result
    except Exception as e:
        logger.error("Life story compilation failed: %s", e)
        return None


def update_story(patient_id: str = "default") -> dict | None:
    """Update an existing life story with new data since last compilation.

    If no story exists yet, does a full compile instead.
    """
    existing = get_story(patient_id)
    if not existing:
        return compile_story(patient_id)

    client = _get_client()
    if not client:
        return existing

    data = _gather_raw_data(patient_id)
    new_text = _format_raw_data(data)

    if not new_text.strip():
        return existing

    prompt = _UPDATE_PROMPT.format(
        current_story=json.dumps(existing, indent=2),
        new_data=new_text,
    )

    try:
        resp = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            messages=[
                {"role": "system", "content": prompt},
            ],
            max_tokens=1200,
            temperature=0.3,
        )
        result = _parse_response(resp.choices[0].message.content)
        if result:
            result["compiled_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            result["patient_id"] = patient_id
            _save_story(patient_id, result)
            logger.info("Life story updated for %s", patient_id)
        return result
    except Exception as e:
        logger.error("Life story update failed: %s", e)
        return existing


# ── Storage (Supabase with local JSON fallback) ──────────────────

def _save_story(patient_id: str, story: dict) -> None:
    """Persist the compiled story."""
    try:
        from memory import db_supabase as db
        if db.is_available():
            db._execute(
                """INSERT INTO life_stories (patient_id, story, compiled_at)
                   VALUES (%s, %s, NOW())
                   ON CONFLICT (patient_id)
                   DO UPDATE SET story = EXCLUDED.story, compiled_at = NOW()""",
                (patient_id, json.dumps(story)),
            )
            return
    except Exception:
        pass

    # Fallback: save to local JSON
    path = os.path.join(os.path.dirname(__file__), "..", "life_stories.json")
    try:
        existing = {}
        if os.path.exists(path):
            with open(path) as f:
                existing = json.load(f)
        existing[patient_id] = story
        with open(path, "w") as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        logger.error("Failed to save life story locally: %s", e)


def get_story(patient_id: str = "default") -> dict | None:
    """Retrieve the compiled life story for a patient."""
    try:
        from memory import db_supabase as db
        if db.is_available():
            row = db._execute(
                "SELECT story FROM life_stories WHERE patient_id = %s",
                (patient_id,),
                fetchone=True,
            )
            if row:
                story = row["story"]
                return json.loads(story) if isinstance(story, str) else story
    except Exception:
        pass

    # Fallback: local JSON
    path = os.path.join(os.path.dirname(__file__), "..", "life_stories.json")
    try:
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            return data.get(patient_id)
    except Exception:
        pass

    return None


def get_chapter(patient_id: str = "default", chapter: str = "family") -> str:
    """Get a single chapter from the life story."""
    story = get_story(patient_id)
    if not story:
        return ""
    return story.get("chapters", {}).get(chapter, "")


def get_story_summary(patient_id: str = "default") -> str:
    """Get a one-paragraph summary of the life story for conversation context."""
    story = get_story(patient_id)
    if not story:
        return ""
    chapters = story.get("chapters", {})
    parts = [v for v in chapters.values() if v]
    if not parts:
        return ""
    name = story.get("name", "The patient")
    return f"{name}'s life story: " + " ".join(parts[:3])
