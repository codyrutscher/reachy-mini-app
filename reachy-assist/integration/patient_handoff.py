"""Multi-Patient Handoff — smooth context switching between patients.

When Reachy moves to a different patient, this module:
1. Saves the current session summary
2. Loads the new patient's profile, facts, and preferences
3. Adjusts the brain's context and greeting
"""

import os
from core.log_config import get_logger

logger = get_logger("handoff")


def handoff(brain, old_patient_id: str, new_patient_id: str) -> str:
    """Switch from one patient to another. Returns a greeting for the new patient."""

    # 1. Save current session if there was one
    if brain and brain._interaction_count > 0:
        try:
            summary = brain.get_session_summary()
            logger.info("Saved session for %s: %d interactions", old_patient_id, summary.get("interactions", 0))
        except Exception:
            pass

    # 2. Reset brain state
    if brain:
        brain._patient_id = new_patient_id
        brain._interaction_count = 0
        brain._topics_discussed = []
        brain._current_topic = None
        brain._topic_depth = 0
        brain.mood_history = []
        brain.consecutive_sad = 0
        brain.session_start = True
        brain._last_response = ""
        brain._session_start_time = None
        # Keep the system prompt but clear conversation history
        system_msg = brain.history[0] if brain.history else None
        brain.history = [system_msg] if system_msg else []

    # 3. Load new patient profile
    name = "friend"
    try:
        from memory import db_supabase as db
        if db.is_available():
            profile = db.get_profile(new_patient_id)
            if profile:
                name = profile.get("preferred_name") or profile.get("name") or profile.get("user_name") or "friend"
                if brain:
                    brain.user_name = name
                    # Load known facts
                    facts = db.get_facts(new_patient_id)
                    brain.user_facts = [f.get("fact", "") for f in (facts or [])[:10]]
    except Exception:
        pass

    logger.info("Handoff: %s -> %s (%s)", old_patient_id, new_patient_id, name)

    return (
        f"Hello {name}! It's wonderful to see you. "
        f"I'm all yours now. How are you doing today?"
    )


def get_patient_summary(patient_id: str) -> dict:
    """Get a quick summary of a patient for handoff context."""
    summary = {"patient_id": patient_id, "name": "", "mood": "unknown", "facts": []}
    try:
        from memory import db_supabase as db
        if db.is_available():
            profile = db.get_profile(patient_id)
            if profile:
                summary["name"] = profile.get("user_name", "")
            moods = db.get_moods(patient_id, limit=5)
            if moods:
                summary["mood"] = moods[0].get("mood", "unknown")
            facts = db.get_facts(patient_id)
            summary["facts"] = [f.get("fact", "") for f in (facts or [])[:5]]
    except Exception:
        pass
    return summary
