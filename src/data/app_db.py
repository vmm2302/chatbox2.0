"""Quản lý kết nối và schema cơ sở dữ liệu ứng dụng (App Database).

Lưu trữ riêng biệt dữ liệu người dùng, cuộc hội thoại, tin nhắn và nhật ký kiểm toán.
Tuyệt đối không can thiệp hoặc ghi đè database từ điển (dictionary_en_vi.db)
hoặc các tệp vector ChromaDB / qa_records.jsonl của hệ thống RAG.
"""

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional, Union

from config.settings import settings


CURRENT_SCHEMA_VERSION = 2

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- Bảng phiên bản schema để quản lý migration an toàn
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

-- Bảng tài khoản người dùng
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'admin')) DEFAULT 'user',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_login_at TEXT,
    updated_at TEXT NOT NULL
);

-- Bảng cuộc hội thoại thuộc người dùng
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'Cuộc trò chuyện mới',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT,
    is_pinned INTEGER NOT NULL DEFAULT 0
);

-- Bảng tin nhắn thuộc từng cuộc hội thoại
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    meta_json TEXT,
    created_at TEXT NOT NULL
);

-- Bảng nhật ký kiểm toán quản trị (Audit Logs)
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    actor_username TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT,
    details TEXT,
    status TEXT NOT NULL DEFAULT 'SUCCESS',
    created_at TEXT NOT NULL
);

-- Các chỉ mục tối ưu truy vấn
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id ASC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action, created_at DESC);
"""


def get_utc_now_iso() -> str:
    """Trả về thời gian UTC chuẩn ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


class AppDatabase:
    """Quản lý kết nối SQLite thread-safe cho cơ sở dữ liệu ứng dụng."""

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            self.db_path = Path(getattr(settings, "APP_DB_PATH", settings.DATA_DIR / "app_data.db"))

        self._local = threading.local()
        self._init_db()

    def _get_raw_connection(self) -> sqlite3.Connection:
        """Lấy kết nối sqlite3 riêng biệt cho luồng hiện tại."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            self._local.conn = conn
        return conn

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager cung cấp kết nối SQLite."""
        conn = self._get_raw_connection()
        yield conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager cung cấp transaction an toàn."""
        conn = self._get_raw_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_db(self) -> None:
        """Khởi tạo cấu trúc bảng và quản lý migration an toàn."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as conn:
            conn.executescript(SCHEMA_SQL)

            # Migration: kiểm tra và thêm cột is_pinned vào bảng conversations nếu chưa có
            cursor = conn.execute("PRAGMA table_info(conversations)")
            existing_cols = [row[1] for row in cursor.fetchall()]
            if "is_pinned" not in existing_cols:
                conn.execute("ALTER TABLE conversations ADD COLUMN is_pinned INTEGER NOT NULL DEFAULT 0")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_pinned ON conversations(user_id, is_pinned, updated_at DESC)")
            
            # Ghi nhận phiên bản schema
            cursor = conn.execute("SELECT MAX(version) FROM schema_version")
            row = cursor.fetchone()
            current_ver = row[0] if (row and row[0] is not None) else 0

            if current_ver < CURRENT_SCHEMA_VERSION:
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (CURRENT_SCHEMA_VERSION, get_utc_now_iso())
                )

    def close(self) -> None:
        """Đóng kết nối SQLite của luồng hiện tại nếu có."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None


# Khởi tạo singleton app database instance mặc định
app_db = AppDatabase()
