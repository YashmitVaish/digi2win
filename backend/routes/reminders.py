from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.db import Reminder, get_db

router = APIRouter(prefix="/reminders", tags=["reminders"])


class ReminderCreate(BaseModel):
    title: str
    due_at: datetime | None = None
    done: bool = False


class ReminderUpdate(BaseModel):
    title: str | None = None
    due_at: datetime | None = None
    done: bool | None = None


def _serialize(row: Reminder) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "due_at": row.due_at,
        "done": bool(row.done),
        "created_at": row.created_at,
    }


@router.get("")
def list_reminders(
    done: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Reminder).order_by(Reminder.created_at.desc())
    if done is not None:
        query = query.filter(Reminder.done == done)
    rows = query.offset(offset).limit(limit).all()
    return [_serialize(row) for row in rows]


@router.post("")
def create_reminder(payload: ReminderCreate, db: Session = Depends(get_db)):
    row = Reminder(
        title=payload.title,
        due_at=payload.due_at,
        done=payload.done,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.patch("/{reminder_id}")
def update_reminder(reminder_id: str, payload: ReminderUpdate, db: Session = Depends(get_db)):
    row = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Reminder not found")

    if payload.title is not None:
        row.title = payload.title
    if payload.due_at is not None:
        row.due_at = payload.due_at
    if payload.done is not None:
        row.done = payload.done

    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.delete("/{reminder_id}")
def delete_reminder(reminder_id: str, db: Session = Depends(get_db)):
    row = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Reminder not found")

    db.delete(row)
    db.commit()
    return {"ok": True}
