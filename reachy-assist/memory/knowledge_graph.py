"""Knowledge Graph — builds a web of relationships from patient conversations.

Instead of flat mentions like "my daughter", this builds structured knowledge:
  Sarah → is_a → daughter
  Sarah → lives_in → Portland
  Sarah → visits → on weekends
  Sarah → makes_patient_feel → happy

The graph grows with every conversation and gives the LLM deep understanding
of the patient's world.
"""

import json

_available = False
_client = None


def init():
    """Initialize OpenAI client for entity extraction."""
    global _client, _available
    try:
        from openai import OpenAI
        _client = OpenAI()
        _available = True
        print("[KNOWLEDGE] Knowledge graph initialized")
        return True
    except Exception as e:
        print(f"[KNOWLEDGE] Not available: {e}")
        return False


def is_available() -> bool:
    return _available


_EXTRACT_PROMPT = """Extract entities and relationships from what an elderly patient said.

Return JSON with two arrays:
1. "entities" — each has "name" (lowercase), "type" (person/place/pet/activity/food/object/event), and "attributes" (dict of known properties like age, location, etc.)
2. "relations" — each has "subject", "relation", "object". Use simple relation names like: is_a, lives_in, works_at, enjoys, has_pet, married_to, child_of, parent_of, friend_of, visits, makes_feel, happened_at, likes, dislikes, used_to, diagnosed_with

Examples:
Input: "My daughter Sarah lives in Portland and visits every Sunday"
Output: {"entities": [{"name": "sarah", "type": "person", "attributes": {"location": "portland", "visits": "every sunday"}}], "relations": [{"subject": "sarah", "relation": "is_a", "object": "daughter"}, {"subject": "sarah", "relation": "lives_in", "object": "portland"}, {"subject": "sarah", "relation": "visits", "object": "every sunday"}]}

Input: "I used to teach at Lincoln Elementary for 30 years"
Output: {"entities": [{"name": "lincoln elementary", "type": "place", "attributes": {"type": "school"}}], "relations": [{"subject": "patient", "relation": "used_to", "object": "teach"}, {"subject": "patient", "relation": "works_at", "object": "lincoln elementary"}]}

Only extract what's clearly stated. If nothing meaningful, return {"entities": [], "relations": []}.
Keep entity names short and lowercase."""


def extract_and_store(text: str, patient_id: str = "default") -> dict:
    """Use GPT to extract entities and relationships, then store in Supabase."""
    if not _available or not _client:
        return {"entities": [], "relations": []}
    try:
        import memory.db_supabase as _db
        if not _db.is_available():
            return {"entities": [], "relations": []}

        resp = _client.chat.completions.create(
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
        data = json.loads(raw)

        entities = data.get("entities", [])
        relations = data.get("relations", [])

        for e in entities:
            name = e.get("name", "").strip()
            etype = e.get("type", "unknown").strip()
            attrs = e.get("attributes", {})
            if name and len(name) > 1:
                _db.save_entity(name, etype, attrs, patient_id)

        for r in relations:
            subj = r.get("subject", "").strip()
            rel = r.get("relation", "").strip()
            obj = r.get("object", "").strip()
            if subj and rel and obj:
                _db.save_relation(subj, rel, obj, source_text=text, patient_id=patient_id)

        if entities or relations:
            print(f"[KNOWLEDGE] Extracted {len(entities)} entities, {len(relations)} relations")
        return data
    except Exception as e:
        print(f"[KNOWLEDGE] Extract error: {e}")
        return {"entities": [], "relations": []}


def build_context(patient_id: str = "default") -> str:
    """Build a context string from the knowledge graph for the LLM.
    Returns something like:
    'People: sarah (daughter, lives in portland, visits sundays);
     Places: lincoln elementary (school, patient worked there);
     Patient: used to teach, enjoys gardening'
    """
    try:
        import memory.db_supabase as _db
        if not _db.is_available():
            return ""

        entities = _db.get_all_entities(patient_id)
        relations = _db.get_all_relations(patient_id)

        if not entities and not relations:
            return ""

        # Group entities by type
        by_type = {}
        for e in entities:
            t = e["entity_type"]
            if t not in by_type:
                by_type[t] = []
            attrs = e.get("attributes", {})
            if isinstance(attrs, str):
                attrs = json.loads(attrs) if attrs else {}
            by_type[t].append({"name": e["name"], "attrs": attrs})

        # Build relation lookup: subject -> [(relation, object)]
        rel_map = {}
        for r in relations:
            subj = r["subject"]
            if subj not in rel_map:
                rel_map[subj] = []
            rel_map[subj].append((r["relation"], r["object"]))

        parts = []

        # Describe each entity type
        for etype, ents in by_type.items():
            descs = []
            for e in ents[:6]:  # limit per type
                name = e["name"]
                bits = [name]
                # Add attributes
                for k, v in list(e["attrs"].items())[:3]:
                    bits.append(f"{k}: {v}")
                # Add relations
                rels = rel_map.get(name, [])
                for rel, obj in rels[:4]:
                    bits.append(f"{rel.replace('_', ' ')} {obj}")
                descs.append(f"{' — '.join(bits)}")
            if descs:
                parts.append(f"{etype}s: {'; '.join(descs)}")

        # Patient-specific relations
        patient_rels = rel_map.get("patient", [])
        if patient_rels:
            pr = [f"{rel.replace('_', ' ')} {obj}" for rel, obj in patient_rels[:6]]
            parts.append(f"about patient: {', '.join(pr)}")

        if parts:
            return "Knowledge graph: " + " | ".join(parts)
        return ""
    except Exception as e:
        print(f"[KNOWLEDGE] Context build error: {e}")
        return ""


def describe_entity(name: str, patient_id: str = "default") -> str:
    """Get a human-readable description of a specific entity."""
    try:
        import memory.db_supabase as _db
        entity = _db.get_entity(name, patient_id)
        if not entity:
            return ""
        relations = _db.get_relations_for(name, patient_id)
        parts = [f"{entity['name']} ({entity['entity_type']})"]
        attrs = entity.get("attributes", {})
        if isinstance(attrs, str):
            attrs = json.loads(attrs) if attrs else {}
        for k, v in attrs.items():
            parts.append(f"{k}: {v}")
        for r in relations:
            if r["subject"] == name.lower():
                parts.append(f"{r['relation'].replace('_', ' ')} {r['object']}")
            else:
                parts.append(f"{r['subject']} {r['relation'].replace('_', ' ')} them")
        return " — ".join(parts)
    except Exception:
        return ""
