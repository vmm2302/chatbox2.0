"""Kho lưu trữ dữ liệu cuộc hội thoại và tin nhắn (Conversation Repository).

Đảm bảo nguyên tắc cách ly dữ liệu tuyệt đối (Data Isolation):
- Mọi truy vấn đọc, ghi, sửa, xóa cuộc hội thoại và tin nhắn BẮT BUỘC kiểm tra user_id.
- Không thể lấy hoặc can thiệp dữ liệu của người khác bằng cách thay đổi conversation_id.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.data.app_db import AppDatabase, app_db, get_utc_now_iso


@dataclass
class Message:
    """Mô hình thực thể tin nhắn hội thoại."""

    id: int
    conversation_id: str
    role: str  # 'user' hoặc 'assistant'
    content: str
    meta_json: Optional[str]
    created_at: str

    def get_meta(self) -> Dict[str, Any]:
        """Giải mã metadata từ chuỗi JSON an toàn."""
        if not self.meta_json:
            return {}
        try:
            return json.loads(self.meta_json)
        except Exception:
            return {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "meta": self.get_meta(),
            "created_at": self.created_at,
        }


@dataclass
class Conversation:
    """Mô hình thực thể cuộc hội thoại của người dùng."""

    id: str
    user_id: int
    title: str
    created_at: str
    updated_at: str
    archived_at: Optional[str] = None
    message_count: int = 0
    is_pinned: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "archived_at": self.archived_at,
            "message_count": self.message_count,
            "is_pinned": self.is_pinned,
        }


class ConversationRepository:
    """Quản lý lưu trữ và cách ly dữ liệu hội thoại theo từng tài khoản."""

    def __init__(self, db: Optional[AppDatabase] = None):
        self.db = db or app_db

    def create_conversation(
        self,
        user_id: int,
        title: str = "Cuộc trò chuyện mới",
        conv_id: Optional[str] = None,
    ) -> Conversation:
        """Tạo cuộc hội thoại mới gắn với user_id xác thực."""
        cid = conv_id or str(uuid4())
        now_iso = get_utc_now_iso()
        clean_title = (title or "Cuộc trò chuyện mới").strip()

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, user_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (cid, user_id, clean_title, now_iso, now_iso),
            )

        return Conversation(
            id=cid,
            user_id=user_id,
            title=clean_title,
            created_at=now_iso,
            updated_at=now_iso,
            archived_at=None,
            message_count=0,
            is_pinned=False,
        )

    def get_conversation(self, user_id: int, conversation_id: str) -> Optional[Conversation]:
        """Lấy thông tin cuộc trò chuyện. BẮT BUỘC kiểm tra quyền sở hữu user_id."""
        with self.db.connection() as conn:
            cursor = conn.execute(
                """
                SELECT c.*, COUNT(m.id) as msg_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.id = ? AND c.user_id = ?
                GROUP BY c.id
                """,
                (conversation_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            row_keys = row.keys() if hasattr(row, "keys") else []
            is_pinned_val = bool(row["is_pinned"]) if "is_pinned" in row_keys else False
            return Conversation(
                id=row["id"],
                user_id=row["user_id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                archived_at=row["archived_at"],
                message_count=row["msg_count"],
                is_pinned=is_pinned_val,
            )

    def list_conversations(self, user_id: int, limit: int = 50) -> List[Conversation]:
        """Liệt kê danh sách cuộc hội thoại thuộc quyền sở hữu của user_id (ưu tiên ghim trước)."""
        with self.db.connection() as conn:
            # Kiểm tra xem cột is_pinned có sẵn trong schema không
            cursor_check = conn.execute("PRAGMA table_info(conversations)")
            has_pinned = any(r[1] == "is_pinned" for r in cursor_check.fetchall())
            order_by = "c.is_pinned DESC, c.updated_at DESC" if has_pinned else "c.updated_at DESC"

            cursor = conn.execute(
                f"""
                SELECT c.*, COUNT(m.id) as msg_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.user_id = ?
                GROUP BY c.id
                ORDER BY {order_by}
                LIMIT ?
                """,
                (user_id, limit),
            )
            convs = []
            for row in cursor.fetchall():
                row_keys = row.keys() if hasattr(row, "keys") else []
                is_pinned_val = bool(row["is_pinned"]) if "is_pinned" in row_keys else False
                convs.append(
                    Conversation(
                        id=row["id"],
                        user_id=row["user_id"],
                        title=row["title"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        archived_at=row["archived_at"],
                        message_count=row["msg_count"],
                        is_pinned=is_pinned_val,
                    )
                )
            return convs

    def toggle_pin_conversation(self, user_id: int, conversation_id: str) -> bool:
        """Bật/tắt trạng thái ghim cuộc trò chuyện (chỉ thực hiện nếu thuộc đúng user_id)."""
        now_iso = get_utc_now_iso()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE conversations
                SET is_pinned = CASE WHEN is_pinned = 1 THEN 0 ELSE 1 END,
                    updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (now_iso, conversation_id, user_id),
            )
            return cursor.rowcount > 0

    def set_pin_conversation(self, user_id: int, conversation_id: str, is_pinned: bool) -> bool:
        """Đặt trạng thái ghim cuộc trò chuyện (chỉ thực hiện nếu thuộc đúng user_id)."""
        now_iso = get_utc_now_iso()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE conversations
                SET is_pinned = ?,
                    updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (1 if is_pinned else 0, now_iso, conversation_id, user_id),
            )
            return cursor.rowcount > 0

    def update_title(self, user_id: int, conversation_id: str, new_title: str) -> bool:
        """Đổi tên cuộc trò chuyện (chỉ thực hiện nếu thuộc đúng user_id)."""
        clean_title = new_title.strip()
        if not clean_title:
            return False
        now_iso = get_utc_now_iso()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (clean_title, now_iso, conversation_id, user_id),
            )
            return cursor.rowcount > 0

    def delete_conversation(self, user_id: int, conversation_id: str) -> bool:
        """Xóa cuộc trò chuyện và toàn bộ tin nhắn liên quan (Cascade)."""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user_id),
            )
            return cursor.rowcount > 0

    def clear_user_history(self, user_id: int) -> int:
        """Xóa toàn bộ lịch sử hội thoại của riêng user_id."""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM conversations WHERE user_id = ?",
                (user_id,),
            )
            return cursor.rowcount

    def add_message(
        self,
        user_id: int,
        conversation_id: str,
        role: str,
        content: str,
        meta_json: Optional[str] = None,
    ) -> Message:
        """Thêm tin nhắn vào cuộc hội thoại sau khi xác minh quyền sở hữu."""
        clean_role = role.strip().lower()
        if clean_role not in ("user", "assistant"):
            raise ValueError(f"Vai trò tin nhắn không hợp lệ: {role}")

        # Xác minh cuộc hội thoại thuộc về người dùng
        conv = self.get_conversation(user_id, conversation_id)
        if not conv:
            raise PermissionError(f"Không có quyền ghi vào cuộc trò chuyện {conversation_id}")

        now_iso = get_utc_now_iso()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO messages (conversation_id, role, content, meta_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, clean_role, content, meta_json, now_iso),
            )
            msg_id = cursor.lastrowid

            # Cập nhật thời điểm updated_at của cuộc hội thoại
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now_iso, conversation_id),
            )

        return Message(
            id=msg_id,
            conversation_id=conversation_id,
            role=clean_role,
            content=content,
            meta_json=meta_json,
            created_at=now_iso,
        )

    def get_messages(self, user_id: int, conversation_id: str) -> List[Message]:
        """Tải toàn bộ tin nhắn thuộc cuộc hội thoại sau khi xác minh quyền sở hữu."""
        conv = self.get_conversation(user_id, conversation_id)
        if not conv:
            # Ngăn chặn truy cập cuộc trò chuyện của người khác
            return []

        with self.db.connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM messages
                WHERE conversation_id = ?
                ORDER BY id ASC
                """,
                (conversation_id,),
            )
            return [
                Message(
                    id=row["id"],
                    conversation_id=row["conversation_id"],
                    role=row["role"],
                    content=row["content"],
                    meta_json=row["meta_json"],
                    created_at=row["created_at"],
                )
                for row in cursor.fetchall()
            ]

    def count_user_conversations(self, user_id: int) -> int:
        """Đếm số cuộc hội thoại của một người dùng."""
        with self.db.connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM conversations WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            return row[0] if row else 0

    def count_all_conversations(self) -> int:
        """Đếm tổng số cuộc hội thoại trên toàn hệ thống (dành cho Admin)."""
        with self.db.connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM conversations")
            row = cursor.fetchone()
            return row[0] if row else 0
