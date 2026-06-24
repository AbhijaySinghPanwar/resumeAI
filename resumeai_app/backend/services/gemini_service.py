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
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            self._model = genai.GenerativeModel(self.MODEL_NAME)
            logger.info("GeminiService initialized with model %s", self.MODEL_NAME)
        except ImportError:
            self._init_error = (
                "google-generativeai is not installed. "
                "Run: py -m pip install google-generativeai"
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
                import google.generativeai as genai
                response = self._model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
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
