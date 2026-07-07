from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db.db import get_db
from backend.services.onboarding import get_current_step, submit_answer

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingAnswerRequest(BaseModel):
    answer: str = Field(min_length=1)


@router.get("")
def onboarding_status(db: Session = Depends(get_db)):
    return get_current_step(db)


@router.post("/answer")
def onboarding_answer(payload: OnboardingAnswerRequest, db: Session = Depends(get_db)):
    answer = payload.answer.strip()
    if not answer:
        raise HTTPException(status_code=422, detail="answer cannot be blank")

    current = get_current_step(db)
    if current["completed"]:
        raise HTTPException(status_code=409, detail="Onboarding already completed")

    return submit_answer(db, answer)
