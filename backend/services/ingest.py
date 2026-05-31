from db.chroma import get_collection
from db import Memory, get_db
from openai import OpenAI
from datetime import datetime
import uuid

client = OpenAI()  # reads OPENAI_API_KEY from env

def embed(text: str) -> list[float]:
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return resp.data[0].embedding

def chunk_text(text: str, max_chars: int = 400) -> list[str]:
    """Naive sentence-aware chunker. Swap for semantic later."""
    sentences = text.replace("\n", " ").split(". ")
    chunks, current = [], ""
    for s in sentences:
        if len(current) + len(s) < max_chars:
            current += s + ". "
        else:
            if current:
                chunks.append(current.strip())
            current = s + ". "
    if current:
        chunks.append(current.strip())
    return chunks

def ingest(content: str, memory_type: str = "fact", importance: float = 1.0):
    collection = get_collection()
    chunks = chunk_text(content)

    for chunk in chunks:
        embedding_id = str(uuid.uuid4())
        vec = embed(chunk)

        collection.add(
            ids=[embedding_id],
            embeddings=[vec],
            documents=[chunk],
            metadatas=[{"type": memory_type, "importance": importance}]
        )

        memory = Memory(
            content=chunk,
            type=memory_type,
            importance=importance,
            embedding_id=embedding_id
        )
        next(get_db()).add(memory)
        next(get_db()).commit()