import chromadb
from pathlib import Path

_client = None
_collection = None
STORE_PATH = str(Path(__file__).resolve().parents[2] / "chroma_store")
COLLECTION_NAME = "twin_memories"

def get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=STORE_PATH)
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def reset_collection() -> None:
    global _client, _collection
    if _client is None:
        _client = chromadb.PersistentClient(path=STORE_PATH)
    try:
        _client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        pass
    _collection = _client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
