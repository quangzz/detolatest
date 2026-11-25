"""Cơ chế lưu tiến độ (Checkpoint) và Cache thực thể toàn cục bằng SQLite WAL."""

from __future__ import annotations

from contextlib import closing
import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import GLOBAL_CACHE_DIR, ensure_directories


class CheckpointStore:
    """Lưu trạng thái hoàn thành của từng bước/KOC trong 1 job để hỗ trợ khôi phục khi gián đoạn."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._lock, closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    stage TEXT NOT NULL,
                    item_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_ts REAL NOT NULL,
                    PRIMARY KEY (stage, item_key)
                );
                """
            )
            conn.commit()

    def save(self, stage: str, item_key: str, payload: Any) -> None:
        """Lưu kết quả của 1 đơn vị xử lý ngay sau khi hoàn tất."""
        serialized = json.dumps(payload, ensure_ascii=False)
        with self._lock, closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO checkpoints (stage, item_key, payload_json, updated_ts)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(stage, item_key) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    updated_ts=excluded.updated_ts;
                """,
                (stage, item_key, serialized, time.time()),
            )
            conn.commit()

    def load(self, stage: str, item_key: str) -> Optional[Any]:
        """Đọc kết quả đã lưu của 1 đơn vị xử lý (trả về None nếu chưa có)."""
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT payload_json FROM checkpoints WHERE stage = ? AND item_key = ?;",
                (stage, item_key),
            ).fetchone()
            if not row:
                return None
            return json.loads(row[0])

    def load_stage_map(self, stage: str) -> Dict[str, Any]:
        """Đọc toàn bộ các mục đã hoàn thành trong 1 stage dưới dạng dict."""
        with self._lock, closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT item_key, payload_json FROM checkpoints WHERE stage = ?;",
                (stage,),
            ).fetchall()
            return {key: json.loads(val) for key, val in rows}


class GlobalEntityCache:
    """Cache liên phiên (cross-job) tránh gọi lại LLM hoặc tải lại dữ liệu cho cùng KOC/Video."""

    def __init__(self, ttl_seconds: int = 7 * 86400) -> None:
        ensure_directories()
        self.db_path = GLOBAL_CACHE_DIR / "global_cache.db"
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._lock, closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS entity_cache (
                    namespace TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_ts REAL NOT NULL,
                    PRIMARY KEY (namespace, cache_key)
                );
                """
            )
            conn.commit()

    @staticmethod
    def hash_text(content: str) -> str:
        """Băm chuỗi nội dung thành mã SHA-256 ngắn để làm khóa cache ổn định."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:20]

    def get(self, namespace: str, cache_key: str) -> Optional[Any]:
        """Lấy dữ liệu từ cache nếu còn hạn sử dụng."""
        now = time.time()
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT payload_json, created_ts FROM entity_cache WHERE namespace = ? AND cache_key = ?;",
                (namespace, cache_key),
            ).fetchone()
            if not row:
                return None
            payload_json, created_ts = row
            if now - float(created_ts) > self.ttl_seconds:
                return None
            return json.loads(payload_json)

    def set(self, namespace: str, cache_key: str, payload: Any) -> None:
        """Ghi dữ liệu vào cache toàn cục."""
        serialized = json.dumps(payload, ensure_ascii=False)
        with self._lock, closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO entity_cache (namespace, cache_key, payload_json, created_ts)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(namespace, cache_key) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    created_ts=excluded.created_ts;
                """,
                (namespace, cache_key, serialized, time.time()),
            )
            conn.commit()
