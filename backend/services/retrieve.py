import math
from datetime import datetime

from sqlalchemy.orm import Session

from backend.db.chroma import get_collection
from backend.db.db import Memory, SessionLocal
from backend.services.embeddings import embed
from backend.util.memory import MEMORY_TYPES, query_type_boost

TYPE_WEIGHTS = {
    "goal":       1.5,
    "preference": 1.3,
    "fact":       1.0,
    "event":      0.9,
    "style":      0.8,
}

def importance_score(memory: Memory, cosine_sim: float) -> float:
    days_old = (datetime.utcnow() - memory.created_at).days
    decay = math.exp(-0.693 * days_old / 30)
    access_boost = min(memory.access_count * 0.04, 0.2)
    type_weight = TYPE_WEIGHTS.get(memory.type, 1.0)
    confidence = max(0.1, float(memory.confidence or 1.0))
    emo = float(memory.emotional_weight or 0.0)
    base = (memory.importance * type_weight) * cosine_sim
    return (base * decay * confidence) + access_boost + emo

def retrieve(
    query: str,
    top_k: int = 5,
    db: Session | None = None,
    filter_type: str | None = None,
) -> list[dict]:
    if filter_type is not None and filter_type not in MEMORY_TYPES:
        raise ValueError(f"Invalid filter_type '{filter_type}'. Must be one of: {sorted(MEMORY_TYPES)}")

    collection = get_collection()
    if collection.count() == 0:
        return []

    owns_session = db is None
    session = db or SessionLocal()
    vec = embed(query)

    query_kwargs = {
        "query_embeddings": [vec],
        "n_results": min(top_k * 5, collection.count()),
        "include": ["documents", "distances", "metadatas"],
    }
    if filter_type is not None:
        query_kwargs["where"] = {"type": filter_type}

    results = collection.query(**query_kwargs)

    docs = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    scored = []
    try:
        for doc, dist, meta in zip(docs, distances, metadatas):
            meta = meta or {}
            sim = 1 - dist

            mem = session.query(Memory).filter(Memory.embedding_id == meta.get("id", "")).first()
            if mem is None:
                mem = session.query(Memory).filter(Memory.content == doc).first()

            if mem:
                if filter_type is not None and mem.type != filter_type:
                    continue
                score = importance_score(mem, sim)
                score = score * query_type_boost(query, mem.type)
                mem.access_count += 1
                mem.last_accessed = datetime.utcnow()
                session.commit()
            else:
                if filter_type is not None and meta.get("type") != filter_type:
                    continue
                score = sim

            scored.append({"content": doc, "score": score, "type": meta.get("type", "fact")})
    finally:
        if owns_session:
            session.close()

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
