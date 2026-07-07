from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.db.db import Profile, get_db

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
def list_profile(db: Session = Depends(get_db)):
    rows = db.query(Profile).order_by(Profile.key.asc()).all()
    return [
        {
            "key": row.key,
            "value": row.value,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]
