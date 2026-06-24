"""
backend/services/gemini_service.py — Gemini API singleton wrapper.

Provides a single authenticated `generate` call used by all Phase 3 services.
Reads GEMINI_API_KEY from environment. Supports retry with exponential backoff.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)


class GeminiService:
    """
    Thread-safe Gemini API client.

    Usage:
        svc = GeminiService()
        text = svc.generate(prompt="Write a haiku about Python")
    """

    MODEL_NAME = "gemini-1.5-flash"
    MAX_RETRIES = 3
    BACKOFF_BASE = 1.5   # seconds

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self._model = None
        self._client = None
        self._init_error: Optional[str] = None
        self._initialize()

    def _initialize(self) -> None:
        if not self._api_key:
            self._init_error = (
                "GEMINI_API_KEY environment variable is not set. "
                "Phase 3 AI features will return fallback responses."
            )
            logger.warning(self._init_error)
            return
        try:
            from google import genai
            self._client = genai.Client(api_key=self._api_key)
            self._model = self.MODEL_NAME   # just store the name; client handles dispatch
            logger.info("GeminiService initialized with model %s (google-genai SDK)", self.MODEL_NAME)
        except ImportError:
            # Fallback: try the legacy google.generativeai package
            try:
                import google.generativeai as genai_legacy
                genai_legacy.configure(api_key=self._api_key)
                self._model = genai_legacy.GenerativeModel(self.MODEL_NAME)
                self._client = None   # signals legacy mode
                logger.info("GeminiService initialized with legacy SDK (model %s)", self.MODEL_NAME)
            except ImportError:
                self._init_error = (
                    "Neither google-genai nor google-generativeai is installed. "
                    "Run: py -m pip install google-genai"
                )
                logger.error(self._init_error)
        except Exception as exc:
            self._init_error = f"Gemini init failed: {exc}"
            logger.error(self._init_error)

    @property
    def is_available(self) -> bool:
        return self._model is not None

    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Send a prompt to Gemini and return the text response.

        Retries up to MAX_RETRIES times with exponential backoff.
        Raises RuntimeError if the service is not available.
        """
        if not self.is_available:
            raise RuntimeError(
                self._init_error or "Gemini service is not available."
            )

        last_exc: Optional[Exception] = None
        for attempt in range(self.MAX_RETRIES):
            try:
                # New google-genai SDK path
                if self._client is not None:
                    from google import genai
                    response = self._client.models.generate_content(
                        model=self._model,
                        contents=prompt,
                        config=genai.types.GenerateContentConfig(
                            temperature=temperature,
                            max_output_tokens=2048,
                        ),
                    )
                    return response.text.strip()
                else:
                    # Legacy google.generativeai fallback
                    import google.generativeai as genai_legacy
                    response = self._model.generate_content(
                        prompt,
                        generation_config=genai_legacy.GenerationConfig(
                            temperature=temperature,
                            max_output_tokens=2048,
                        ),
                    )
                    return response.text.strip()
            except Exception as exc:
                last_exc = exc
                wait = self.BACKOFF_BASE ** attempt
                logger.warning(
                    "Gemini attempt %d/%d failed (%s). Retrying in %.1fs…",
                    attempt + 1, self.MAX_RETRIES, exc, wait,
                )
                time.sleep(wait)

        raise RuntimeError(
            f"Gemini API failed after {self.MAX_RETRIES} attempts. Last error: {last_exc}"
        )
