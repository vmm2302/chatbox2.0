"""Kho lưu trữ dữ liệu người dùng (User Repository).

Thực hiện các thao tác truy vấn và cập nhật dữ liệu bảng 'users' bằng câu lệnh
tham số hóa (parameterized SQL), ngăn chặn tuyệt đối lỗi SQL Injection.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.data.app_db import AppDatabase, app_db, get_utc_now_iso


@dataclass
class User:
    """Mô hình thực thể tài khoản người dùng."""

    id: int
    username: str
    password_hash: str
    display_name: str
    role: str  # 'user' hoặc 'admin'
    is_active: bool
    created_at: str
    last_login_at: Optional[str]
    updated_at: str

    def to_dict(self, safe: bool = True) -> Dict[str, Any]:
        """Chuyển đổi thực thể thành từ điển. Mặc định loại bỏ chuỗi hash mật khẩu."""
        data = {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "last_login_at": self.last_login_at,
            "updated_at": self.updated_at,
        }
        if not safe:
            data["password_hash"] = self.password_hash
        return data


class UserRepository:
    """Truy vấn và quản trị tài khoản người dùng an toàn."""

    def __init__(self, db: Optional[AppDatabase] = None):
        self.db = db or app_db

    def _row_to_user(self, row: Any) -> Optional[User]:
        if not row:
            return None
        return User(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            display_name=row["display_name"],
            role=row["role"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            last_login_at=row["last_login_at"],
            updated_at=row["updated_at"],
        )

    def create_user(
        self,
        username: str,
        password_hash: str,
        display_name: str,
        role: str = "user",
        is_active: bool = True,
    ) -> User:
        """Tạo mới tài khoản người dùng với vai trò được kiểm định."""
        clean_username = username.strip().lower()
        now_iso = get_utc_now_iso()
        clean_role = role.strip().lower()
        if clean_role not in ("user", "admin"):
            raise ValueError(f"Vai trò không hợp lệ: {role}")

        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (username, password_hash, display_name, role, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_username,
                    password_hash,
                    display_name.strip() or clean_username,
                    clean_role,
                    1 if is_active else 0,
                    now_iso,
                    now_iso,
                ),
            )
            user_id = cursor.lastrowid

        return User(
            id=user_id,
            username=clean_username,
            password_hash=password_hash,
            display_name=display_name.strip() or clean_username,
            role=clean_role,
            is_active=is_active,
            created_at=now_iso,
            last_login_at=None,
            updated_at=now_iso,
        )

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Truy vấn tài khoản theo định danh ID."""
        with self.db.connection() as conn:
            cursor = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            return self._row_to_user(cursor.fetchone())

    def get_by_username(self, username: str) -> Optional[User]:
        """Truy vấn tài khoản theo tên đăng nhập (không phân biệt hoa thường)."""
        clean_username = username.strip().lower()
        with self.db.connection() as conn:
            cursor = conn.execute("SELECT * FROM users WHERE username = ?", (clean_username,))
            return self._row_to_user(cursor.fetchone())

    def update_last_login(self, user_id: int) -> None:
        """Cập nhật thời điểm đăng nhập gần nhất."""
        now_iso = get_utc_now_iso()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
                (now_iso, now_iso, user_id),
            )

    def update_profile(self, user_id: int, display_name: str) -> bool:
        """Cập nhật tên hiển thị cá nhân."""
        clean_name = display_name.strip()
        if not clean_name:
            return False
        now_iso = get_utc_now_iso()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE users SET display_name = ?, updated_at = ? WHERE id = ?",
                (clean_name, now_iso, user_id),
            )
            return cursor.rowcount > 0

    def update_password(self, user_id: int, new_password_hash: str) -> bool:
        """Cập nhật mật khẩu băm mới."""
        now_iso = get_utc_now_iso()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (new_password_hash, now_iso, user_id),
            )
            return cursor.rowcount > 0

    def set_active_status(self, user_id: int, is_active: bool) -> bool:
        """Vô hiệu hóa hoặc kích hoạt lại tài khoản. Không cho phép vô hiệu hóa tài khoản Admin."""
        if not is_active:
            user = self.get_by_id(user_id)
            if user and user.role == "admin":
                return False
        now_iso = get_utc_now_iso()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE users SET is_active = ?, updated_at = ? WHERE id = ?",
                (1 if is_active else 0, now_iso, user_id),
            )
            return cursor.rowcount > 0

    def set_role(self, user_id: int, new_role: str) -> bool:
        """Thay đổi vai trò người dùng (user <-> admin)."""
        clean_role = new_role.strip().lower()
        if clean_role not in ("user", "admin"):
            raise ValueError(f"Vai trò không hợp lệ: {new_role}")
        now_iso = get_utc_now_iso()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
                (clean_role, now_iso, user_id),
            )
            return cursor.rowcount > 0

    def count_active_admins(self) -> int:
        """Đếm số lượng quản trị viên (Admin) đang hoạt động."""
        with self.db.connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1"
            )
            row = cursor.fetchone()
            return row[0] if row else 0

    def count_users(self) -> Dict[str, int]:
        """Thống kê tổng hợp số lượng tài khoản theo vai trò và trạng thái."""
        with self.db.connection() as conn:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN role = 'admin' THEN 1 ELSE 0 END) as total_admins,
                    SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) as total_users,
                    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_count,
                    SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) as disabled_count,
                    SUM(CASE WHEN role = 'admin' AND is_active = 1 THEN 1 ELSE 0 END) as active_admins
                FROM users
                """
            )
            row = cursor.fetchone()
            return {
                "total": row["total"] or 0,
                "total_admins": row["total_admins"] or 0,
                "total_users": row["total_users"] or 0,
                "active_count": row["active_count"] or 0,
                "disabled_count": row["disabled_count"] or 0,
                "active_admins": row["active_admins"] or 0,
            }

    def list_users(
        self,
        search: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[User]:
        """Truy vấn danh sách người dùng kèm bộ lọc tìm kiếm và phân trang."""
        query = "SELECT * FROM users WHERE 1=1"
        params: List[Any] = []

        if search:
            query += " AND (username LIKE ? OR display_name LIKE ?)"
            term = f"%{search.strip()}%"
            params.extend([term, term])

        if role:
            query += " AND role = ?"
            params.append(role.strip().lower())

        if is_active is not None:
            query += " AND is_active = ?"
            params.append(1 if is_active else 0)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.db.connection() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_user(r) for r in cursor.fetchall()]

    def delete_user(self, user_id: int) -> bool:
        """Xóa hoàn toàn tài khoản người dùng và dữ liệu hội thoại liên quan. Không cho phép xóa tài khoản Admin."""
        user = self.get_by_id(user_id)
        if user and user.role == "admin":
            return False
        with self.db.transaction() as conn:
            cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            return cursor.rowcount > 0
