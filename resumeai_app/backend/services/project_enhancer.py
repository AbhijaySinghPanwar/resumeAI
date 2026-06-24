"""
backend/services/project_enhancer.py — AI Project Description Enhancer.

Rewrites a project description into 3 professional variants:
  - ats_version:       Keyword-heavy, ATS-optimized
  - technical_version: Architecture and tech-stack focused for technical reviewers
  - recruiter_version: Business impact and value-driven for non-technical hiring managers
"""
from __future__ import annotations

import json
import logging
import re

from .gemini_service import GeminiService

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """\
You are a senior technical writer and resume expert.

Task: Rewrite the project description below into exactly 3 professional versions.

Project Name: "{project_name}"
Description: "{description}"

Rules:
- ats_version: Include relevant technical keywords (programming languages, frameworks, tools). Mention architecture if inferable. Use action verbs. Quantify impact with realistic estimates (e.g., "~40% reduction in response time"). 2-3 sentences. Optimised for ATS scanning.
- technical_version: Emphasise system design, architecture decisions, tech stack choices, and engineering complexity. Written for a senior engineer reviewer. 2-3 sentences.
- recruiter_version: Focus on business problem solved, user impact, and value delivered. Avoid jargon. Written for a non-technical hiring manager. 1-2 sentences.

Return ONLY valid JSON in this exact format, no markdown fences:
{{
  "ats_version": "...",
  "technical_version": "...",
  "recruiter_version": "..."
}}
"""


def _parse_json_response(raw: str) -> dict:
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    return json.loads(raw)


class ProjectEnhancer:
    """Enhances project descriptions using Gemini AI."""

    def __init__(self, gemini: GeminiService) -> None:
        self._gemini = gemini

    def enhance(self, project_name: str, description: str) -> dict:
        """
        Generate 3 enhanced descriptions for a project.

        Args:
            project_name: Name of the project
            description:  Original project description

        Returns:
            dict with ats_version, technical_version, recruiter_version
        """
        if not project_name or not project_name.strip():
            raise ValueError("project_name must not be empty")
        if not description or not description.strip():
            raise ValueError("description must not be empty")

        project_name = project_name.strip()
        description = description.strip()

        if not self._gemini.is_available:
            logger.warning("Gemini unavailable — returning fallback project descriptions")
            return self._fallback(project_name, description)

        prompt = PROMPT_TEMPLATE.format(
            project_name=project_name,
            description=description,
        )
        try:
            raw = self._gemini.generate(prompt, temperature=0.7)
            result = _parse_json_response(raw)

            for key in ("ats_version", "technical_version", "recruiter_version"):
                if key not in result or not result[key]:
                    result[key] = description

            return result

        except json.JSONDecodeError as exc:
            logger.error("ProjectEnhancer JSON parse error: %s", exc)
            return self._fallback(project_name, description)
        except Exception as exc:
            logger.error("ProjectEnhancer error: %s", exc)
            raise

    def _fallback(self, project_name: str, description: str) -> dict:
        return {
            "ats_version": (
                f"Developed {project_name}: {description} "
                "Implemented using modern technologies with focus on performance and scalability."
            ),
            "technical_version": (
                f"Engineered {project_name} with emphasis on clean architecture and maintainability. "
                f"{description}"
            ),
            "recruiter_version": (
                f"Built {project_name} to solve a real-world problem, "
                "delivering measurable value to end users."
            ),
        }
