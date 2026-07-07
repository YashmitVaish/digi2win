from sqlalchemy.orm import Session

from backend.db.db import Conversation, Memory, Profile
from backend.services.retrieve import retrieve

SYSTEM_PROMPT = """You are Twin, a personal AI assistant.
You have persistent memory of the user's goals, preferences, and life.
Answer based on the retrieved context. If context is missing, say so honestly.
Never make up facts about the user."""

def build_context_bundle(query: str, db: Session, session_id: str | None = None) -> str:
    memories = retrieve(query, top_k=5, db=db)

    profile = db.query(Profile).all()
    profile_str = "\n".join(f"- {p.key}: {p.value}" for p in profile)

    recent_events = (
        db.query(Memory)
        .filter(Memory.type == "event")
        .order_by(Memory.created_at.desc())
        .limit(5)
        .all()
    )
    recent_events_str = "\n".join(f"- {event.content}" for event in recent_events)

    turns_query = db.query(Conversation)
    if session_id:
        turns_query = turns_query.filter(Conversation.session_id == session_id)

    recent_turns = turns_query.order_by(Conversation.created_at.desc()).limit(6).all()
    recent_turns.reverse()
    recent_turns_str = "\n".join(f"- {turn.role}: {turn.content}" for turn in recent_turns)

    memory_str = "\n".join(
        f"[{m['type']}] {m['content']}" for m in memories
    )

    return f"""PROFILE FACTS:
        {profile_str or 'None yet.'}

        RECENT EVENTS:
        {recent_events_str or 'None yet.'}

        RECENT CONVERSATION TURNS:
        {recent_turns_str or 'None yet.'}

        RELEVANT MEMORIES (ranked by importance × recency):
        {memory_str or 'None yet.'}

        USER QUERY: {query}"""
