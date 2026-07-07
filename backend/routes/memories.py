from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.db.chroma import get_collection
from backend.db.db import Memory, get_db
from backend.util.memory import MEMORY_TYPES

router = APIRouter(prefix="/memories", tags=["memories"])


def _serialize_memory(row: Memory) -> dict:
    return {
        "id": row.id,
        "type": row.type,
        "content": row.content,
        "importance": row.importance,
        "confidence": row.confidence,
        "emotional_weight": row.emotional_weight,
        "access_count": row.access_count,
        "created_at": row.created_at,
        "last_accessed": row.last_accessed,
        "embedding_id": row.embedding_id,
    }


@router.get("")
def list_memories(
    type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="newest"),
    db: Session = Depends(get_db),
):
    if type is not None and type not in MEMORY_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of: {sorted(MEMORY_TYPES)}")

    if sort not in {"newest", "oldest"}:
        raise HTTPException(status_code=400, detail="sort must be 'newest' or 'oldest'")

    query = db.query(Memory)
    if type is not None:
        query = query.filter(Memory.type == type)

    if sort == "oldest":
        query = query.order_by(Memory.created_at.asc())
    else:
        query = query.order_by(Memory.created_at.desc())

    rows = query.offset(offset).limit(limit).all()
    return [_serialize_memory(row) for row in rows]


@router.delete("/{memory_id}")
def delete_memory(memory_id: str, db: Session = Depends(get_db)):
    row = db.query(Memory).filter(Memory.id == memory_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Memory not found")

    if row.embedding_id:
        collection = get_collection()
        try:
            collection.delete(ids=[row.embedding_id])
        except Exception:
            pass

    db.delete(row)
    db.commit()
    return {"ok": True}
