"""
backend/core/logger.py — Structured logging setup for ResumeAI.

Creates a named logger for each module.  All handlers are configured once here.
Supports INFO / WARNING / ERROR levels.

Usage:
    from core.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Resume uploaded", extra={"user_id": 42})
"""
from __future__ import annotations

import logging
import sys
from typing import Optional


_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure_root() -> None:
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a logger configured with ResumeAI's format."""
    _configure_root()
    return logging.getLogger(name or "resumeai")
