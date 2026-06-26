"""
backend/services/gemini_service.py — Gemini API singleton with dynamic model discovery.

On startup the service:
  1. Lists all models available for this API key.
  2. Picks the best model from a preference list (gemini-2.5-flash > gemini-2.5-flash-lite >
     gemini-2.5-pro > first generateContent-capable model).
  3. Stores the chosen name in self.active_model.
  4. Falls back gracefully when no API key is set or the API is unreachable.

Never crashes the application — any failure is logged and is_available returns False.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional, List

from core.config import settings

logger = logging.getLogger(__name__)

# Preference order for model selection (exact names returned by the API)
_PREFERRED_MODELS: List[str] = [
    "models/gemini-2.5-flash",
    "models/gemini-2.5-flash-lite",
    "models/gemini-2.5-pro",
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-lite",
]

_GENERATE_CONTENT_ACTION = "generateContent"


class GeminiService:
    """
    Thread-safe Gemini API client with dynamic model discovery.

    Usage:
        svc = GeminiService()
        if svc.is_available:
            text = svc.generate("Write a haiku about Python")
    """

    MAX_RETRIES = 3
    BACKOFF_BASE = 1.5   # seconds — wait grows as 1.5^attempt

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key: str = api_key or settings.GEMINI_API_KEY
        self._client = None           # google.genai.Client instance
        self.active_model: Optional[str] = None   # e.g. "models/gemini-2.5-flash"
        self._init_error: Optional[str] = None
        self._initialize()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _pick_model(self, available: List[str]) -> Optional[str]:
        """
        Return the best model from *available* according to _PREFERRED_MODELS,
        falling back to the first generateContent-capable model.
        """
        available_set = set(available)
        for preferred in _PREFERRED_MODELS:
            if preferred in available_set:
                return preferred
        # Last resort: any generateContent model
        return available[0] if available else None

    def _list_generatecontent_models(self) -> List[str]:
        """
        Return all model names that support generateContent, sorted by name.
        Uses the new google-genai SDK.
        """
        from google import genai  # type: ignore
        models = []
        for m in self._client.models.list():
            actions = getattr(m, "supported_actions", None) or []
            if _GENERATE_CONTENT_ACTION in actions:
                models.append(m.name)
        return models

    def _initialize(self) -> None:
        if not self._api_key or self._api_key == "your-gemini-api-key-here":
            self._init_error = (
                "GEMINI_API_KEY environment variable is not set or is a dummy value. "
                "Phase 3 AI features will return fallback responses."
            )
            logger.warning(self._init_error)
            return

        try:
            from google import genai  # type: ignore
            self._client = genai.Client(api_key=self._api_key)

            # Discover available models
            available = self._list_generatecontent_models()
            if not available:
                self._init_error = (
                    "Gemini API key is valid but no generateContent models are available."
                )
                logger.error(self._init_error)
                return

            # Pick best model
            self.active_model = self._pick_model(available)
            logger.info("=" * 60)
            logger.info("Gemini API Connected")
            logger.info("Active Model: %s", self.active_model)
            logger.info("=" * 60)

        except ImportError:
            self._init_error = (
                "google-genai package is not installed. "
                "Run: py -m pip install google-genai"
            )
            logger.error(self._init_error)
        except BaseException as exc:
            self._init_error = f"Gemini initialization failed: {exc}"
            logger.error("Gemini init error: %s", exc, exc_info=True)

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        """True when the client is authenticated and an active model was found."""
        return self._client is not None and self.active_model is not None

    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Send *prompt* to Gemini and return the response text.

        Retries up to MAX_RETRIES times with exponential backoff.
        Raises RuntimeError if the service is not available or all retries fail.
        """
        if not self.is_available:
            raise RuntimeError(
                self._init_error or "Gemini service is not available."
            )

        from google import genai  # type: ignore

        last_exc: Optional[Exception] = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self._client.models.generate_content(
                    model=self.active_model,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=2048,
                    ),
                )
                return response.text.strip()
            except Exception as exc:
                last_exc = exc
                wait = self.BACKOFF_BASE ** attempt
                logger.warning(
                    "Gemini attempt %d/%d failed — %s: %s. Retrying in %.1fs…",
                    attempt + 1, self.MAX_RETRIES, type(exc).__name__, exc, wait,
                )
                time.sleep(wait)

        raise RuntimeError(
            f"Gemini API failed after {self.MAX_RETRIES} attempts. "
            f"Last error ({type(last_exc).__name__}): {last_exc}"
        )

    def status_dict(self) -> dict:
        """Return a JSON-serialisable status dictionary for /ai/status."""
        return {
            "available": self.is_available,
            "active_model": self.active_model,
        }
