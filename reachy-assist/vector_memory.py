"""Vector memory — stores conversation embeddings in Supabase pgvector
for semantic search across all past conversations.

This gives Reachy true long-term memory: instead of matching keywords,
it finds past conversations that are *similar in meaning* to what the
patient is saying right now.
"""

import os

_client = None
_available = False
_model = "text-embedding-3-small"  # 1536 dimensions, cheap and fast


def init():
    """Initialize the OpenAI client for embeddings."""
    global _client, _available
    try:
        from openai import OpenAI
        _client = OpenAI()
        _available = True
        print("[VECMEM] Vector memory initialized (OpenAI embeddings)")
        return True
    except Exception as e:
        print(f"[VECMEM] Not available: {e}")
        return False


def is_available() -> bool:
    return _available


def _get_embedding(text: str) -> list:
    """Turn text into a 1536-dimension vector."""
    if not _client:
        return []
    resp = _client.embeddings.create(input=text, model=_model)
    return resp.data[0].embedding


# Emotions that make a memory more important
_EMOTION_WEIGHTS = {
    "joy": 1.4,       # happy memories are treasured
    "sadness": 1.5,   # sad memories are deeply personal
    "fear": 1.3,      # fears are important to remember
    "anger": 1.2,     # frustrations matter
    "surprise": 1.1,  # surprises are memorable
    "neutral": 1.0,   # baseline
}


def _get_emotion_weight(emotion: str) -> float:
    """Return how important this memory is based on emotion."""
    return _EMOTION_WEIGHTS.get(emotion, 1.0)


def store_turn(text: str, speaker: str = "patient", emotion: str = "",
               topic: str = "general", patient_id: str = "default"):
    """Store a conversation turn with its embedding and emotion weight."""
    if not _available:
        return
    try:
        import db_supabase as _db
        if not _db.is_available():
            return
        embedding = _get_embedding(text)
        if embedding:
            weight = _get_emotion_weight(emotion)
            _db.save_memory_vector(text, embedding, speaker, emotion, topic,
                                   patient_id, emotion_weight=weight)
    except Exception as e:
        print(f"[VECMEM] Store error: {e}")


def store_bot_response(text: str, emotion: str = "", topic: str = "general",
                       patient_id: str = "default"):
    """Store what Reachy said too — so we can find full conversation context."""
    store_turn(text, speaker="reachy", emotion=emotion, topic=topic,
               patient_id=patient_id)


def recall(text: str, patient_id: str = "default", limit: int = 5) -> list:
    """Find past conversations most similar to what the patient just said.
    Results are re-ranked by similarity * emotion_weight, so emotional
    memories bubble up higher than neutral ones."""
    if not _available:
        return []
    try:
        import db_supabase as _db
        if not _db.is_available():
            return []
        embedding = _get_embedding(text)
        if not embedding:
            return []
        # Fetch more than we need so we can re-rank
        raw = _db.search_memory_vectors(embedding, patient_id, limit=limit * 2)
        # Re-rank: weighted_score = similarity * emotion_weight
        for r in raw:
            sim = r.get("similarity", 0)
            weight = r.get("emotion_weight", 1.0) or 1.0
            r["weighted_score"] = sim * weight
        raw.sort(key=lambda x: x["weighted_score"], reverse=True)
        return raw[:limit]
    except Exception as e:
        print(f"[VECMEM] Recall error: {e}")
        return []


def build_context(text: str, patient_id: str = "default") -> str:
    """Build a context string from similar past conversations.
    This gets injected into the LLM prompt so it knows what was
    discussed before in similar contexts."""
    memories = recall(text, patient_id, limit=5)
    if not memories:
        return ""
    parts = []
    for m in memories:
        score = m.get("weighted_score", m.get("similarity", 0))
        if score < 0.2:  # skip low-relevance matches
            continue
        speaker = m.get("speaker", "patient")
        txt = m.get("text", "")[:120]
        emotion = m.get("emotion", "")
        when = m.get("created_at", "")
        prefix = "Patient said" if speaker == "patient" else "You said"
        entry = f"{prefix}: \"{txt}\""
        if emotion:
            entry += f" (feeling {emotion})"
        parts.append(entry)
    if parts:
        return "Related past conversations: " + " | ".join(parts[:4])
    return ""


def get_stats(patient_id: str = "default") -> dict:
    """Get vector memory stats."""
    try:
        import db_supabase as _db
        count = _db.get_memory_vector_count(patient_id)
        return {"total_memories": count, "model": _model, "dimensions": 1536}
    except Exception:
        return {"total_memories": 0}


def summarize_session(conversation_turns: list, patient_id: str = "default") -> str:
    """Use GPT to summarize a conversation session into a paragraph.
    This gets stored and loaded at the start of the next session so
    the bot has continuity without replaying every message.

    conversation_turns: list of (speaker, text, emotion) tuples
    """
    if not _available or not _client:
        return ""
    if len(conversation_turns) < 3:
        return ""
    try:
        # Build the conversation text
        lines = []
        for speaker, text, emotion in conversation_turns[-30:]:  # last 30 turns max
            label = "Patient" if speaker == "patient" else "Reachy"
            lines.append(f"{label} ({emotion}): {text}")
        convo_text = "\n".join(lines)

        resp = _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "Summarize this conversation between an elderly patient and their robot companion Reachy. "
                    "Write 2-3 sentences covering: main topics discussed, patient's emotional state, "
                    "any important facts learned about the patient, and anything the bot should follow up on next time. "
                    "Write from Reachy's perspective, like notes for next session."
                )},
                {"role": "user", "content": convo_text},
            ],
            max_tokens=200,
            temperature=0.3,
        )
        summary = resp.choices[0].message.content.strip()

        # Store the summary with an embedding for future retrieval
        import db_supabase as _db
        if _db.is_available():
            embedding = _get_embedding(summary)
            if embedding:
                _db.save_memory_vector(
                    f"[SESSION SUMMARY] {summary}",
                    embedding, speaker="system", emotion="",
                    topic="session_summary", patient_id=patient_id,
                    emotion_weight=2.0)  # high weight so summaries rank high
            print(f"[VECMEM] Session summary stored: {summary[:80]}...")
        return summary
    except Exception as e:
        print(f"[VECMEM] Summarize error: {e}")
        return ""
