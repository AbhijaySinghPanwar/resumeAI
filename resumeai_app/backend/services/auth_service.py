"""
backend/services/auth_service.py — JWT authentication and password hashing.

Provides:
    hash_password()          — bcrypt hash
    verify_password()        — bcrypt verify
    create_access_token()    — signed JWT
    decode_access_token()    — verify + decode JWT
    get_current_user()       — FastAPI dependency: returns User or raises 401
    get_optional_user()      — FastAPI dependency: returns User | None (guest-friendly)
"""
from __future__ import annotations

import os, sys
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from core.config import settings
from core.logger import get_logger
from database.engine import get_db

logger = get_logger(__name__)

# ── Password Hashing ──────────────────────────────────────────────────────────

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return bcrypt hash of *plain* password."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*."""
    return _pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: int, email: str) -> str:
    """Create a signed JWT access token for the given user."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    logger.info("JWT issued for user_id=%d", user_id)
    return token


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT. Returns the payload dict.
    Raises HTTPException 401 on any failure.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError as exc:
        logger.warning("JWT decode failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI Dependencies ──────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
):
    """
    Require authenticated user. Raises 401 if token is missing or invalid.
    Inject as: current_user = Depends(get_current_user)
    """
    from repositories.user_repo import UserRepository

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    user_id = int(payload.get("sub", 0))
    user = UserRepository(db).get_by_id(user_id)
    if not user or not user.is_active:
        logger.warning("Auth failed: user_id=%d not found or inactive", user_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
):
    """
    Optionally authenticate the user. Returns User if valid token present, else None.
    Guest-friendly: existing endpoints use this to enable auto-save for logged-in users.
    """
    from repositories.user_repo import UserRepository

    if not credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload.get("sub", 0))
        return UserRepository(db).get_by_id(user_id)
    except HTTPException:
        return None
