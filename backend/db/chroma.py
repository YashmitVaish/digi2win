import chromadb

_client = None
_collection = None

def get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path="./chroma_store")
        _collection = _client.get_or_create_collection(
            name="twin_memories",
            metadata={"hnsw:space": "cosine"}
        )
    return _collection