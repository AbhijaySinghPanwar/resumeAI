"""
backend/services/interview_generator.py — AI Interview Question Generator.

Generates personalized interview questions from resume data + job description:
  - technical_questions:  Concept/coding/system design questions based on skills
  - project_questions:    Deep-dive questions on listed projects
  - behavioral_questions: STAR-format situational questions tailored to the role
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

from .gemini_service import GeminiService

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """\
You are an experienced technical interviewer at a top technology company.

Task: Generate realistic interview questions for the candidate below.

JOB DESCRIPTION:
{job_description}

CANDIDATE RESUME SUMMARY:
- Name: {name}
- Skills: {skills}
- Projects: {projects}
- Experience: {experience}
- Education: {education}

Rules:
- technical_questions: 5 questions testing technical depth based on the candidate's skills and the JD. Include at least 1 system design question if the JD mentions backend/distributed systems. Include at least 1 data structures/algorithms question if relevant.
- project_questions: 4 questions — one per major project listed (or repeat projects if fewer than 4). Ask about architecture decisions, challenges, trade-offs, and scalability.
- behavioral_questions: 4 STAR-format questions tailored to the role. Focus on teamwork, ownership, handling failure, and communication.

Each question must be specific to THIS candidate and THIS role — not generic.

Return ONLY valid JSON in this exact format, no markdown fences:
{{
  "technical_questions": ["...", "...", "...", "...", "..."],
  "project_questions": ["...", "...", "...", "..."],
  "behavioral_questions": ["...", "...", "...", "..."]
}}
"""


def _summarize_resume(resume_data: Dict[str, Any]) -> Dict[str, str]:
    """Extract key resume fields for the prompt."""
    contact = resume_data.get("contact", {}) or {}
    name = contact.get("name", "Candidate")

    skills_obj = resume_data.get("skills", {}) or {}
    skills_flat = skills_obj.get("flat_list", [])
    skills_str = ", ".join(skills_flat[:20]) if skills_flat else "Not specified"

    projects = resume_data.get("projects", []) or []
    proj_parts = []
    for p in projects[:4]:
        pname = p.get("name", "")
        pdesc = p.get("description", "")[:80]
        tech = ", ".join((p.get("technologies", []) or [])[:5])
        proj_parts.append(f"{pname}: {pdesc}" + (f" [{tech}]" if tech else ""))
    projects_str = " | ".join(proj_parts) if proj_parts else "None listed"

    experience = resume_data.get("experience", []) or []
    exp_parts = []
    for e in experience[:3]:
        title = e.get("title", "")
        company = e.get("company", "")
        exp_parts.append(f"{title} at {company}" if company else title)
    experience_str = " | ".join(exp_parts) if exp_parts else "None listed"

    education = resume_data.get("education", []) or []
    edu_parts = []
    for e in education[:2]:
        degree = e.get("degree", "")
        field = e.get("field_of_study", "")
        inst = e.get("institution", "")
        edu_parts.append(f"{degree} {field} from {inst}".strip())
    education_str = " | ".join(edu_parts) if edu_parts else "Not specified"

    return {
        "name": name,
        "skills": skills_str,
        "projects": projects_str,
        "experience": experience_str,
        "education": education_str,
    }


def _parse_json_response(raw: str) -> dict:
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    return json.loads(raw)


class InterviewGenerator:
    """Generates personalized interview questions using Gemini AI."""

    def __init__(self, gemini: GeminiService) -> None:
        self._gemini = gemini

    def generate(self, resume_data: Dict[str, Any], job_description: str) -> dict:
        """
        Generate categorized interview questions.

        Args:
            resume_data:     Parsed resume dict from /api/parse
            job_description: Raw JD text

        Returns:
            dict with technical_questions, project_questions, behavioral_questions
        """
        if not resume_data:
            raise ValueError("resume_data must not be empty")
        if not job_description or not job_description.strip():
            raise ValueError("job_description must not be empty")

        summary = _summarize_resume(resume_data)

        if not self._gemini.is_available:
            logger.warning("Gemini unavailable — returning fallback interview questions")
            return self._fallback(summary)

        prompt = PROMPT_TEMPLATE.format(
            job_description=job_description.strip()[:1500],
            **summary,
        )
        try:
            raw = self._gemini.generate(prompt, temperature=0.8)
            result = _parse_json_response(raw)

            for key in ("technical_questions", "project_questions", "behavioral_questions"):
                if key not in result or not isinstance(result[key], list):
                    result[key] = []

            return result

        except json.JSONDecodeError as exc:
            logger.error("InterviewGenerator JSON parse error: %s", exc)
            return self._fallback(summary)
        except Exception as exc:
            logger.error("InterviewGenerator error: %s", exc)
            raise

    def _fallback(self, summary: Dict[str, str]) -> dict:
        name = summary.get("name", "you")
        skills = summary.get("skills", "your skills")
        return {
            "technical_questions": [
                f"Can you walk me through your experience with {skills.split(',')[0].strip() if skills != 'Not specified' else 'your primary technology'}?",
                "Describe a time when you had to debug a complex production issue. What was your approach?",
                "How would you design a RESTful API for a high-traffic web service?",
                "Explain the difference between SQL and NoSQL databases and when you'd choose each.",
                "What is your approach to writing maintainable, testable code?",
            ],
            "project_questions": [
                "Walk me through your most technically challenging project from start to finish.",
                "What was the biggest architectural decision you made in one of your projects and why?",
                "How did you handle unexpected technical challenges during project development?",
                "If you were to rebuild one of your projects from scratch, what would you do differently?",
            ],
            "behavioral_questions": [
                "Tell me about a time when you had to deliver a project under a tight deadline.",
                "Describe a situation where you disagreed with a teammate's technical decision. How did you handle it?",
                "Give an example of when you proactively identified and fixed a problem before it became critical.",
                "Tell me about a project that failed or didn't meet expectations. What did you learn from it?",
            ],
        }
