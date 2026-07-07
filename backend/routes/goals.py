from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db.db import Memory, get_db
from backend.services.ingest import ingest

router = APIRouter(prefix="/goals", tags=["goals"])


class GoalCreate(BaseModel):
    content: str = Field(min_length=1)
    importance: float = Field(default=1.0, gt=0)


def _serialize_goal(row: Memory) -> dict:
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
def list_goals(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Memory)
        .filter(Memory.type == "goal")
        .order_by(Memory.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_serialize_goal(row) for row in rows]


@router.post("")
def create_goal(payload: GoalCreate, db: Session = Depends(get_db)):
    chunks_ingested = ingest(
        payload.content,
        memory_type="goal",
        importance=payload.importance,
        db=db,
    )
    return {"ok": True, "ingested_chunks": chunks_ingested}
