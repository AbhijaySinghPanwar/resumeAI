"""
backend/services/bullet_improver.py — AI Resume Bullet Improver.

Uses Gemini to rewrite a single resume bullet into 3 variants:
  - ats_version:          Keyword-rich, quantified, ATS-optimised
  - professional_version: Polished, action-verb-first professional tone
  - concise_version:      ≤12 words, punchy one-liner
"""
from __future__ import annotations

import json
import logging
import re
from typing import Literal

from .gemini_service import GeminiService

logger = logging.getLogger(__name__)

Context = Literal["project", "experience"]

PROMPT_TEMPLATE = """\
You are an expert resume writer specializing in ATS optimization and recruiter psychology.

Task: Rewrite the resume bullet below into exactly 3 improved versions.

Bullet: "{bullet}"
Context: {context} ({context_label})

Rules:
- ats_version: Lead with a strong action verb. Include 2-3 relevant technical keywords naturally. Add quantified metrics (use realistic estimates if none given, e.g. "reduced latency by ~30%"). Keep to 1-2 lines. Optimise for ATS keyword scanning.
- professional_version: Polished, confident tone suited for senior hiring managers. Focus on impact and ownership. Avoid clichés. 1-2 lines.
- concise_version: 12 words or fewer. Maximum punch. Single most impressive takeaway.

Return ONLY valid JSON in this exact format, no markdown fences:
{{
  "ats_version": "...",
  "professional_version": "...",
  "concise_version": "..."
}}
"""


def _parse_json_response(raw: str) -> dict:
    """Extract JSON from Gemini response, handling markdown fences gracefully."""
    # Strip markdown code fences if present
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    return json.loads(raw)


class BulletImprover:
    """Rewrites resume bullets using Gemini AI."""

    def __init__(self, gemini: GeminiService) -> None:
        self._gemini = gemini

    def improve(self, bullet: str, context: Context = "experience") -> dict:
        """
        Generate 3 improved versions of a resume bullet.

        Args:
            bullet:  Original bullet text
            context: "project" or "experience"

        Returns:
            dict with ats_version, professional_version, concise_version
        """
        if not bullet or not bullet.strip():
            raise ValueError("bullet must not be empty")

        bullet = bullet.strip()
        context = context if context in ("project", "experience") else "experience"
        context_label = "project description" if context == "project" else "work experience"

        if not self._gemini.is_available:
            logger.warning("AI Provider: fallback - Reason: Gemini unavailable")
            return self._fallback(bullet, reason=self._gemini._init_error or "Gemini unavailable")

        prompt = PROMPT_TEMPLATE.format(bullet=bullet, context=context, context_label=context_label)
        try:
            raw = self._gemini.generate(prompt, temperature=0.7)
            result = _parse_json_response(raw)

            # Validate required keys
            for key in ("ats_version", "professional_version", "concise_version"):
                if key not in result or not result[key]:
                    result[key] = bullet

            result["provider"] = "gemini"
            result["fallback"] = False
            result["reason"] = None
            return result

        except json.JSONDecodeError as exc:
            logger.error("BulletImprover JSON parse error: %s", exc)
            logger.warning("AI Provider: fallback - Reason: JSON Parse Error")
            return self._fallback(bullet, reason="JSON Parse Error")
        except Exception as exc:
            logger.error("BulletImprover error: %s", exc)
            raise

    def _fallback(self, bullet: str, reason: str = "Unknown error") -> dict:
        """Return basic variants when Gemini is unavailable."""
        words = bullet.strip().rstrip(".")
        return {
            "ats_version": f"Developed and implemented {words.lower()} with measurable impact.",
            "professional_version": f"Led {words.lower()}, delivering results aligned with organizational goals.",
            "concise_version": words[:60] + ("…" if len(words) > 60 else ""),
            "provider": "fallback",
            "fallback": True,
            "reason": reason
        }
