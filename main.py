import os
from datetime import datetime
import asyncio

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from openai import AsyncOpenAI
from dotenv import load_dotenv

from backend.db.db import ChatSession, Conversation, SessionLocal, get_db
from backend.routes.goals import router as goals_router
from backend.routes.memories import router as memories_router
from backend.routes.onboarding import router as onboarding_router
from backend.routes.profile import router as profile_router
from backend.routes.reminders import router as reminders_router
from backend.routes.sessions import router as sessions_router
from backend.services.context import SYSTEM_PROMPT, build_context_bundle
from backend.services.ingest import ingest
from backend.util.memory_filter import is_memory_worthy
from backend.util.prof import extract_profile_facts
from backend.util.sanitize import sanitise

load_dotenv()

app = FastAPI()
app.include_router(memories_router)
app.include_router(goals_router)
app.include_router(reminders_router)
app.include_router(onboarding_router)
app.include_router(sessions_router)
app.include_router(profile_router)

oai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

class ChatRequest(BaseModel):
    message: str
    mode: str = "local"
    session_id: str | None = None


def _build_context(message: str, session_id: str) -> str:
    with SessionLocal() as session:
        return build_context_bundle(message, session, session_id=session_id)


def _post_chat_processing(message: str) -> None:
    with SessionLocal() as session:
        extract_profile_facts(message, session)
        if is_memory_worthy(message):
            ingest(message, memory_type="auto", importance=1.0, db=session)


def _title_from_message(message: str) -> str:
    clean = " ".join(message.split())
    if len(clean) <= 50:
        return clean
    return f"{clean[:47]}..."


async def _ollama_chat(messages: list[dict[str, str]]) -> str:
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    chat_model = os.getenv("OLLAMA_CHAT_MODEL", "mistral:7b")
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            f"{ollama_url}/api/chat",
            json={"model": chat_model, "messages": messages, "stream": False},
        )
    resp.raise_for_status()
    return resp.json()["message"][  "content"]


async def _cloud_chat(messages: list[dict[str, str]]) -> str:
    if oai is None:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY is not set for cloud mode")
    completion = await oai.chat.completions.create(model="gpt-4o", messages=messages)
    return completion.choices[0].message.content or ""


async def choose_mode(requested_mode: str) -> str:
    if requested_mode in {"local", "cloud"}:
        return requested_mode

    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            resp = await client.get(f"{ollama_url}/api/tags")
            if resp.status_code == 200:
                return "local"
    except Exception:
        pass

    if oai is not None:
        return "cloud"
    return "local"

@app.post("/chat")
async def chat(req: ChatRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    session_row: ChatSession | None = None
    if req.session_id:
        session_row = db.query(ChatSession).filter(ChatSession.id == req.session_id).first()
        if session_row is None:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session_row = ChatSession(title="New chat", archived=False)
        db.add(session_row)
        db.commit()
        db.refresh(session_row)

    session_row.last_active_at = datetime.utcnow()
    db.commit()

    context = await asyncio.to_thread(_build_context, req.message, session_row.id)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": context},
    ]

    mode = await choose_mode(req.mode)

    if mode == "local":
        try:
            reply = await _ollama_chat(messages)
        except Exception as exc:
            if req.mode == "auto" and oai is not None:
                messages[-1]["content"] = sanitise(context)
                reply = await _cloud_chat(messages)
                mode = "cloud"
            else:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Local mode failed. Ensure Ollama is installed and running, then pull "
                        "mistral:7b and nomic-embed-text."
                    ),
                ) from exc

    elif mode == "cloud":
        messages[-1]["content"] = sanitise(context)
        reply = await _cloud_chat(messages)
    else:
        raise HTTPException(status_code=400, detail="mode must be 'local', 'cloud', or 'auto'")

    db.add(Conversation(session_id=session_row.id, role="user", content=req.message))
    db.add(Conversation(session_id=session_row.id, role="assistant", content=reply))

    if session_row.title == "New chat":
        session_row.title = _title_from_message(req.message)
    session_row.last_active_at = datetime.utcnow()
    db.commit()

    background_tasks.add_task(_post_chat_processing, req.message)

    return {"reply": reply, "mode_used": mode, "session_id": session_row.id}
