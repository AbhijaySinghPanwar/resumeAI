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
You are an elite Senior Technical Recruiter and Hiring Manager conducting an interview for a {company_preset} style company.

Task: Generate a highly personalized interview preparation guide for the candidate below based on their resume AND the target Job Description (JD).

JOB DESCRIPTION (PRIMARY SOURCE - MUST INFLUENCE 70% OF QUESTIONS):
{job_description}

CANDIDATE RESUME SUMMARY:
- Name: {name}
- Skills: {skills}
- Projects: {projects}
- Experience: {experience}
- Education: {education}

Rules & Strategy:
1. SEMANTIC MATCHING & GAPS: Analyze the JD for required skills/technologies. If the candidate lacks a required skill, generate specific "Gap-Based" questions (e.g., "Your resume doesn't mention X. How would you approach using X?").
2. PROJECT AWARENESS: Analyze the candidate's specific projects. Instead of "Tell me about your project", ask deep-dives like "Explain the architecture of your [Project Name] project" or "Why did you choose [Tech] for [Project Name]?".
3. NO DUPLICATES: Maintain semantic uniqueness. Do not ask the same concept twice.
4. PROGRESSION: Ensure difficulty progresses naturally (Easy -> Medium -> Hard -> Expert).
5. COMPANY PRESET: Adapt the style to '{company_preset}'. (e.g., Google = Algorithms/Scalability; Amazon = Leadership Principles).
6. REQUIRED CATEGORIES (3 categories only):
   - technical_questions: Questions testing JD-required tech stack, System Design, Coding concepts, and missing skills.
   - project_questions: Deep dives specifically referencing the candidate's actual projects.
   - behavioral_questions: STAR format questions, tailored to the role and company style.

Format Requirements:
Return ONLY a valid JSON object matching this schema. NO markdown formatting.
Each category must be a list of exactly 4-5 question objects.
Question Object Schema:
{{
  "question": "The actual interview question.",
  "difficulty": "Easy", // Must be Easy, Medium, Hard, or Expert
  "duration": "5 mins",
  "why_asked": "Why the recruiter is asking this.",
  "good_answer": "Key concepts a good answer should contain.",
  "sample_outline": "A brief outline of an ideal answer."
}}

JSON Output Schema:
{{
  "technical_questions": [ {{...}} ],
  "project_questions": [ {{...}} ],
  "behavioral_questions": [ {{...}} ]
}}
"""


def _summarize_resume(resume_data: Dict[str, Any]) -> Dict[str, str]:
    """Extract key resume fields for the prompt."""
    contact = resume_data.get("contact", {}) or {}
    name = contact.get("name", "Candidate")

    skills_obj = resume_data.get("skills", {}) or {}
    skills_flat = skills_obj.get("flat_list", [])
    skills_str = ", ".join(skills_flat) if skills_flat else "Not specified"

    projects = resume_data.get("projects", []) or []
    proj_parts = []
    for p in projects:
        pname = p.get("name", "")
        pdesc = p.get("description", "")
        tech = ", ".join((p.get("technologies", []) or []))
        bullets = " ".join((p.get("bullets", []) or []))
        proj_parts.append(f"Project '{pname}' ({tech}): {pdesc}. Details: {bullets}")
    projects_str = " | ".join(proj_parts) if proj_parts else "None listed"

    experience = resume_data.get("experience", []) or []
    exp_parts = []
    for e in experience:
        title = e.get("title", "")
        company = e.get("company", "")
        bullets = " ".join((e.get("bullets", []) or []))
        exp_parts.append(f"Role '{title}' at '{company}': {bullets}")
    experience_str = " | ".join(exp_parts) if exp_parts else "None listed"

    education = resume_data.get("education", []) or []
    edu_parts = []
    for e in education:
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

    def generate(self, resume_data: Dict[str, Any], job_description: str, company_preset: str = "Generic") -> dict:
        """
        Generate personalized interview questions.

        Args:
            resume_data:     Parsed resume dict from /api/parse
            job_description: Raw JD text
            company_preset:  The company style preset

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
            job_description=job_description.strip(),
            company_preset=company_preset,
            **summary,
        )
        try:
            # Temperature 0.85 to introduce controlled randomness and semantic variation
            raw = self._gemini.generate(prompt, temperature=0.85)
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
        
        def _make_q(q: str, diff: str) -> dict:
            return {
                "question": q,
                "difficulty": diff,
                "duration": "5 mins",
                "why_asked": "To assess basic competency.",
                "good_answer": "Structured response.",
                "sample_outline": "1. Intro. 2. Details. 3. Conclusion."
            }

        return {
            "technical_questions": [
                _make_q(f"Can you walk me through your experience with {skills.split(',')[0].strip() if skills != 'Not specified' else 'your primary technology'}?", "Medium"),
                _make_q("Describe a time when you had to debug a complex production issue. What was your approach?", "Hard"),
                _make_q("How would you design a RESTful API for a high-traffic web service?", "Expert"),
            ],
            "project_questions": [
                _make_q("Walk me through your most technically challenging project from start to finish.", "Medium"),
                _make_q("What was the biggest architectural decision you made in one of your projects and why?", "Hard"),
            ],
            "behavioral_questions": [
                _make_q("Tell me about a time when you had to deliver a project under a tight deadline.", "Medium"),
                _make_q("Describe a situation where you disagreed with a teammate's technical decision.", "Hard"),
            ],
        }
