"""FastAPI Security Dependencies for Access Token Verification and RBAC Enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.service import AuthService
from src.data.audit_repository import AuditRepository
from src.data.user_repository import User

# Shared singleton instances backed by app_db
auth_service = AuthService()
audit_repo = AuditRepository()

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    """Thông tin phiên đã xác thực được trích xuất từ Access Token và CSDL."""

    user: User
    session_id: str
    token: str


def get_current_auth_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> AuthContext:
    """Xác thực Bearer Access Token, kiểm tra chữ ký, phiên SQLite và trạng thái hoạt động từ DB."""
    if (
        credentials is None
        or not credentials.credentials
        or credentials.scheme.lower() != "bearer"
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu Access Token hợp lệ (Authorization: Bearer <token>).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_token = credentials.credentials.strip()
    user, session, err_msg = auth_service.verify_access_token(raw_token)
    if not user or not session:
        audit_repo.log(
            actor_username="anonymous",
            action="TOKEN_REJECTED",
            target_type="auth",
            target_id=request.url.path,
            details={"reason": err_msg or "Invalid or expired token"},
            status="FAILURE",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err_msg or "Access Token không hợp lệ hoặc đã hết hạn.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthContext(user=user, session_id=session.id, token=raw_token)


def get_current_user(auth_ctx: AuthContext = Depends(get_current_auth_context)) -> User:
    """Trả về thực thể User đang hoạt động đã được xác thực qua Access Token."""
    return auth_ctx.user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Kiểm tra lại phân quyền Quản trị viên (Admin) trực tiếp từ trạng thái DB hiện hành."""
    if not current_user.is_active or current_user.role != "admin":
        audit_repo.log(
            actor_username=current_user.username,
            actor_id=current_user.id,
            action="ACCESS_DENIED_ADMIN",
            target_type="auth",
            details={"role": current_user.role, "is_active": current_user.is_active},
            status="FAILURE",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yêu cầu quyền Quản trị viên (Admin) để thực hiện thao tác này.",
        )
    return current_user


def verify_actor_user_id_match(
    current_user: User,
    claimed_user_id: Optional[Any],
    allow_default_placeholder: bool = False,
) -> int:
    """Chặn mạo danh user_id: nếu client truyền user_id khác với chủ sở hữu token thì trả về 403."""
    if claimed_user_id is None:
        return current_user.id

    claimed_str = str(claimed_user_id).strip()
    if not claimed_str:
        return current_user.id
    if allow_default_placeholder and claimed_str == "default_user":
        return current_user.id

    if claimed_str != str(current_user.id):
        audit_repo.log(
            actor_username=current_user.username,
            actor_id=current_user.id,
            action="IDOR_ATTEMPT_BLOCKED",
            target_type="user",
            target_id=claimed_str,
            details={"authenticated_user_id": current_user.id, "claimed_user_id": claimed_str},
            status="FAILURE",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không được phép mạo danh hoặc truy cập dữ liệu của tài khoản khác.",
        )

    return current_user.id
