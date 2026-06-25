"""
backend/routers/auth.py — Authentication endpoints.

POST /auth/signup   — register a new user
POST /auth/login    — authenticate and return JWT
GET  /auth/me       — get current user profile (protected)
POST /auth/logout   — client-side logout (stateless: instructs frontend to clear token)
GET  /auth/stats    — per-user dashboard statistics (protected)
"""
from __future__ import annotations

import os, sys
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from core.responses import success, error
from core.logger import get_logger
from database.engine import get_db
from database.models import User
from repositories.user_repo import UserRepository
from repositories.report_repo import ReportRepository
from services.auth_service import (
    hash_password, verify_password,
    create_access_token, get_current_user,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Request / Response Models ─────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str  = Field(..., min_length=2, max_length=120, examples=["Abhijay Singh Panwar"])
    email: str = Field(..., examples=["abhijay@example.com"])
    password: str = Field(..., min_length=8, max_length=128, examples=["securepassword123"])


class LoginRequest(BaseModel):
    email: str    = Field(..., examples=["abhijay@example.com"])
    password: str = Field(..., examples=["securepassword123"])


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/signup",
    summary="Register a new user",
    description="Create a new account. Returns a JWT access token on success.",
    status_code=201,
)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    repo = UserRepository(db)

    if repo.email_exists(req.email):
        logger.warning("Signup failed: duplicate email %s", req.email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    hashed = hash_password(req.password)
    user = repo.create(name=req.name, email=req.email, password_hash=hashed)
    token = create_access_token(user.id, user.email)

    logger.info("New user registered: id=%d email=%s", user.id, user.email)
    return success(
        data={"user": user.to_dict(), "access_token": token, "token_type": "bearer"},
        message="Account created successfully.",
        status_code=201,
    )


@router.post(
    "/login",
    summary="Authenticate and return JWT",
    description="Verify email + password. Returns a JWT access token.",
)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    user = repo.get_by_email(req.email)

    if not user or not verify_password(req.password, user.password_hash):
        logger.warning("Login failed for email=%s", req.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled.")

    token = create_access_token(user.id, user.email)
    logger.info("User logged in: id=%d email=%s", user.id, user.email)
    return success(
        data={"user": user.to_dict(), "access_token": token, "token_type": "bearer"},
        message="Login successful.",
    )


@router.get(
    "/me",
    summary="Get current user profile",
    description="Returns the authenticated user's profile. Requires Bearer token.",
)
def me(current_user: User = Depends(get_current_user)):
    return success(data=current_user.to_dict(), message="Profile retrieved.")


@router.post(
    "/logout",
    summary="Logout (client-side token invalidation)",
    description="Stateless logout. The client should discard the JWT token.",
)
def logout(current_user: User = Depends(get_current_user)):
    logger.info("User logged out: id=%d", current_user.id)
    return success(data=None, message="Logged out successfully.")


@router.get(
    "/stats",
    summary="Get dashboard statistics for current user",
    description="Returns aggregate stats: total resumes, avg ATS, avg match, total reports.",
)
def stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats_data = ReportRepository(db).get_user_stats(current_user.id)
    return success(data=stats_data, message="Stats retrieved.")
