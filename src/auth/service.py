"""Dịch vụ nghiệp vụ xác thực và phân quyền (Authentication & RBAC Service).

Chịu trách nhiệm thực thi các quy tắc kiểm tra quyền hạn (Access Control),
ngăn chặn người dùng tự nâng quyền và bảo vệ an toàn cho hệ thống.
"""

import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from src.auth.security import (
    hash_password,
    validate_password,
    validate_username,
    verify_password,
)
from src.data.app_db import AppDatabase, app_db
from src.data.audit_repository import AuditRepository
from src.data.user_repository import User, UserRepository


class AuthService:
    """Xử lý toàn bộ logic nghiệp vụ xác thực, tài khoản và phân quyền."""

    def __init__(
        self,
        user_repo: Optional[UserRepository] = None,
        audit_repo: Optional[AuditRepository] = None,
        db: Optional[AppDatabase] = None,
    ):
        database = db or app_db
        self.user_repo = user_repo or UserRepository(db=database)
        self.audit_repo = audit_repo or AuditRepository(db=database)

    # --------------------------------------------------------------------------
    # 0. KIỂM TRA TRẠNG THÁI KHỞI TẠO HỆ THỐNG
    # --------------------------------------------------------------------------

    def has_admin(self) -> bool:
        """Kiểm tra hệ thống đã có ít nhất một Quản trị viên (Admin) hoạt động hay chưa."""
        try:
            return self.user_repo.count_active_admins() > 0
        except Exception:
            return False

    def get_system_init_status(self) -> Tuple[str, Optional[str]]:
        """Xác định trạng thái khởi tạo của hệ thống tài khoản:
        - 'READY': Hệ thống đã sẵn sàng với ít nhất một Admin hợp lệ.
        - 'NO_ADMIN': Chưa có tài khoản Admin nào được khởi tạo (yêu cầu bootstrap).
        - 'DB_ERROR': Lỗi kết nối hoặc hỏng tệp cơ sở dữ liệu (không phải trạng thái không có tài khoản).
        """
        try:
            admins = self.user_repo.count_active_admins()
            if admins > 0:
                return "READY", None
            return "NO_ADMIN", None
        except sqlite3.DatabaseError as db_err:
            return "DB_ERROR", f"Cơ sở dữ liệu SQLite gặp lỗi tính toàn vẹn: {db_err}"
        except Exception as exc:
            return "DB_ERROR", f"Không thể kết nối cơ sở dữ liệu ứng dụng: {exc}"

    def get_account_lifecycle_state(self, current_user: Optional[User] = None) -> Tuple[str, Dict[str, Any]]:
        """Phân loại chính xác 7 trạng thái vòng đời tài khoản & hệ thống (Section 5 Spec):
        1. STATE_1_DB_NOT_INITIALIZED: Database chưa tồn tại trên đĩa.
        2. STATE_2_DB_EMPTY: Database đã tồn tại nhưng chưa có bất kỳ tài khoản nào.
        3. STATE_3_NO_ACTIVE_ADMIN: Database có tài khoản nhưng chưa có Admin nào đang hoạt động.
        4. STATE_4_UNAUTHENTICATED: Hệ thống đã sẵn sàng nhưng người dùng chưa đăng nhập.
        5. STATE_5_AUTHENTICATED: Người dùng đã đăng nhập bình thường và tài khoản đang hoạt động.
        6. STATE_6_DISABLED_OR_INVALID: Phiên xác thực không còn hợp lệ hoặc tài khoản bị vô hiệu hóa.
        7. STATE_7_DB_ERROR: Database gặp lỗi kết nối hoặc hỏng tính toàn vẹn.
        """
        from pathlib import Path
        db_path = getattr(self.user_repo.db, "db_path", None)
        if db_path and not Path(db_path).exists():
            return "STATE_1_DB_NOT_INITIALIZED", {"detail": f"Database chưa tồn tại tại {db_path}"}

        try:
            counts = self.user_repo.count_users()
            total_users = counts.get("total", 0)
            active_admins = counts.get("active_admins", 0)

            if total_users == 0:
                return "STATE_2_DB_EMPTY", {"total_users": 0, "active_admins": 0}

            if active_admins == 0:
                return "STATE_3_NO_ACTIVE_ADMIN", {"total_users": total_users, "active_admins": 0}

            if current_user is None:
                return "STATE_4_UNAUTHENTICATED", {"active_admins": active_admins}

            fresh = self.user_repo.get_by_id(current_user.id)
            if not fresh or not fresh.is_active:
                return "STATE_6_DISABLED_OR_INVALID", {"user_id": current_user.id, "reason": "Tài khoản bị vô hiệu hóa hoặc không tồn tại"}

            return "STATE_5_AUTHENTICATED", {"user": fresh}

        except sqlite3.DatabaseError as db_err:
            return "STATE_7_DB_ERROR", {"error": f"Lỗi toàn vẹn SQLite: {db_err}"}
        except Exception as exc:
            return "STATE_7_DB_ERROR", {"error": f"Lỗi kết nối database: {exc}"}

    # --------------------------------------------------------------------------
    # 1. ĐĂNG KÝ VÀ ĐĂNG NHẬP (USER FACING)
    # --------------------------------------------------------------------------

    def register_user(
        self,
        username: str,
        password: str,
        confirm_password: str,
        display_name: Optional[str] = None,
        require_admin_exists: bool = False,
    ) -> Tuple[bool, Optional[User], str]:
        """Đăng ký tài khoản User mới cho khách.
        
        Quy tắc:
        - Nếu require_admin_exists=True, chỉ cho phép đăng ký khi hệ thống đã có ít nhất một Admin.
        - Luôn gán vai trò 'user'. Tuyệt đối không cho phép tạo admin qua form đăng ký.
        - Kiểm tra độ mạnh mật khẩu và trùng khớp mật khẩu.
        - Tên đăng nhập là duy nhất.
        """
        if require_admin_exists and not self.has_admin():
            return False, None, "Hệ thống chưa có tài khoản Quản trị viên (Admin). Vui lòng khởi tạo Admin trước bằng lệnh: python scripts/create_admin.py"

        valid_u, err_u = validate_username(username)
        if not valid_u:
            return False, None, err_u

        valid_p, err_p = validate_password(password)
        if not valid_p:
            return False, None, err_p

        if password != confirm_password:
            return False, None, "Mật khẩu xác nhận không khớp. Vui lòng nhập lại."

        clean_username = username.strip().lower()
        existing = self.user_repo.get_by_username(clean_username)
        if existing:
            return False, None, f"Tên đăng nhập '{clean_username}' đã tồn tại. Vui lòng chọn tên khác."

        # Băm mật khẩu bằng Bcrypt
        hashed = hash_password(password)
        final_display_name = (display_name or "").strip() or clean_username

        try:
            user = self.user_repo.create_user(
                username=clean_username,
                password_hash=hashed,
                display_name=final_display_name,
                role="user",  # Ép buộc vai trò user
                is_active=True,
            )
            self.audit_repo.log(
                actor_username=clean_username,
                actor_id=user.id,
                action="USER_REGISTER",
                target_type="user",
                target_id=str(user.id),
                details={"username": clean_username, "role": "user"},
                status="SUCCESS",
            )
            return True, user, "Đăng ký tài khoản thành công! Bạn có thể đăng nhập ngay."
        except Exception as exc:
            return False, None, f"Lỗi khi tạo tài khoản: {exc}"

    def authenticate(
        self,
        username: str,
        password: str,
    ) -> Tuple[bool, Optional[User], str]:
        """Xác thực đăng nhập người dùng.
        
        Bảo mật:
        - Thông báo lỗi chung 'Tên đăng nhập hoặc mật khẩu không chính xác' để tránh dò tài khoản.
        - Thông báo rõ ràng khi tài khoản đã bị vô hiệu hóa bởi Admin.
        """
        if not username or not password:
            return False, None, "Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu."

        clean_username = username.strip().lower()
        user = self.user_repo.get_by_username(clean_username)

        # Tránh timing attack hoặc lộ danh tính tài khoản
        if not user or not verify_password(password, user.password_hash):
            self.audit_repo.log(
                actor_username=clean_username,
                action="LOGIN_FAILED",
                target_type="auth",
                details={"reason": "Invalid credentials"},
                status="FAILURE",
            )
            return False, None, "Tên đăng nhập hoặc mật khẩu không chính xác."

        # Kiểm tra trạng thái hoạt động của tài khoản
        if not user.is_active:
            self.audit_repo.log(
                actor_username=clean_username,
                actor_id=user.id,
                action="LOGIN_REJECTED_DISABLED",
                target_type="auth",
                details={"reason": "Account is deactivated"},
                status="FAILURE",
            )
            return False, None, "Tài khoản của bạn đã bị vô hiệu hóa. Vui lòng liên hệ quản trị viên."

        # Đăng nhập thành công -> cập nhật thời gian
        self.user_repo.update_last_login(user.id)
        refreshed_user = self.user_repo.get_by_id(user.id) or user
        self.audit_repo.log(
            actor_username=clean_username,
            actor_id=user.id,
            action="USER_LOGIN",
            target_type="auth",
            details={"role": user.role},
            status="SUCCESS",
        )
        return True, refreshed_user, "Đăng nhập thành công."

    def logout(self, user: User) -> None:
        """Ghi nhận lượt đăng xuất."""
        if user:
            self.audit_repo.log(
                actor_username=user.username,
                actor_id=user.id,
                action="USER_LOGOUT",
                target_type="auth",
                status="SUCCESS",
            )

    # --------------------------------------------------------------------------
    # 2. KHỞI TẠO ADMIN ĐẦU TIÊN (BOOTSTRAP ADMIN)
    # --------------------------------------------------------------------------

    def bootstrap_first_admin(
        self,
        username: str,
        password: str,
        display_name: Optional[str] = "Quản trị viên",
    ) -> Tuple[bool, Optional[User], str]:
        """Tạo tài khoản Quản trị viên (Admin) đầu tiên qua CLI an toàn."""
        valid_u, err_u = validate_username(username)
        if not valid_u:
            return False, None, err_u

        valid_p, err_p = validate_password(password)
        if not valid_p:
            return False, None, err_p

        clean_username = username.strip().lower()
        existing = self.user_repo.get_by_username(clean_username)
        if existing:
            return False, None, f"Tài khoản '{clean_username}' đã tồn tại trong cơ sở dữ liệu."

        hashed = hash_password(password)
        final_display_name = (display_name or "").strip() or clean_username

        try:
            admin_user = self.user_repo.create_user(
                username=clean_username,
                password_hash=hashed,
                display_name=final_display_name,
                role="admin",
                is_active=True,
            )
            self.audit_repo.log(
                actor_username="system_cli",
                action="BOOTSTRAP_ADMIN",
                target_type="user",
                target_id=str(admin_user.id),
                details={"username": clean_username, "role": "admin"},
                status="SUCCESS",
            )
            return True, admin_user, f"Khởi tạo thành công Quản trị viên '{clean_username}'."
        except Exception as exc:
            return False, None, f"Lỗi khi khởi tạo tài khoản Admin: {exc}"

    # --------------------------------------------------------------------------
    # 3. KIỂM TRA QUYỀN HẠN BACKEND (RBAC ENFORCEMENT)
    # --------------------------------------------------------------------------

    def verify_active_session(self, user_id: int) -> Optional[User]:
        """Xác minh tài khoản còn tồn tại và đang hoạt động."""
        user = self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            return None
        return user

    def require_admin(self, actor: Optional[User]) -> User:
        """Kiểm tra quyền quản trị viên ở backend. Ném ngoại lệ PermissionError nếu không đủ quyền."""
        if not actor:
            raise PermissionError("Yêu cầu đăng nhập để thực hiện thao tác này.")
        
        # Luôn xác minh lại trạng thái mới nhất từ cơ sở dữ liệu
        fresh = self.user_repo.get_by_id(actor.id)
        if not fresh or not fresh.is_active:
            raise PermissionError("Tài khoản của bạn đã bị vô hiệu hóa hoặc không tồn tại.")
        if fresh.role != "admin":
            raise PermissionError("Thao tác bị từ chối: Yêu cầu quyền Quản trị viên (Admin).")

        return fresh

    def require_active_user(self, actor: Optional[User]) -> User:
        """Kiểm tra tài khoản người dùng đang hoạt động."""
        if not actor:
            raise PermissionError("Yêu cầu đăng nhập để thực hiện thao tác này.")
        fresh = self.user_repo.get_by_id(actor.id)
        if not fresh or not fresh.is_active:
            raise PermissionError("Tài khoản đã bị vô hiệu hóa.")
        return fresh

    # --------------------------------------------------------------------------
    # 4. CHỨC NĂNG QUẢN TRỊ VIÊN (ADMIN DASHBOARD ACTIONS)
    # --------------------------------------------------------------------------

    def admin_create_user(
        self,
        actor: User,
        username: str,
        password: str,
        display_name: Optional[str] = None,
        role: str = "user",
    ) -> Tuple[bool, Optional[User], str]:
        """Admin tạo tài khoản người dùng hoặc admin mới."""
        self.require_admin(actor)

        valid_u, err_u = validate_username(username)
        if not valid_u:
            return False, None, err_u

        valid_p, err_p = validate_password(password)
        if not valid_p:
            return False, None, err_p

        clean_username = username.strip().lower()
        if self.user_repo.get_by_username(clean_username):
            return False, None, f"Tên đăng nhập '{clean_username}' đã tồn tại."

        clean_role = role.strip().lower()
        if clean_role not in ("user", "admin"):
            return False, None, "Vai trò chỉ được là 'user' hoặc 'admin'."

        hashed = hash_password(password)
        final_display_name = (display_name or "").strip() or clean_username

        user = self.user_repo.create_user(
            username=clean_username,
            password_hash=hashed,
            display_name=final_display_name,
            role=clean_role,
            is_active=True,
        )
        self.audit_repo.log(
            actor_username=actor.username,
            actor_id=actor.id,
            action="ADMIN_CREATE_USER",
            target_type="user",
            target_id=str(user.id),
            details={"username": clean_username, "role": clean_role},
            status="SUCCESS",
        )
        return True, user, f"Đã tạo thành công tài khoản '{clean_username}' với vai trò '{clean_role}'."

    def admin_toggle_active(
        self,
        actor: User,
        target_user_id: int,
        is_active: bool,
    ) -> Tuple[bool, str]:
        """Admin vô hiệu hóa hoặc kích hoạt lại tài khoản."""
        self.require_admin(actor)

        target = self.user_repo.get_by_id(target_user_id)
        if not target:
            return False, "Không tìm thấy tài khoản người dùng tương ứng."

        # Bảo vệ: Tuyệt đối không cho phép vô hiệu hóa tài khoản Quản trị viên (Admin)
        if not is_active and target.role == "admin":
            return False, "Không thể vô hiệu hóa tài khoản Quản trị viên (Admin)."

        ok = self.user_repo.set_active_status(target_user_id, is_active)
        if ok:
            action_name = "ADMIN_ENABLE_USER" if is_active else "ADMIN_DISABLE_USER"
            self.audit_repo.log(
                actor_username=actor.username,
                actor_id=actor.id,
                action=action_name,
                target_type="user",
                target_id=str(target_user_id),
                details={"target_username": target.username, "new_active_status": is_active},
                status="SUCCESS",
            )
            status_text = "kích hoạt" if is_active else "vô hiệu hóa"
            return True, f"Đã {status_text} thành công tài khoản '{target.username}'."
        return False, "Không thể cập nhật trạng thái tài khoản."

    def admin_reset_password(
        self,
        actor: User,
        target_user_id: int,
        new_password: str,
    ) -> Tuple[bool, str]:
        """Admin đặt lại mật khẩu cho tài khoản người dùng."""
        self.require_admin(actor)

        target = self.user_repo.get_by_id(target_user_id)
        if not target:
            return False, "Không tìm thấy người dùng."

        valid_p, err_p = validate_password(new_password)
        if not valid_p:
            return False, err_p

        hashed = hash_password(new_password)
        ok = self.user_repo.update_password(target_user_id, hashed)
        if ok:
            self.audit_repo.log(
                actor_username=actor.username,
                actor_id=actor.id,
                action="ADMIN_RESET_PASSWORD",
                target_type="user",
                target_id=str(target_user_id),
                details={"target_username": target.username},
                status="SUCCESS",
            )
            return True, f"Đã đặt lại mật khẩu thành công cho tài khoản '{target.username}'."
        return False, "Không thể cập nhật mật khẩu."

    def admin_change_role(
        self,
        actor: User,
        target_user_id: int,
        new_role: str,
    ) -> Tuple[bool, str]:
        """Admin thay đổi vai trò giữa user và admin."""
        self.require_admin(actor)

        target = self.user_repo.get_by_id(target_user_id)
        if not target:
            return False, "Không tìm thấy tài khoản người dùng."

        clean_role = new_role.strip().lower()
        if clean_role not in ("user", "admin"):
            return False, "Vai trò không hợp lệ."

        if target.role == clean_role:
            return True, "Vai trò tài khoản không thay đổi."

        # Bảo vệ: Nếu giáng quyền admin xuống user, kiểm tra xem có phải admin cuối cùng không
        if target.role == "admin" and clean_role != "admin" and target.is_active:
            if self.user_repo.count_active_admins() <= 1:
                return False, "Không thể giáng quyền Quản trị viên cuối cùng của hệ thống."

        ok = self.user_repo.set_role(target_user_id, clean_role)
        if ok:
            self.audit_repo.log(
                actor_username=actor.username,
                actor_id=actor.id,
                action="ADMIN_CHANGE_ROLE",
                target_type="user",
                target_id=str(target_user_id),
                details={"target_username": target.username, "old_role": target.role, "new_role": clean_role},
                status="SUCCESS",
            )
            return True, f"Đã chuyển vai trò tài khoản '{target.username}' thành '{clean_role}'."
        return False, "Không thể cập nhật vai trò."

    def admin_delete_user(
        self,
        actor: User,
        target_user_id: int,
    ) -> Tuple[bool, str]:
        """Admin xóa tài khoản người dùng kèm toàn bộ dữ liệu hội thoại liên quan."""
        self.require_admin(actor)

        target = self.user_repo.get_by_id(target_user_id)
        if not target:
            return False, "Không tìm thấy tài khoản để xóa."

        # Bảo vệ 1: Không cho phép tự xóa tài khoản đang đăng nhập
        if actor.id == target_user_id:
            return False, "Không thể tự xóa tài khoản quản trị bạn đang sử dụng."

        # Bảo vệ 2: Tuyệt đối không cho phép xóa tài khoản Quản trị viên (Admin)
        if target.role == "admin":
            return False, "Không thể xóa tài khoản Quản trị viên (Admin)."

        target_username = target.username
        ok = self.user_repo.delete_user(target_user_id)
        if ok:
            self.audit_repo.log(
                actor_username=actor.username,
                actor_id=actor.id,
                action="ADMIN_DELETE_USER",
                target_type="user",
                target_id=str(target_user_id),
                details={"deleted_username": target_username, "role": target.role},
                status="SUCCESS",
            )
            return True, f"Đã xóa hoàn toàn tài khoản '{target_username}' cùng dữ liệu liên quan."
        return False, "Không thể xóa tài khoản."

    # --------------------------------------------------------------------------
    # 5. CHỨC NĂNG THÔNG TIN CÁ NHÂN (SELF PROFILE)
    # --------------------------------------------------------------------------

    def user_update_profile(
        self,
        actor: User,
        display_name: str,
    ) -> Tuple[bool, str]:
        """Người dùng tự cập nhật tên hiển thị cá nhân."""
        self.require_active_user(actor)

        clean_name = display_name.strip()
        if not clean_name:
            return False, "Tên hiển thị không được để trống."

        ok = self.user_repo.update_profile(actor.id, clean_name)
        if ok:
            self.audit_repo.log(
                actor_username=actor.username,
                actor_id=actor.id,
                action="USER_UPDATE_PROFILE",
                target_type="user",
                target_id=str(actor.id),
                details={"new_display_name": clean_name},
                status="SUCCESS",
            )
            return True, "Cập nhật tên hiển thị thành công."
        return False, "Không thể cập nhật hồ sơ cá nhân."

    def user_change_password(
        self,
        actor: User,
        old_password: str,
        new_password: str,
        confirm_new_password: str,
    ) -> Tuple[bool, str]:
        """Người dùng tự đổi mật khẩu sau khi xác minh mật khẩu cũ."""
        fresh = self.require_active_user(actor)

        if not verify_password(old_password, fresh.password_hash):
            return False, "Mật khẩu hiện tại không chính xác."

        if new_password == old_password:
            return False, "Mật khẩu mới không được trùng với mật khẩu cũ."

        if new_password != confirm_new_password:
            return False, "Mật khẩu xác nhận không khớp."

        valid_p, err_p = validate_password(new_password)
        if not valid_p:
            return False, err_p

        hashed = hash_password(new_password)
        ok = self.user_repo.update_password(actor.id, hashed)
        if ok:
            self.audit_repo.log(
                actor_username=actor.username,
                actor_id=actor.id,
                action="USER_CHANGE_PASSWORD",
                target_type="user",
                target_id=str(actor.id),
                status="SUCCESS",
            )
            return True, "Đổi mật khẩu thành công. Vui lòng ghi nhớ mật khẩu mới."
        return False, "Không thể cập nhật mật khẩu."
