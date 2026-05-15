import threading
import uuid
import time
from typing import Optional

_EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
_PRUNE_TARGET_RATIO = 0.9


class VectorMemory:
    """Persistent semantic memory for group conversations.

    Singleton per persist_dir — safe to construct multiple times with the same
    path (hot-reload calls handler_init repeatedly).  Model loading runs in a
    background thread so the bot starts immediately.
    """

    _instances: dict = {}
    _lock = threading.Lock()

    def __new__(cls, persist_dir: str = "./memory_db", search_results: int = 6, max_records_per_group: int = 5000):
        with cls._lock:
            if persist_dir not in cls._instances:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instances[persist_dir] = instance
            return cls._instances[persist_dir]

    def __init__(self, persist_dir: str = "./memory_db", search_results: int = 6, max_records_per_group: int = 5000):
        if self._initialized:
            self._search_results = search_results
            self._max_records_per_group = max(0, int(max_records_per_group))
            return
        self._initialized = True
        self._persist_dir = persist_dir
        self._search_results = search_results
        self._max_records_per_group = max(0, int(max_records_per_group))
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

    def _collection_exists(self, name: str) -> bool:
        try:
            collections = self._client.list_collections()
        except Exception:
            return True

        for collection in collections:
            collection_name = getattr(collection, "name", collection)
            if collection_name == name:
                return True
        return False

    def store(self, group_id: int, user_id: Optional[int], content: str, role: str, mode: Optional[str] = None) -> None:
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
                "mode": mode or "",
                "timestamp": int(time.time() * 1000),
            }],
        )
        self._prune_collection(col, group_id)

    def _prune_collection(self, col, group_id: int) -> None:
        if self._max_records_per_group <= 0:
            return

        try:
            count = col.count()
            if count <= self._max_records_per_group:
                return

            target_count = max(1, int(self._max_records_per_group * _PRUNE_TARGET_RATIO))
            delete_count = count - target_count
            records = col.get(include=["metadatas"])
            ids = records.get("ids", [])
            metadatas = records.get("metadatas", [])
            pairs = sorted(
                zip(ids, metadatas),
                key=lambda pair: int((pair[1] or {}).get("timestamp") or 0),
            )
            delete_ids = [record_id for record_id, _meta in pairs[:delete_count]]
            if delete_ids:
                col.delete(ids=delete_ids)
                print(
                    f"[Memory] Pruned group {group_id} vector memory "
                    f"from {count} to about {target_count} records"
                )
        except Exception as exc:
            print(f"[Memory] Failed to prune group {group_id}: {exc}")

    def clear(self, group_id: int) -> bool:
        """Delete all stored messages for a group. Returns False if not ready."""
        if not self._ready:
            return False
        collection_name = f"group_{group_id}"
        try:
            if not self._collection_exists(collection_name):
                print(f"[Memory] Group {group_id} collection already empty")
                return True

            before_count = self._client.get_collection(name=collection_name).count()
            self._client.delete_collection(name=collection_name)
            print(f"[Memory] Cleared group {group_id} vector memory ({before_count} records)")
            return True
        except Exception as exc:
            if "does not exist" in str(exc).lower() or "not found" in str(exc).lower():
                print(f"[Memory] Group {group_id} collection already empty")
                return True
            print(f"[Memory] Failed to clear group {group_id}: {exc}")
            return False

    def search(self, group_id: int, query: str, mode: Optional[str] = None) -> str:
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
            memory_mode = meta.get("mode", "")
            if mode == "guardian" and role == "assistant" and memory_mode != "guardian":
                continue
            if role == "assistant":
                lines.append(f"Bot曾回复: {doc}")
            elif uid:
                lines.append(f"QQ{uid} 曾说: {doc}")
            else:
                lines.append(doc)

        return "\n".join(lines)
