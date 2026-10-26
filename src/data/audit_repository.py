"""Kho lưu trữ nhật ký kiểm toán hệ thống (Audit Repository).

Ghi lại các thao tác quan trọng của quản trị viên và người dùng nhằm phục vụ
bảo mật và quản trị hệ thống. Tuyệt đối không lưu mật khẩu hoặc thông tin nhạy cảm.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.data.app_db import AppDatabase, app_db, get_utc_now_iso


@dataclass
class AuditLog:
    """Mô hình thực thể bản ghi nhật ký kiểm toán."""

    id: int
    actor_id: Optional[int]
    actor_username: str
    action: str
    target_type: str
    target_id: Optional[str]
    details: Optional[str]
    status: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "actor_id": self.actor_id,
            "actor_username": self.actor_username,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "details": self.details,
            "status": self.status,
            "created_at": self.created_at,
        }


class AuditRepository:
    """Truy vấn và ghi nhật ký kiểm toán hệ thống."""

    def __init__(self, db: Optional[AppDatabase] = None):
        self.db = db or app_db

    def log(
        self,
        actor_username: str,
        action: str,
        target_type: str,
        target_id: Optional[str] = None,
        details: Optional[Any] = None,
        status: str = "SUCCESS",
        actor_id: Optional[int] = None,
    ) -> AuditLog:
        """Ghi một sự kiện kiểm toán mới vào cơ sở dữ liệu."""
        clean_user = (actor_username or "system").strip().lower()
        clean_action = action.strip().upper()
        clean_target_type = target_type.strip().lower()
        clean_status = status.strip().upper()
        now_iso = get_utc_now_iso()

        details_str: Optional[str] = None
        if details is not None:
            if isinstance(details, (dict, list)):
                # Loại trừ bất kỳ key nhạy cảm nào nếu có
                safe_details = {}
                if isinstance(details, dict):
                    for k, v in details.items():
                        if "password" in k.lower() or "secret" in k.lower() or "token" in k.lower():
                            safe_details[k] = "******"
                        else:
                            safe_details[k] = v
                else:
                    safe_details = details
                details_str = json.dumps(safe_details, ensure_ascii=False)
            else:
                details_str = str(details)

        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO audit_logs (actor_id, actor_username, action, target_type, target_id, details, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    actor_id,
                    clean_user,
                    clean_action,
                    clean_target_type,
                    str(target_id) if target_id is not None else None,
                    details_str,
                    clean_status,
                    now_iso,
                ),
            )
            log_id = cursor.lastrowid

        return AuditLog(
            id=log_id,
            actor_id=actor_id,
            actor_username=clean_user,
            action=clean_action,
            target_type=clean_target_type,
            target_id=str(target_id) if target_id is not None else None,
            details=details_str,
            status=clean_status,
            created_at=now_iso,
        )

    def list_logs(
        self,
        limit: int = 100,
        offset: int = 0,
        action: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[AuditLog]:
        """Truy vấn danh sách nhật ký kiểm toán có lọc và phân trang."""
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params: List[Any] = []

        if action:
            query += " AND action = ?"
            params.append(action.strip().upper())

        if search:
            query += " AND (actor_username LIKE ? OR target_type LIKE ? OR details LIKE ?)"
            term = f"%{search.strip()}%"
            params.extend([term, term, term])

        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.db.connection() as conn:
            cursor = conn.execute(query, params)
            return [
                AuditLog(
                    id=row["id"],
                    actor_id=row["actor_id"],
                    actor_username=row["actor_username"],
                    action=row["action"],
                    target_type=row["target_type"],
                    target_id=row["target_id"],
                    details=row["details"],
                    status=row["status"],
                    created_at=row["created_at"],
                )
                for row in cursor.fetchall()
            ]

    def count_logs(self, action: Optional[str] = None, search: Optional[str] = None) -> int:
        """Đếm số bản ghi nhật ký kiểm toán."""
        query = "SELECT COUNT(*) FROM audit_logs WHERE 1=1"
        params: List[Any] = []

        if action:
            query += " AND action = ?"
            params.append(action.strip().upper())

        if search:
            query += " AND (actor_username LIKE ? OR target_type LIKE ? OR details LIKE ?)"
            term = f"%{search.strip()}%"
            params.extend([term, term, term])

        with self.db.connection() as conn:
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            return row[0] if row else 0
