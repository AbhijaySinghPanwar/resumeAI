"""
backend/core/config.py — Centralized configuration via Pydantic Settings.

All secrets and environment-specific values are loaded from environment variables.
No secrets are hardcoded. Supports a .env file for local development.

Usage:
    from core.config import settings
    secret = settings.SECRET_KEY
"""
from __future__ import annotations

import secrets
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Defaults are safe for local development only — override in production.
    """

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    APP_NAME: str = "ResumeAI"
    APP_VERSION: str = "4.0.0"
    ENVIRONMENT: str = "development"        # development | staging | production
    DEBUG: bool = True

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = secrets.token_hex(32)   # Override in production!
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7    # 7 days

    # ── Database ──────────────────────────────────────────────────────────────
    # Default: SQLite (zero-config for local dev).
    # Set DATABASE_URL=postgresql://user:pass@host/db for production.
    DATABASE_URL: str = "sqlite:///./resumeai.db"

    # ── Gemini ────────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = ["*"]

    # ── Export ────────────────────────────────────────────────────────────────
    EXPORT_TEMP_DIR: str = "/tmp/resumeai_exports"


settings = Settings()
