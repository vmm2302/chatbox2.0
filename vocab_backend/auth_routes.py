"""Authentication and User Profile routes for Vocab Web Application.
Reuses src.auth.service.AuthService with Bearer Access Token verification.
"""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.data.user_repository import User
from vocab_backend.dependencies import (
    AuthContext,
    auth_service,
    get_current_auth_context,
    get_current_user,
    verify_actor_user_id_match,
)

logger = logging.getLogger("vocab_api.auth")
auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=6)
    confirm_password: str = Field(..., min_length=6)
    display_name: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    user_id: Optional[int] = None
    current_password: str
    new_password: str
    confirm_password: str


@auth_router.get("/status")
def get_auth_system_status():
    """Get system account initialization status."""
    init_status, init_error = auth_service.get_system_init_status()
    has_admin = auth_service.has_admin()
    return {
        "status": init_status,
        "has_admin": has_admin,
        "error": init_error,
    }


@auth_router.post("/login")
def login(payload: LoginRequest):
    """Authenticate user with username and password and issue a signed Access Token."""
    success, user, message = auth_service.authenticate(payload.username, payload.password)
    if not success or not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
        )

    token_data = auth_service.issue_access_token(user)
    return {
        "status": "success",
        "message": message,
        "access_token": token_data["access_token"],
        "token_type": token_data["token_type"],
        "expires_in": token_data["expires_in"],
        "expires_at": token_data["expires_at"],
        "user": user.to_dict(),
    }


@auth_router.post("/register")
def register(payload: RegisterRequest):
    """Register a new learner account."""
    success, user, message = auth_service.register_user(
        username=payload.username,
        password=payload.password,
        confirm_password=payload.confirm_password,
        display_name=payload.display_name,
        require_admin_exists=False,  # Allow registration
    )
    if not success or not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    return {
        "status": "success",
        "message": message,
        "user": user.to_dict(),
    }


@auth_router.post("/logout")
def logout(auth_ctx: AuthContext = Depends(get_current_auth_context)):
    """Revoke current Access Token session and clear user tracker cache."""
    auth_service.revoke_session(auth_ctx.session_id, actor=auth_ctx.user)
    try:
        from vocab_backend.api_server import clear_user_trackers
        clear_user_trackers(auth_ctx.user.id)
    except Exception:
        pass
    return {"status": "success", "message": "Đã đăng xuất an toàn."}


@auth_router.get("/me")
def verify_session(
    user_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Verify that user Access Token and account are active."""
    verify_actor_user_id_match(current_user, user_id)
    return {
        "status": "active",
        "user": current_user.to_dict(),
    }


@auth_router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    auth_ctx: AuthContext = Depends(get_current_auth_context),
):
    """Change user password and rotate active Access Token sessions."""
    user = auth_ctx.user
    verify_actor_user_id_match(user, payload.user_id)

    try:
        success, message = auth_service.user_change_password(
            actor=user,
            old_password=payload.current_password,
            new_password=payload.new_password,
            confirm_new_password=payload.confirm_password,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    # Cấp token mới sau khi thu hồi toàn bộ phiên cũ
    refreshed_user = auth_service.user_repo.get_by_id(user.id) or user
    token_data = auth_service.issue_access_token(refreshed_user)
    return {
        "status": "success",
        "message": message,
        "access_token": token_data["access_token"],
        "token_type": token_data["token_type"],
        "expires_in": token_data["expires_in"],
        "expires_at": token_data["expires_at"],
    }
