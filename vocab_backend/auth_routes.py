"""Authentication and User Profile routes for Vocab Web Application.
Reuses src.auth.service.AuthService and src.data.user_repository without modifying existing files.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.auth.service import AuthService
from src.auth.security import validate_password, validate_username
from src.data.user_repository import User

logger = logging.getLogger("vocab_api.auth")
auth_router = APIRouter(prefix="/api/auth", tags=["auth"])
auth_service = AuthService()


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=6)
    confirm_password: str = Field(..., min_length=6)
    display_name: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    user_id: int
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
    """Authenticate user with username and password."""
    success, user, message = auth_service.authenticate(payload.username, payload.password)
    if not success or not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
        )
    return {
        "status": "success",
        "message": message,
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


@auth_router.get("/me")
def verify_session(user_id: int = Query(...)):
    """Verify that user account is active."""
    user = auth_service.verify_active_session(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên làm việc đã hết hạn hoặc tài khoản bị vô hiệu hóa.",
        )
    return {
        "status": "active",
        "user": user.to_dict(),
    }


@auth_router.post("/change-password")
def change_password(payload: ChangePasswordRequest):
    """Change user password."""
    user = auth_service.verify_active_session(payload.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không hợp lệ.")

    success, message = auth_service.change_password(
        user=user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        confirm_password=payload.confirm_password,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    return {"status": "success", "message": message}
