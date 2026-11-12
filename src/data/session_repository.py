"""Kho lưu trữ phiên xác thực và khóa ký Access Token (Session Repository).

Quản lý vòng đời Access Token ở phía server trong SQLite để hỗ trợ:
- Kiểm chứng và thu hồi token tức thì khi đăng xuất, đổi mật khẩu hoặc khóa/hạ quyền tài khoản.
- Sinh và lưu trữ khóa ký HMAC-SHA256 ngẫu nhiên an toàn cho môi trường 100% offline.
"""

import secrets
import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.data.app_db import AppDatabase, app_db, get_utc_now_iso


@dataclass
class UserSession:
    """Thực thể phiên đăng nhập gắn với Access Token."""

    id: str
    user_id: int
    token_hash: str
    created_at: str
    expires_at: str
    last_used_at: Optional[str] = None
    revoked_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_used_at": self.last_used_at,
            "revoked_at": self.revoked_at,
        }


class SessionRepository:
    """Quản lý lưu trữ và thu hồi phiên Access Token trong SQLite."""

    _SECRET_KEY_NAME = "auth_token_secret"

    def __init__(self, db: Optional[AppDatabase] = None):
        self.db = db or app_db
        self._secret_lock = threading.Lock()
        self._cached_secret: Optional[bytes] = None

    def _row_to_session(self, row: Any) -> Optional[UserSession]:
        if not row:
            return None
        return UserSession(
            id=row["id"],
            user_id=row["user_id"],
            token_hash=row["token_hash"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            last_used_at=row["last_used_at"],
            revoked_at=row["revoked_at"],
        )

    def get_or_create_token_secret(self, configured_secret: str = "") -> bytes:
        """Lấy khóa bí mật ký Access Token từ biến môi trường hoặc bảng app_settings."""
        clean_cfg = (configured_secret or "").strip()
        if clean_cfg:
            return clean_cfg.encode("utf-8")

        with self._secret_lock:
            if self._cached_secret is not None:
                return self._cached_secret

            now_iso = get_utc_now_iso()
            with self.db.transaction() as conn:
                cursor = conn.execute(
                    "SELECT value FROM app_settings WHERE key = ?",
                    (self._SECRET_KEY_NAME,),
                )
                row = cursor.fetchone()
                if row and row["value"]:
                    secret_hex = row["value"]
                else:
                    secret_hex = secrets.token_hex(32)
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO app_settings (key, value, updated_at)
                        VALUES (?, ?, ?)
                        """,
                        (self._SECRET_KEY_NAME, secret_hex, now_iso),
                    )
                    row_after = conn.execute(
                        "SELECT value FROM app_settings WHERE key = ?",
                        (self._SECRET_KEY_NAME,),
                    ).fetchone()
                    if row_after and row_after["value"]:
                        secret_hex = row_after["value"]

            try:
                self._cached_secret = bytes.fromhex(secret_hex)
            except ValueError:
                self._cached_secret = secret_hex.encode("utf-8")
            return self._cached_secret

    def create_session(
        self,
        session_id: str,
        user_id: int,
        token_hash: str,
        expires_at: str,
    ) -> UserSession:
        """Lưu phiên đăng nhập mới gắn với user_id và hash của token."""
        now_iso = get_utc_now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO user_sessions (id, user_id, token_hash, created_at, expires_at, last_used_at, revoked_at)
                VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (session_id, user_id, token_hash, now_iso, expires_at, now_iso),
            )
        return UserSession(
            id=session_id,
            user_id=user_id,
            token_hash=token_hash,
            created_at=now_iso,
            expires_at=expires_at,
            last_used_at=now_iso,
            revoked_at=None,
        )

    def get_session_by_id(self, session_id: str) -> Optional[UserSession]:
        """Truy vấn thông tin phiên theo jti."""
        if not session_id:
            return None
        with self.db.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM user_sessions WHERE id = ?",
                (session_id,),
            )
            return self._row_to_session(cursor.fetchone())

    def touch_session(self, session_id: str) -> None:
        """Cập nhật thời điểm sử dụng gần nhất của phiên."""
        now_iso = get_utc_now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE user_sessions SET last_used_at = ? WHERE id = ? AND revoked_at IS NULL",
                (now_iso, session_id),
            )

    def revoke_session(self, session_id: str) -> bool:
        """Thu hồi một phiên đăng nhập cụ thể."""
        if not session_id:
            return False
        now_iso = get_utc_now_iso()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE user_sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                (now_iso, session_id),
            )
            return cursor.rowcount > 0

    def revoke_all_user_sessions(
        self,
        user_id: int,
        exclude_session_id: Optional[str] = None,
    ) -> int:
        """Thu hồi toàn bộ phiên đang hoạt động của một người dùng."""
        now_iso = get_utc_now_iso()
        with self.db.transaction() as conn:
            if exclude_session_id:
                cursor = conn.execute(
                    """
                    UPDATE user_sessions
                    SET revoked_at = ?
                    WHERE user_id = ? AND revoked_at IS NULL AND id != ?
                    """,
                    (now_iso, user_id, exclude_session_id),
                )
            else:
                cursor = conn.execute(
                    """
                    UPDATE user_sessions
                    SET revoked_at = ?
                    WHERE user_id = ? AND revoked_at IS NULL
                    """,
                    (now_iso, user_id),
                )
            return cursor.rowcount

    def purge_expired_sessions(self) -> int:
        """Dọn dẹp các phiên đã hết hạn để giữ bảng gọn nhẹ."""
        now_iso = get_utc_now_iso()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM user_sessions WHERE expires_at <= ?",
                (now_iso,),
            )
            return cursor.rowcount
