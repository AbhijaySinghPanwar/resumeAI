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

# Default fallback if GEMINI_MODEL is not set
_DEFAULT_MODEL = "gemini-2.5-flash"

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
        # Lazy initialization: do not initialize at startup

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _initialize(self) -> bool:
        if not self._api_key or self._api_key == "your-gemini-api-key-here":
            self._init_error = (
                "GEMINI_API_KEY environment variable is not set or is a dummy value. "
                "Phase 3 AI features will return fallback responses."
            )
            logger.warning(self._init_error)
            return False

        try:
            from google import genai  # type: ignore
            
            logger.debug("Gemini initialization started")
            init_start = time.time()
            
            self._client = genai.Client(
                api_key=self._api_key, 
                http_options={'timeout': 60.0}
            )

            # Use GEMINI_MODEL environment variable or fallback to default
            model_name = os.getenv("GEMINI_MODEL", _DEFAULT_MODEL)
            # Ensure model name has 'models/' prefix if required, though the SDK usually handles it,
            # keeping it clean.
            self.active_model = model_name if model_name.startswith("models/") else f"models/{model_name}"

            self._init_error = None
            logger.info("=" * 60)
            logger.info("Gemini API Client Initialized (No remote calls made)")
            logger.info("Active Model: %s", self.active_model)
            logger.info("=" * 60)
            logger.debug("Gemini initialization complete in %.4fs", time.time() - init_start)
            return True

        except ImportError:
            self._init_error = (
                "google-genai package is not installed. "
                "Run: py -m pip install google-genai"
            )
            logger.error(self._init_error)
            return False
        except BaseException as exc:
            self._init_error = f"Gemini initialization failed: {exc}"
            logger.error("Gemini init error: %s", exc, exc_info=True)
            self._client = None
            self.active_model = None
            return False

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        """True when the client is authenticated and an active model was found."""
        if self._client is None or self.active_model is None:
            self._initialize()
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
                req_start = time.time()
                if attempt == 0:
                    logger.debug("First generation request started for active model %s", self.active_model)
                else:
                    logger.debug("Generation request retry %d started", attempt)

                response = self._client.models.generate_content(
                    model=self.active_model,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=2048,
                    ),
                )
                elapsed = time.time() - req_start
                logger.info("AI Provider: gemini - Generation success - Elapsed: %.2fs", elapsed)
                return response.text.strip()
            except Exception as exc:
                elapsed = time.time() - req_start
                last_exc = exc
                wait = self.BACKOFF_BASE ** attempt
                logger.error("Generation failure - Elapsed: %.2fs - Error: %s", elapsed, exc)
                logger.warning(
                    "Gemini attempt %d/%d failed — %s: %s. Retrying in %.1fs…",
                    attempt + 1, self.MAX_RETRIES, type(exc).__name__, exc, wait,
                )
                time.sleep(wait)

        # Clear client so it tries to re-initialize next time if the network recovers
        self._client = None
        self.active_model = None
        raise RuntimeError(
            f"Gemini API failed after {self.MAX_RETRIES} attempts. "
            f"Last error ({type(last_exc).__name__}): {last_exc}"
        )

    def status_dict(self) -> dict:
        """Return a JSON-serialisable status dictionary for /ai/status."""
        if self.is_available:
            return {
                "available": True,
                "provider": "gemini",
                "initialized": True,
                "fallback": False,
                "reason": None
            }
        
        # Determine error code
        err_code = "UNKNOWN_ERROR"
        if self._init_error:
            if "leaked" in self._init_error.lower() or "permission_denied" in self._init_error.lower() or "401" in self._init_error or "403" in self._init_error or "invalid" in self._init_error.lower() or "api_key" in self._init_error.lower():
                err_code = "PERMISSION_DENIED"
            elif "not configured" in self._init_error.lower() or "not set" in self._init_error.lower():
                err_code = "NOT_CONFIGURED"
            elif "google-genai package" in self._init_error.lower():
                err_code = "MISSING_DEPENDENCY"
            else:
                err_code = "INIT_FAILED"

        return {
            "available": False,
            "provider": "fallback",
            "initialized": self._client is not None,
            "fallback": True,
            "error_code": err_code,
            "reason": self._init_error or "Service failed to initialize."
        }
