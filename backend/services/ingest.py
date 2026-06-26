from chromadb.errors import InvalidArgumentError
from sqlalchemy.orm import Session
import uuid

from backend.db.chroma import get_collection
from backend.db.db import Memory, SessionLocal
from backend.services.embeddings import embed
from backend.util.memory import classify_memory_type, emotional_weight

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
                chunks.append(candidate[:max_chars].strip())
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
    chunks = chunk_text(content)
    owns_session = db is None
    session = db or SessionLocal()

    try:
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

        session.commit()
        return len(chunks)
    finally:
        if owns_session:
            session.close()
