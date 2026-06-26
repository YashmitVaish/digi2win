import os

import httpx
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from openai import OpenAI

from backend.db.db import Conversation, get_db
from backend.services.context import SYSTEM_PROMPT, build_context_bundle
from backend.services.ingest import ingest
from backend.util.prof import extract_profile_facts
from backend.util.sanitize import sanitise

app = FastAPI()
oai = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

class ChatRequest(BaseModel):
    message: str
    mode: str = "auto"


def _ollama_chat(messages: list[dict[str, str]]) -> str:
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    chat_model = os.getenv("OLLAMA_CHAT_MODEL", "mistral:7b")
    resp = httpx.post(
        f"{ollama_url}/api/chat",
        json={"model": chat_model, "messages": messages, "stream": False},
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _cloud_chat(messages: list[dict[str, str]]) -> str:
    if oai is None:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY is not set for cloud mode")
    completion = oai.chat.completions.create(model="gpt-4o", messages=messages)
    return completion.choices[0].message.content or ""


def choose_mode(requested_mode: str) -> str:
    if requested_mode in {"local", "cloud"}:
        return requested_mode

    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    try:
        resp = httpx.get(f"{ollama_url}/api/tags", timeout=2)
        if resp.status_code == 200:
            return "local"
    except Exception:
        pass

    if oai is not None:
        return "cloud"
    return "local"

@app.post("/chat")
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    context = build_context_bundle(req.message, db)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": context},
    ]

    mode = choose_mode(req.mode)

    if mode == "local":
        try:
            reply = _ollama_chat(messages)
        except Exception as exc:
            if req.mode == "auto" and oai is not None:
                messages[-1]["content"] = sanitise(context)
                reply = _cloud_chat(messages)
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
        reply = _cloud_chat(messages)
    else:
        raise HTTPException(status_code=400, detail="mode must be 'local', 'cloud', or 'auto'")

    extract_profile_facts(req.message, db)
    ingest(req.message, memory_type="auto", importance=1.0, db=db)

    db.add(Conversation(role="user",      content=req.message))
    db.add(Conversation(role="assistant", content=reply))
    db.commit()

    return {"reply": reply, "mode_used": mode}
