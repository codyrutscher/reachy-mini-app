"""RAG memory system — persistent cross-session memory for Reachy.

Stores conversation snippets, patient facts, and care events in a
SQLite vector store. Uses OpenAI embeddings (preferred) or a
hash-based fallback for vector similarity.
At query time, retrieves the most relevant memories to inject into
the LLM context, making Reachy remember across sessions.

Memory types:
- fact: personal info (name, family, pets, career, preferences)
- conversation: notable conversation snippets worth remembering
- event: care events (medication taken, exercise done, mood episode)
- preference: likes, dislikes, routines
"""

import json
import os
import sqlite3
import threading
import time
from datetime import datetime

import numpy as np

MEMORY_DB = os.environ.get(
    "REACHY_MEMORY_DB",
    os.path.join(os.path.dirname(__file__), "memory.db"),
)

_local = threading.local()
_embedder = None
_embedder_lock = threading.Lock()
EMBED_DIM = 384  # default dimension for local model
_embed_backend = None  # "openai" or "local"


def _get_embedder():
    """Lazy-load the embedding backend. Prefers OpenAI if API key is set,
    falls back to hash-based embeddings."""
    global _embedder, _embed_backend, EMBED_DIM
    if _embedder is not None:
        return _embedder

    with _embedder_lock:
        if _embedder is not None:
            return _embedder

        # Try OpenAI embeddings first (fast, no local model needed)
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if api_key:
            try:
                from openai import OpenAI
                _embedder = OpenAI()
                _embed_backend = "openai"
                EMBED_DIM = 1536  # text-embedding-3-small
                print("[MEMORY] Using OpenAI embeddings")
                return _embedder
            except Exception as e:
                print(f"[MEMORY] OpenAI embeddings failed: {e}")

        # Hash-based fallback: deterministic, no dependencies
        _embed_backend = "hash"
        _embedder = "hash"
        EMBED_DIM = 128
        print("[MEMORY] Using hash-based embeddings (no semantic search)")
        return _embedder


