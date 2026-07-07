import re
import uuid

from chromadb.errors import InvalidArgumentError
from sqlalchemy.orm import Session

from backend.db.chroma import get_collection
from backend.db.db import Memory, SessionLocal
from backend.services.embeddings import embed
from backend.util.memory import classify_memory_type, emotional_weight

_ACTION_VERBS = (
    "build",
    "create",
    "finish",
    "get",
    "improve",
    "launch",
    "learn",
    "make",
    "maintain",
    "reduce",
    "ship",
    "start",
    "stop",
    "study",
    "write",
)


def _clean_segment(value: str) -> str:
    segment = value.strip()
    segment = re.sub(r"^(?:[-*]|\d+[.)])\s*", "", segment)
    segment = re.sub(r"\s+", " ", segment)
    return segment.strip(" ,;")


def _split_sentences(value: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", value) if part.strip()]
    return parts or [value.strip()]


def _looks_like_goal_fragment(value: str) -> bool:
    low = value.lower()
    if "want to" in low or "need to" in low or "plan to" in low:
        return True
    if low.startswith("to "):
        return True
    return any(low.startswith(f"{verb} ") for verb in _ACTION_VERBS)


def _split_goal_clauses(value: str) -> list[str]:
    clauses = [_clean_segment(part) for part in re.split(r",\s+", value) if _clean_segment(part)]
    if len(clauses) <= 1:
        return [value]

    goal_like = [part for part in clauses if _looks_like_goal_fragment(part)]
    if len(goal_like) >= 2:
        return clauses

    return [value]


def _split_compound_goals(value: str) -> list[str]:
    verb_pattern = "|".join(_ACTION_VERBS)
    parts = [
        part.strip()
        for part in re.split(rf"\s+(?=(?:{verb_pattern})\b)", value, flags=re.IGNORECASE)
        if part.strip()
    ]
    return parts if len(parts) > 1 else [value]


def split_memory_content(content: str, memory_type: str = "auto") -> list[str]:
    raw_parts = [part for part in re.split(r"\n+|[;•]+", content) if part.strip()]
    parts = [_clean_segment(part) for part in raw_parts]
    parts = [part for part in parts if len(part) >= 4]

    if not parts:
        fallback = content.strip()
        return [fallback] if fallback else []

    if memory_type in {"goal", "preference", "style", "event"}:
        expanded: list[str] = []
        for part in parts:
            expanded.extend(_split_sentences(part))
        parts = [_clean_segment(part) for part in expanded if _clean_segment(part)]
    elif memory_type == "auto":
        parts = [_clean_segment(part) for part in parts if _clean_segment(part)]

    if memory_type == "goal":
        expanded_goals: list[str] = []
        for part in parts:
            expanded_goals.extend(_split_goal_clauses(part))

        if len(expanded_goals) == 1:
            expanded_goals = _split_compound_goals(expanded_goals[0])

        parts = [_clean_segment(part) for part in expanded_goals if _clean_segment(part)]

    deduped: list[str] = []
    seen: set[str] = set()
    for part in parts:
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(part)

    return deduped


def _split_long_segment(text: str, max_chars: int) -> list[str]:
    words = [word for word in text.split() if word]
    if not words:
        return [text[:max_chars].strip()] if text.strip() else []

    parts: list[str] = []
    current = ""

    for word in words:
        if len(word) > max_chars:
            if current:
                parts.append(current)
                current = ""
            start = 0
            while start < len(word):
                parts.append(word[start : start + max_chars])
                start += max_chars
            continue

        if not current:
            current = word
            continue

        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            parts.append(current)
            current = word

    if current:
        parts.append(current)
    return parts

def chunk_text(text: str, max_chars: int = 260) -> list[str]:
    """Paragraph-first chunking to reduce mixed memory types per chunk."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []

    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            chunks.append(paragraph)
            continue

        sentences = [s.strip() for s in paragraph.split(".") if s.strip()]
        current = ""
        for sentence in sentences:
            candidate = f"{sentence}."
            if len(candidate) > max_chars:
                if current:
                    chunks.append(current.strip())
                    current = ""
                chunks.extend(_split_long_segment(candidate, max_chars))
                continue

            if not current:
                current = candidate
            elif len(current) + 1 + len(candidate) <= max_chars:
                current = f"{current} {candidate}"
            else:
                chunks.append(current.strip())
                current = candidate

        if current:
            chunks.append(current.strip())

    return chunks

def ingest(
    content: str,
    memory_type: str = "auto",
    importance: float = 1.0,
    db: Session | None = None,
):
    collection = get_collection()
    memory_units = split_memory_content(content, memory_type=memory_type)
    owns_session = db is None
    session = db or SessionLocal()
    total_chunks = 0

    try:
        for unit in memory_units:
            chunks = chunk_text(unit)
            for chunk in chunks:
                embedding_id = str(uuid.uuid4())
                vec = embed(chunk)
                resolved_type, confidence = classify_memory_type(chunk, requested_type=memory_type)
                emo_weight = emotional_weight(chunk)

                try:
                    collection.add(
                        ids=[embedding_id],
                        embeddings=[vec],
                        documents=[chunk],
                        metadatas=[
                            {
                                "id": embedding_id,
                                "type": resolved_type,
                                "importance": importance,
                                "confidence": confidence,
                                "emotional_weight": emo_weight,
                            }
                        ],
                    )
                except InvalidArgumentError as exc:
                    if "dimension" in str(exc).lower():
                        raise RuntimeError(
                            "Embedding dimension mismatch. Your existing Chroma collection was created with a "
                            "different embedding model. Re-run with --reset-chroma to rebuild the vector store."
                        ) from exc
                    raise
                session.add(
                    Memory(
                        content=chunk,
                        type=resolved_type,
                        importance=importance,
                        confidence=confidence,
                        emotional_weight=emo_weight,
                        embedding_id=embedding_id,
                    )
                )
                total_chunks += 1

        session.commit()
        return total_chunks
    finally:
        if owns_session:
            session.close()
