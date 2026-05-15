import math
import os
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

_DEFAULT_EMBED_MODEL = "BAAI/bge-small-zh-v1.5"
_PRUNE_TARGET_RATIO = 0.9
_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


class VectorMemory:
    """Persistent semantic memory for group conversations.

    The previous implementation used a heavier local vector stack, which is
    powerful but keeps many libraries resident in the bot process.
    This implementation uses FastEmbed/ONNX plus SQLite storage to keep the same
    public API with much lower idle memory.
    """

    _instances: dict = {}
    _lock = threading.Lock()

    def __new__(
        cls,
        persist_dir: str = "./memory_db",
        search_results: int = 6,
        max_records_per_group: int = 5000,
        embedding_model: str = _DEFAULT_EMBED_MODEL,
        lexical_weight: float = 0.18,
        recency_weight: float = 0.04,
    ):
        with cls._lock:
            instance_key = os.path.abspath(persist_dir)
            if instance_key not in cls._instances:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instances[instance_key] = instance
            return cls._instances[instance_key]

    def __init__(
        self,
        persist_dir: str = "./memory_db",
        search_results: int = 6,
        max_records_per_group: int = 5000,
        embedding_model: str = _DEFAULT_EMBED_MODEL,
        lexical_weight: float = 0.18,
        recency_weight: float = 0.04,
    ):
        if self._initialized:
            self._search_results = search_results
            self._max_records_per_group = max(0, int(max_records_per_group))
            self._embedding_model_name = embedding_model
            self._lexical_weight = max(0.0, float(lexical_weight))
            self._recency_weight = max(0.0, float(recency_weight))
            return

        self._initialized = True
        self._persist_dir = Path(persist_dir)
        self._db_path = self._resolve_db_path(self._persist_dir)
        self._search_results = search_results
        self._max_records_per_group = max(0, int(max_records_per_group))
        self._embedding_model_name = embedding_model or _DEFAULT_EMBED_MODEL
        self._lexical_weight = max(0.0, float(lexical_weight))
        self._recency_weight = max(0.0, float(recency_weight))
        self._ready = False
        self._model = None
        self._dimension = None
        self._db_lock = threading.RLock()
        self._model_lock = threading.Lock()
        self._conn = None

        t = threading.Thread(target=self._init_sync, daemon=True)
        t.start()

    @staticmethod
    def _resolve_db_path(path: Path) -> Path:
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        path.mkdir(parents=True, exist_ok=True)
        return path / "memory.sqlite3"

    def _init_sync(self):
        try:
            from fastembed import TextEmbedding

            self._conn = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
                isolation_level=None,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA temp_store=MEMORY")
            self._create_schema()

            self._model = TextEmbedding(model_name=self._embedding_model_name)
            warmup = self._embed_one("memory warmup", kind="passage")
            self._dimension = int(warmup.shape[0])
            self._ready = True
            print(
                f"[Memory] FastEmbed memory ready model={self._embedding_model_name} "
                f"dim={self._dimension} db={self._db_path}"
            )
        except Exception as exc:
            print(f"[Memory] Background init failed: {exc}")

    def _create_schema(self):
        with self._db_lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    group_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_group_time
                ON memories(group_id, created_at)
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_group_role_mode
                ON memories(group_id, role, mode)
                """
            )

    def _embed_one(self, text: str, kind: str):
        if kind == "query":
            text = f"query: {text}"
        elif kind == "passage":
            text = f"passage: {text}"
        with self._model_lock:
            embedding = next(self._model.embed([text]))
        np = _numpy()
        arr = np.asarray(embedding, dtype=np.float32)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        return arr

    @staticmethod
    def _embedding_to_blob(embedding) -> bytes:
        np = _numpy()
        return np.asarray(embedding, dtype=np.float32).tobytes()

    @staticmethod
    def _blob_to_embedding(blob: bytes):
        np = _numpy()
        return np.frombuffer(blob, dtype=np.float32)

    def store(
        self,
        group_id: int,
        user_id: Optional[int],
        content: str,
        role: str,
        mode: Optional[str] = None,
    ) -> None:
        if not self._ready or not content or not content.strip():
            return

        created_at = int(time.time() * 1000)
        memory_id = str(uuid.uuid4())
        embedding = self._embed_one(content, kind="passage")

        with self._db_lock:
            self._conn.execute(
                """
                INSERT INTO memories
                    (id, group_id, user_id, role, mode, content, embedding, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    int(group_id),
                    str(user_id) if user_id is not None else "",
                    role,
                    mode or "",
                    content,
                    self._embedding_to_blob(embedding),
                    created_at,
                ),
            )
            self._prune_group_locked(int(group_id))

    def _prune_group_locked(self, group_id: int) -> None:
        if self._max_records_per_group <= 0:
            return

        count = self._conn.execute(
            "SELECT COUNT(*) FROM memories WHERE group_id = ?",
            (group_id,),
        ).fetchone()[0]
        if count <= self._max_records_per_group:
            return

        target_count = max(1, int(self._max_records_per_group * _PRUNE_TARGET_RATIO))
        delete_count = count - target_count
        self._conn.execute(
            """
            DELETE FROM memories
            WHERE id IN (
                SELECT id FROM memories
                WHERE group_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            )
            """,
            (group_id, delete_count),
        )
        print(
            f"[Memory] Pruned group {group_id} memory "
            f"from {count} to about {target_count} records"
        )

    def clear(self, group_id: int) -> bool:
        """Delete all stored messages for a group. Returns False if not ready."""
        if not self._ready:
            return False

        with self._db_lock:
            before_count = self._conn.execute(
                "SELECT COUNT(*) FROM memories WHERE group_id = ?",
                (int(group_id),),
            ).fetchone()[0]
            self._conn.execute(
                "DELETE FROM memories WHERE group_id = ?",
                (int(group_id),),
            )
        print(f"[Memory] Cleared group {group_id} vector memory ({before_count} records)")
        return True

    def search(self, group_id: int, query: str, mode: Optional[str] = None) -> str:
        """Return relevant historical messages as a formatted string.

        Hybrid scoring combines semantic similarity, exact text overlap, and a
        small recency hint. Returned memories are sorted chronologically so the
        injected context reads like conversation history.
        """
        if not self._ready or not query or not query.strip():
            return ""

        query_embedding = self._embed_one(query, kind="query")
        query_terms = _terms(query)
        now_ms = int(time.time() * 1000)
        np = _numpy()

        with self._db_lock:
            rows = self._conn.execute(
                """
                SELECT id, user_id, role, mode, content, embedding, created_at
                FROM memories
                WHERE group_id = ?
                """,
                (int(group_id),),
            ).fetchall()

        scored = []
        for row in rows:
            memory_id, user_id, role, memory_mode, content, blob, created_at = row
            if not self._visible_for_mode(role, memory_mode, mode):
                continue

            memory_embedding = self._blob_to_embedding(blob)
            if memory_embedding.shape != query_embedding.shape:
                continue

            vector_score = float(np.dot(query_embedding, memory_embedding))
            lexical_score = _overlap_score(query_terms, content)
            recency_score = _recency_score(now_ms, int(created_at))
            combined = (
                vector_score
                + self._lexical_weight * lexical_score
                + self._recency_weight * recency_score
            )
            scored.append(
                {
                    "score": combined,
                    "created_at": int(created_at),
                    "user_id": user_id,
                    "role": role,
                    "content": content,
                }
            )

        if not scored:
            return ""

        top = sorted(scored, key=lambda item: item["score"], reverse=True)[: self._search_results]
        top = sorted(top, key=lambda item: item["created_at"])
        return "\n".join(_format_memory_line(item) for item in top)

    @staticmethod
    def _visible_for_mode(role: str, memory_mode: str, mode: Optional[str]) -> bool:
        if mode == "guardian" and role == "assistant" and memory_mode != "guardian":
            return False
        return True


def _terms(text: str) -> set[str]:
    normalized = text.lower()
    terms = set(_TOKEN_RE.findall(normalized))
    chinese_chars = {char for char in normalized if "\u4e00" <= char <= "\u9fff"}
    return terms | chinese_chars


def _numpy():
    import numpy as np

    return np


def _overlap_score(query_terms: set[str], content: str) -> float:
    if not query_terms:
        return 0.0
    content_terms = _terms(content)
    if not content_terms:
        return 0.0
    return len(query_terms & content_terms) / math.sqrt(len(query_terms) * len(content_terms))


def _recency_score(now_ms: int, created_at: int) -> float:
    age_days = max(0.0, (now_ms - created_at) / 86_400_000)
    return 1.0 / (1.0 + age_days / 14.0)


def _format_memory_line(item: dict) -> str:
    user_id = item.get("user_id", "")
    role = item.get("role", "")
    content = item.get("content", "")
    if role == "assistant":
        return f"Bot曾回复: {content}"
    if user_id:
        return f"QQ{user_id} 曾说: {content}"
    return content
