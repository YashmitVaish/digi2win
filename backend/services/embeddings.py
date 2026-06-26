import os

import httpx
from sentence_transformers import SentenceTransformer

_fallback_model = None


def _fallback_embed(text: str) -> list[float]:
    global _fallback_model
    if _fallback_model is None:
        _fallback_model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    vec = _fallback_model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed(text: str) -> list[float]:
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    embed_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    try:
        resp = httpx.post(
            f"{ollama_url}/api/embeddings",
            json={"model": embed_model, "prompt": text},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        if "embedding" in data:
            return data["embedding"]
    except Exception:
        return _fallback_embed(text)

    return _fallback_embed(text)
