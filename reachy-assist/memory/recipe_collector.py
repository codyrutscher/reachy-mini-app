"""Recipe Collector — detects and saves recipes patients describe.

When a patient talks about cooking or describes a recipe, this module
extracts it and saves it in a structured format (name, ingredients, steps).
Uses GPT for structured extraction when available, falls back to raw text.
"""

import json
import os
import re
import time
from core.log_config import get_logger

logger = get_logger("recipe_collector")

_RECIPE_TRIGGERS = [
    "my recipe for", "how i make", "how to make", "the way i cook",
    "you take some", "first you", "the secret ingredient",
    "i always cook", "my special", "the ingredients are",
    "you need to add", "mix it with", "bake it", "let it simmer",
    "my grandmother's recipe", "family recipe", "i used to make",
]


def is_recipe_mention(text: str) -> bool:
    """Check if the text describes a recipe."""
    lower = text.lower()
    return any(t in lower for t in _RECIPE_TRIGGERS)


_EXTRACT_PROMPT = """Extract a recipe from what an elderly person said. Return JSON:
{
  "name": "recipe name (best guess)",
  "ingredients": ["ingredient 1", "ingredient 2"],
  "steps": ["step 1", "step 2"],
  "notes": "any tips or personal touches mentioned"
}
Only include what was actually mentioned. If unclear, use the raw text as a single step."""


def save_recipe(text: str, patient_id: str = "default") -> str:
    """Extract and save a recipe. Returns acknowledgment."""
    recipe = _extract_recipe(text)

    try:
        from memory import db_supabase as db
        if db.is_available():
            db._execute(
                "INSERT INTO recipe_book (patient_id, name, recipe, raw_text) VALUES (%s, %s, %s, %s)",
                (patient_id, recipe.get("name", "Untitled"), json.dumps(recipe), text),
            )
            logger.info("Recipe saved: %s", recipe.get("name", ""))
            return f"I've saved your recipe for {recipe.get('name', 'that')}. What a treasure."
    except Exception:
        pass

    # Fallback
    path = os.path.join(os.path.dirname(__file__), "..", "recipe_book.json")
    try:
        existing = []
        if os.path.exists(path):
            with open(path) as f:
                existing = json.load(f)
        recipe["patient_id"] = patient_id
        recipe["raw_text"] = text
        existing.append(recipe)
        with open(path, "w") as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        logger.error("Failed to save recipe: %s", e)

    return f"I've saved your recipe for {recipe.get('name', 'that')}. What a treasure."


def _extract_recipe(text: str) -> dict:
    """Try GPT extraction, fall back to raw text."""
    try:
        from openai import OpenAI
        key = os.environ.get("OPENAI_API_KEY")
        if key:
            client = OpenAI()
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _EXTRACT_PROMPT},
                    {"role": "user", "content": text},
                ],
                max_tokens=400,
                temperature=0,
            )
            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
            return json.loads(raw)
    except Exception:
        pass

    # Fallback: just save the raw text
    return {"name": "Untitled Recipe", "ingredients": [], "steps": [text], "notes": ""}


def get_recipes(patient_id: str = "default", limit: int = 20) -> list[dict]:
    """Get saved recipes."""
    try:
        from memory import db_supabase as db
        if db.is_available():
            rows = db._execute(
                "SELECT name, recipe, created_at FROM recipe_book "
                "WHERE patient_id=%s ORDER BY created_at DESC LIMIT %s",
                (patient_id, limit), fetch=True,
            )
            if rows:
                results = []
                for r in rows:
                    recipe = r.get("recipe", "{}")
                    if isinstance(recipe, str):
                        recipe = json.loads(recipe)
                    recipe["date"] = str(r.get("created_at", ""))
                    results.append(recipe)
                return results
    except Exception:
        pass

    path = os.path.join(os.path.dirname(__file__), "..", "recipe_book.json")
    try:
        if os.path.exists(path):
            with open(path) as f:
                entries = json.load(f)
            return [e for e in entries if e.get("patient_id") == patient_id][-limit:]
    except Exception:
        pass
    return []
