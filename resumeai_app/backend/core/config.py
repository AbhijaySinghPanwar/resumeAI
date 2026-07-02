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
from pydantic import model_validator, Field

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
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"        # development | staging | production
    DEBUG: bool = True

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = Field(default="")   # Must be overridden in production
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

    # ── ML Engines ────────────────────────────────────────────────────────────
    EMBEDDING_ENGINE: str = "onnx"  # "onnx" or "pytorch"

    @model_validator(mode="after")
    def validate_settings(self) -> Settings:
        if self.ENVIRONMENT == "production":
            self.DEBUG = False
            if not self.SECRET_KEY:
                raise ValueError("SECRET_KEY must be explicitly configured in production!")
            if not self.ALLOWED_ORIGINS or self.ALLOWED_ORIGINS == ["*"]:
                raise ValueError("ALLOWED_ORIGINS must be explicitly configured in production (cannot be ['*']).")
        else:
            if not self.SECRET_KEY:
                import secrets
                self.SECRET_KEY = secrets.token_hex(32)
        return self

settings = Settings()
