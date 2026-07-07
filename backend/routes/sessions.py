from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db.db import ChatSession, Conversation, get_db

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    title: str = Field(default="New chat", min_length=1)


class SessionUpdate(BaseModel):
    title: str | None = None
    archived: bool | None = None


def _serialize_session(row: ChatSession) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "archived": bool(row.archived),
        "created_at": row.created_at,
        "last_active_at": row.last_active_at,
    }


@router.get("")
def list_sessions(
    archived: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(ChatSession)
    if archived is not None:
        query = query.filter(ChatSession.archived == archived)

    rows = (
        query.order_by(ChatSession.last_active_at.desc(), ChatSession.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_serialize_session(row) for row in rows]


@router.post("")
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="title cannot be blank")
    row = ChatSession(title=title, archived=False)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_session(row)


@router.get("/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    row = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _serialize_session(row)


@router.get("/{session_id}/messages")
def get_session_messages(
    session_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    session_row = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session_row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    rows = (
        db.query(Conversation)
        .filter(Conversation.session_id == session_id)
        .order_by(Conversation.created_at.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": row.id,
            "session_id": row.session_id,
            "role": row.role,
            "content": row.content,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.patch("/{session_id}")
def update_session(session_id: str, payload: SessionUpdate, db: Session = Depends(get_db)):
    row = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=422, detail="title cannot be blank")
        row.title = title
    if payload.archived is not None:
        row.archived = payload.archived

    row.last_active_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _serialize_session(row)


@router.delete("/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    row = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    db.query(Conversation).filter(Conversation.session_id == session_id).delete()
    db.delete(row)
    db.commit()
    return {"ok": True}