def _get_conn():
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(MEMORY_DB, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
    return _local.conn


def init_memory_db():
    """Create the memory tables."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT DEFAULT 'default',
            memory_type TEXT NOT NULL,
            content TEXT NOT NULL,
            embedding BLOB,
            importance REAL DEFAULT 0.5,
            access_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            last_accessed TEXT,
            metadata TEXT DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_memories_patient
            ON memories(patient_id);
        CREATE INDEX IF NOT EXISTS idx_memories_type
            ON memories(patient_id, memory_type);

        CREATE TABLE IF NOT EXISTS session_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT DEFAULT 'default',
            summary TEXT NOT NULL,
            mood_distribution TEXT DEFAULT '{}',
            facts_learned TEXT DEFAULT '[]',
            duration_minutes REAL DEFAULT 0,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    print(f"[MEMORY] Database ready: {MEMORY_DB}")


def _embed(text: str) -> bytes:
    """Embed text and return as bytes for SQLite storage."""
    model = _get_embedder()

    if _embed_backend == "openai":
        resp = model.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        vec = np.array(resp.data[0].embedding, dtype=np.float32)
        # Normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tobytes()

    else:
        # Hash-based fallback: deterministic but no semantic similarity
        import hashlib
        h = hashlib.sha256(text.lower().encode()).digest()
        # Expand hash to EMBED_DIM floats
        vec = np.frombuffer(h * (EMBED_DIM // 32 + 1), dtype=np.uint8)[:EMBED_DIM].astype(np.float32)
        vec = vec / (np.linalg.norm(vec) + 1e-8)
        return vec.tobytes()


def _bytes_to_vec(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32)


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    # Vectors are already normalized, so dot product = cosine similarity
    return float(np.dot(a, b))


# ── Store memories ──────────────────────────────────────────────────

def store_memory(
    content: str,
    memory_type: str = "fact",
    patient_id: str = "default",
    importance: float = 0.5,
    metadata: dict = None,
):
    """Store a new memory with its embedding."""
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Check for near-duplicates before storing
    existing = recall(content, patient_id=patient_id, top_k=1, threshold=0.85)
    if existing:
        # Update access count instead of duplicating
        conn.execute(
            "UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
            (now, existing[0]["id"]),
        )
        conn.commit()
        return existing[0]["id"]

    embedding = _embed(content)
    meta_json = json.dumps(metadata or {})

    cur = conn.execute(
        """INSERT INTO memories
           (patient_id, memory_type, content, embedding, importance, created_at, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (patient_id, memory_type, content, embedding, importance, now, meta_json),
    )
    conn.commit()
    print(f"[MEMORY] Stored ({memory_type}): {content[:60]}")
    return cur.lastrowid


def recall(
    query: str,
    patient_id: str = "default",
    top_k: int = 5,
    memory_type: str = None,
    threshold: float = 0.3,
) -> list[dict]:
    """Retrieve the most relevant memories for a query."""
    conn = _get_conn()
    query_vec = _embed(query)
    query_np = _bytes_to_vec(query_vec)

    # Fetch all memories for this patient
    if memory_type:
        rows = conn.execute(
            "SELECT * FROM memories WHERE patient_id = ? AND memory_type = ?",
            (patient_id, memory_type),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM memories WHERE patient_id = ?",
            (patient_id,),
        ).fetchall()

    if not rows:
        return []

    # Score each memory: cosine similarity * importance * recency boost
    scored = []
    for row in rows:
        if not row["embedding"]:
            continue
        mem_vec = _bytes_to_vec(row["embedding"])
        sim = _cosine_sim(query_np, mem_vec)

        # Recency boost: memories from today get a small boost
        try:
            created = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
            age_hours = (datetime.now() - created).total_seconds() / 3600
            recency = max(0, 1.0 - (age_hours / 720))  # decays over 30 days
        except (ValueError, TypeError):
            recency = 0.5

        # Final score: similarity (70%) + importance (20%) + recency (10%)
        score = sim * 0.7 + row["importance"] * 0.2 + recency * 0.1

        if sim >= threshold:
            scored.append({
                "id": row["id"],
                "content": row["content"],
                "memory_type": row["memory_type"],
                "importance": row["importance"],
                "similarity": round(sim, 3),
                "score": round(score, 3),
                "created_at": row["created_at"],
                "access_count": row["access_count"],
                "metadata": json.loads(row["metadata"] or "{}"),
            })

    # Sort by score, return top_k
    scored.sort(key=lambda x: x["score"], reverse=True)

    # Update access counts
    for mem in scored[:top_k]:
        conn.execute(
            "UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), mem["id"]),
        )
    conn.commit()

    return scored[:top_k]


def build_memory_context(query: str, patient_id: str = "default", max_tokens: int = 300) -> str:
    """Build a context string from relevant memories for LLM injection."""
    memories = recall(query, patient_id=patient_id, top_k=8, threshold=0.25)
    if not memories:
        return ""

    # Group by type for cleaner context
    by_type = {}
    for m in memories:
        t = m["memory_type"]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(m["content"])

    parts = []
    type_labels = {
        "fact": "Things you know about them",
        "conversation": "From past conversations",
        "event": "Recent care events",
        "preference": "Their preferences",
    }

    for mtype, items in by_type.items():
        label = type_labels.get(mtype, mtype.capitalize())
        items_str = "; ".join(items[:3])  # max 3 per type
        parts.append(f"{label}: {items_str}")

    context = " | ".join(parts)
    # Rough token limit
    if len(context) > max_tokens * 4:
        context = context[: max_tokens * 4]
    return context


# ── Session summaries ───────────────────────────────────────────────

def save_session_summary(
    summary: str,
    mood_distribution: dict = None,
    facts_learned: list = None,
    duration_minutes: float = 0,
    patient_id: str = "default",
):
    """Save a session summary for long-term reference."""
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """INSERT INTO session_summaries
           (patient_id, summary, mood_distribution, facts_learned, duration_minutes, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            patient_id,
            summary,
            json.dumps(mood_distribution or {}),
            json.dumps(facts_learned or []),
            duration_minutes,
            now,
        ),
    )
    conn.commit()

    # Also store the summary as a memory for future retrieval
    store_memory(
        f"Session summary ({now[:10]}): {summary}",
        memory_type="event",
        patient_id=patient_id,
        importance=0.7,
    )


def get_recent_summaries(patient_id: str = "default", limit: int = 5) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM session_summaries WHERE patient_id = ? ORDER BY id DESC LIMIT ?",
        (patient_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Automatic fact extraction and storage ───────────────────────────

def process_conversation_turn(
    user_text: str,
    reachy_response: str,
    emotion: str,
    patient_id: str = "default",
):
    """Process a conversation turn — extract and store relevant memories."""
    lower = user_text.lower()

    # Store notable emotional moments
    if emotion in ("sadness", "fear", "anger") and len(user_text) > 20:
        store_memory(
            f"Patient expressed {emotion}: {user_text[:100]}",
            memory_type="event",
            patient_id=patient_id,
            importance=0.6,
            metadata={"emotion": emotion},
        )

    # Store personal facts
    fact_triggers = {
        "family": ["my daughter", "my son", "my wife", "my husband",
                    "my sister", "my brother", "my mother", "my father",
                    "my grandchild", "my grandson", "my granddaughter",
                    "my family"],
        "pet": ["my dog", "my cat", "my bird", "my pet",
                "i have a dog", "i have a cat"],
        "career": ["i used to be", "i was a", "i worked as",
                    "i retired from", "my job"],
        "interest": ["i love", "i enjoy", "my hobby",
                      "i like to", "i'm passionate about"],
        "health": ["i have diabetes", "i have arthritis",
                    "my back hurts", "i take medication for",
                    "i was diagnosed", "my doctor said"],
        "preference": ["my favorite", "i prefer", "i always",
                        "i never liked", "i don't like"],
        "location": ["i live in", "i lived in", "i grew up in",
                      "i'm from", "my home"],
    }

    for category, triggers in fact_triggers.items():
        for trigger in triggers:
            if trigger in lower:
                idx = lower.index(trigger)
                snippet = user_text[idx:idx + 100].split(".")[0].strip()
                if len(snippet) > 10:
                    store_memory(
                        snippet,
                        memory_type="fact",
                        patient_id=patient_id,
                        importance=0.8,
                        metadata={"category": category},
                    )
                break

    # Store care events
    care_events = {
        "took my medication": ("medication_taken", 0.7),
        "took my medicine": ("medication_taken", 0.7),
        "went for a walk": ("exercise", 0.5),
        "did my exercises": ("exercise", 0.5),
        "slept well": ("sleep_good", 0.4),
        "didn't sleep": ("sleep_bad", 0.6),
        "fell down": ("fall", 0.9),
        "in pain": ("pain", 0.8),
    }

    for trigger, (event_type, importance) in care_events.items():
        if trigger in lower:
            store_memory(
                f"Patient {trigger} ({datetime.now().strftime('%m/%d')})",
                memory_type="event",
                patient_id=patient_id,
                importance=importance,
                metadata={"event_type": event_type},
            )
            break


def get_memory_stats(patient_id: str = "default") -> dict:
    """Get stats about stored memories."""
    conn = _get_conn()
    total = conn.execute(
        "SELECT COUNT(*) FROM memories WHERE patient_id = ?", (patient_id,)
    ).fetchone()[0]
    by_type = conn.execute(
        "SELECT memory_type, COUNT(*) as cnt FROM memories WHERE patient_id = ? GROUP BY memory_type",
        (patient_id,),
    ).fetchall()
    sessions = conn.execute(
        "SELECT COUNT(*) FROM session_summaries WHERE patient_id = ?", (patient_id,)
    ).fetchone()[0]
    return {
        "total_memories": total,
        "by_type": {r["memory_type"]: r["cnt"] for r in by_type},
        "total_sessions": sessions,
    }
