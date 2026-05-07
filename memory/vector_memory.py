import threading
import uuid
import time
from typing import Optional

_EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


class VectorMemory:
    """Persistent semantic memory for group conversations.

    Singleton per persist_dir — safe to construct multiple times with the same
    path (hot-reload calls handler_init repeatedly).  Model loading runs in a
    background thread so the bot starts immediately.
    """

    _instances: dict = {}
    _lock = threading.Lock()

    def __new__(cls, persist_dir: str = "./memory_db", search_results: int = 6):
        with cls._lock:
            if persist_dir not in cls._instances:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instances[persist_dir] = instance
            return cls._instances[persist_dir]

    def __init__(self, persist_dir: str = "./memory_db", search_results: int = 6):
        if self._initialized:
            return
        self._initialized = True
        self._persist_dir = persist_dir
        self._search_results = search_results
        self._ready = False
        self._client = None
        self._model = None
        t = threading.Thread(target=self._init_sync, daemon=True)
        t.start()

    def _init_sync(self):
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
            self._client = chromadb.PersistentClient(path=self._persist_dir)
            self._model = SentenceTransformer(_EMBED_MODEL)
            self._ready = True
            print("[Memory] Vector memory ready")
        except Exception as exc:
            print(f"[Memory] Background init failed: {exc}")

    def _collection(self, group_id: int):
        return self._client.get_or_create_collection(
            name=f"group_{group_id}",
            metadata={"hnsw:space": "cosine"},
        )

    def store(self, group_id: int, user_id: Optional[int], content: str, role: str) -> None:
        if not self._ready or not content or not content.strip():
            return
        col = self._collection(group_id)
        embedding = self._model.encode(content, show_progress_bar=False).tolist()
        col.add(
            ids=[str(uuid.uuid4())],
            embeddings=[embedding],
            documents=[content],
            metadatas=[{
                "user_id": str(user_id) if user_id is not None else "",
                "role": role,
                "timestamp": int(time.time() * 1000),
            }],
        )

    def clear(self, group_id: int) -> bool:
        """Delete all stored messages for a group. Returns False if not ready."""
        if not self._ready:
            return False
        try:
            self._client.delete_collection(f"group_{group_id}")
            return True
        except Exception as exc:
            print(f"[Memory] Failed to clear group {group_id}: {exc}")
            return False

    def search(self, group_id: int, query: str) -> str:
        """Return relevant historical messages as a formatted string.

        Results are sorted by timestamp so they read chronologically.
        Returns empty string when not ready or no history exists.
        """
        if not self._ready:
            return ""
        col = self._collection(group_id)
        count = col.count()
        if count == 0:
            return ""

        n = min(self._search_results, count)
        embedding = self._model.encode(query, show_progress_bar=False).tolist()
        results = col.query(query_embeddings=[embedding], n_results=n)

        docs = results["documents"][0]
        metas = results["metadatas"][0]
        pairs = sorted(zip(metas, docs), key=lambda x: x[0]["timestamp"])

        lines = []
        for meta, doc in pairs:
            uid = meta.get("user_id", "")
            role = meta.get("role", "")
            if role == "assistant":
                lines.append(f"Bot曾回复: {doc}")
            elif uid:
                lines.append(f"QQ{uid} 曾说: {doc}")
            else:
                lines.append(doc)

        return "\n".join(lines)
