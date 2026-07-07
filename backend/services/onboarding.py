from sqlalchemy.orm import Session

from backend.db.db import OnboardingState, Profile
from backend.services.ingest import ingest
from backend.util.prof import extract_profile_facts

ONBOARDING_QUESTIONS = [
    {
        "key": "identity",
        "question": "Give me a quick intro: what should I call you, what do you do, and what's your current season of life?",
        "memory_type": "fact",
        "profile_extract": True,
    },
    {
        "key": "goals",
        "question": "What are the top 2-3 outcomes you want to achieve in the next 30-90 days?",
        "memory_type": "goal",
        "profile_extract": False,
    },
    {
        "key": "preferences",
        "question": "How do you like to work and make decisions? (planning style, focus hours, tools, constraints)",
        "memory_type": "preference",
        "profile_extract": True,
    },
    {
        "key": "routine",
        "question": "What does a typical week look like, including recurring commitments and energy highs/lows?",
        "memory_type": "event",
        "profile_extract": False,
    },
    {
        "key": "assistant_style",
        "question": "How should Twin respond so you keep using it? (tone, length, directness, reminders, accountability style)",
        "memory_type": "style",
        "profile_extract": True,
    },
]


def get_or_create_state(db: Session) -> OnboardingState:
    state = db.query(OnboardingState).order_by(OnboardingState.updated_at.desc()).first()
    if state is None:
        state = OnboardingState(current_step=0, completed=False)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def _step_payload(state: OnboardingState) -> dict:
    total = len(ONBOARDING_QUESTIONS)
    if state.completed:
        return {
            "completed": True,
            "current_step": total,
            "total_steps": total,
            "progress_pct": 100,
            "question_key": None,
            "question": None,
        }

    step = max(0, min(state.current_step, total - 1))
    question = ONBOARDING_QUESTIONS[step]
    return {
        "completed": False,
        "current_step": step + 1,
        "total_steps": total,
        "progress_pct": int((step / total) * 100),
        "question_key": question["key"],
        "question": question["question"],
    }


def get_current_step(db: Session) -> dict:
    state = get_or_create_state(db)
    return _step_payload(state)


def _build_completion_payload(db: Session) -> dict:
    profile_rows = db.query(Profile).all()
    profile_snapshot = {row.key: row.value for row in profile_rows}
    highlights = [
        f"{key}: {value}"
        for key, value in list(profile_snapshot.items())[:3]
    ]
    return {
        "completed": True,
        "current_step": len(ONBOARDING_QUESTIONS),
        "total_steps": len(ONBOARDING_QUESTIONS),
        "progress_pct": 100,
        "profile_highlights": highlights,
        "next_action": "Ask: What should I focus on today?",
        "integrations_available": ["calendar", "gmail"],
    }


def submit_answer(db: Session, answer: str) -> dict:
    state = get_or_create_state(db)
    if state.completed:
        return _build_completion_payload(db)

    step = max(0, min(state.current_step, len(ONBOARDING_QUESTIONS) - 1))
    question = ONBOARDING_QUESTIONS[step]

    ingest(answer, memory_type=question["memory_type"], importance=1.0, db=db)

    if question["profile_extract"]:
        extract_profile_facts(answer, db)

    if step + 1 >= len(ONBOARDING_QUESTIONS):
        state.current_step = len(ONBOARDING_QUESTIONS)
        state.completed = True
        db.commit()
        db.refresh(state)
        return _build_completion_payload(db)

    state.current_step = step + 1
    db.commit()
    db.refresh(state)
    return _step_payload(state)
