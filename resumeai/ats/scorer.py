"""
ats/scorer.py — Score a parsed resume against a job description.

Produces a structured match report with per-category scores,
matched/missing skills, experience alignment, and education fit.

Design: purely functional, no ML, fully deterministic.
Same resume + same JD always produces the same score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class CategoryScore:
    category: str
    score: float          # 0.0 – 1.0
    matched: List[str]
    missing: List[str]
    weight: float         # contribution to overall score
    detail: str = ""


@dataclass
class MatchReport:
    overall_score: float                    # 0.0 – 100.0
    grade: str                              # A / B / C / D / F
    category_scores: List[CategoryScore]
    matched_skills: List[str]
    missing_skills: List[str]
    experience_years_required: Optional[int]
    experience_years_found: Optional[int]
    education_match: bool
    recommendation: str
    resume_version: str
    jd_hash: str

    def to_dict(self) -> dict:
        return {
            "overall_score": round(self.overall_score, 1),
            "grade": self.grade,
            "category_scores": [
                {
                    "category": c.category,
                    "score": round(c.score * 100, 1),
                    "weight": c.weight,
                    "matched": c.matched,
                    "missing": c.missing,
                    "detail": c.detail,
                }
                for c in self.category_scores
            ],
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "experience_years_required": self.experience_years_required,
            "experience_years_found": self.experience_years_found,
            "education_match": self.education_match,
            "recommendation": self.recommendation,
            "resume_version": self.resume_version,
            "jd_hash": self.jd_hash,
        }


# ── Score weights ─────────────────────────────────────────────────────────────
WEIGHTS = {
    "skills":      0.40,
    "experience":  0.30,
    "education":   0.15,
    "leadership":  0.10,
    "certifications": 0.05,
}

# Degree hierarchy (higher index = higher qualification)
DEGREE_HIERARCHY = [
    "high school", "secondary", "diploma", "associate",
    "bachelor", "b.tech", "btech", "b.e", "b.sc", "b.s",
    "master", "m.tech", "mtech", "m.sc", "m.s", "mba", "pgdm",
    "ph.d", "phd", "doctorate",
]

EXP_YEARS_RE = re.compile(
    r"(\d+)\+?\s*(?:to\s*\d+)?\s*(?:year|yr)s?\s*(?:of\s*)?(?:experience|exp)",
    re.IGNORECASE,
)


class ResumeScorer:
    """
    Score a v7.0.0 resume result against a job description string.

    Usage:
        scorer = ResumeScorer()
        report = scorer.score(parse_result, job_description_text)
        print(report.to_dict())
    """

    def score(
        self,
        result: Dict[str, Any],
        job_description: str,
    ) -> MatchReport:
        import hashlib
        jd_hash = hashlib.sha256(job_description.encode()).hexdigest()[:12]

        jd_skills = self._extract_skills_from_jd(job_description)
        jd_exp_years = self._extract_required_experience(job_description)
        jd_degrees = self._extract_required_degrees(job_description)

        # ── Skills score ──────────────────────────────────────────────────────
        resume_skills = self._get_resume_skills(result)
        skills_score, matched_skills, missing_skills = self._score_skills(
            resume_skills, jd_skills
        )

        # ── Experience score ──────────────────────────────────────────────────
        from resumeai.ats.exporters import _estimate_years_experience
        resume_years = _estimate_years_experience(result.get("experience", []))
        exp_score, exp_detail = self._score_experience(resume_years, jd_exp_years)

        # ── Education score ───────────────────────────────────────────────────
        edu_score, edu_match = self._score_education(result.get("education", []), jd_degrees)

        # ── Leadership score ──────────────────────────────────────────────────
        leadership_entries = result.get("leadership", [])
        leadership_score = min(1.0, len(leadership_entries) / 3.0) if leadership_entries else 0.0

        # ── Certifications score ──────────────────────────────────────────────
        jd_certs = self._extract_cert_keywords(job_description)
        resume_certs = [
            c.get("name", "").lower()
            for c in result.get("certifications", [])
            if c.get("name")
        ]
        cert_score = self._score_certifications(resume_certs, jd_certs)

        # ── Weighted overall score ────────────────────────────────────────────
        category_scores = [
            CategoryScore("skills", skills_score, matched_skills, missing_skills,
                          WEIGHTS["skills"], f"{len(matched_skills)}/{len(jd_skills)} skills matched"),
            CategoryScore("experience", exp_score, [], [], WEIGHTS["experience"], exp_detail),
            CategoryScore("education", edu_score, [], [], WEIGHTS["education"],
                          "Degree requirement met" if edu_match else "Degree requirement unclear/unmet"),
            CategoryScore("leadership", leadership_score, [], [], WEIGHTS["leadership"],
                          f"{len(leadership_entries)} leadership entries"),
            CategoryScore("certifications", cert_score, [], [], WEIGHTS["certifications"],
                          f"{len(jd_certs)} cert keywords in JD"),
        ]

        overall = sum(c.score * c.weight for c in category_scores) * 100

        return MatchReport(
            overall_score=overall,
            grade=self._grade(overall),
            category_scores=category_scores,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            experience_years_required=jd_exp_years,
            experience_years_found=resume_years,
            education_match=edu_match,
            recommendation=self._recommendation(overall),
            resume_version=result.get("version", "unknown"),
            jd_hash=jd_hash,
        )

    # ── Extraction helpers ────────────────────────────────────────────────────

    @staticmethod
    def _extract_skills_from_jd(jd: str) -> Set[str]:
        """Extract technology/skill keywords from job description."""
        from resumeai.extractors.projects import TECH_KEYWORDS
        jd_lower = jd.lower()
        found = set()
        for tech in TECH_KEYWORDS:
            if re.search(rf"\b{re.escape(tech)}\b", jd_lower):
                found.add(tech)
        # Also extract capitalized words that look like tools/frameworks
        capitalized = re.findall(r"\b[A-Z][a-zA-Z]+(?:\.[a-zA-Z]+)?\b", jd)
        for word in capitalized:
            if len(word) > 2 and word not in {"The", "This", "That", "With", "From",
                                               "Must", "Will", "Have", "Been", "They"}:
                found.add(word.lower())
        return found

    @staticmethod
    def _extract_required_experience(jd: str) -> Optional[int]:
        m = EXP_YEARS_RE.search(jd)
        if m:
            return int(m.group(1))
        return None

    @staticmethod
    def _extract_required_degrees(jd: str) -> List[str]:
        jd_lower = jd.lower()
        return [d for d in DEGREE_HIERARCHY if re.search(rf"\b{re.escape(d)}\b", jd_lower)]

    @staticmethod
    def _extract_cert_keywords(jd: str) -> List[str]:
        cert_patterns = [
            r"\b(?:aws|azure|gcp|google cloud)\s+certif\w+",
            r"\bcertified\s+\w+",
            r"\bpmp\b", r"\bcissp\b", r"\bccna\b", r"\bcpa\b",
        ]
        found = []
        for pattern in cert_patterns:
            matches = re.findall(pattern, jd, re.IGNORECASE)
            found.extend(m.lower() for m in matches)
        return found

    @staticmethod
    def _get_resume_skills(result: Dict[str, Any]) -> Set[str]:
        skills_obj = result.get("skills", {})
        flat = set(s.lower() for s in skills_obj.get("flat_list", []))
        # Also extract skill-like tokens from experience bullets
        for exp in result.get("experience", []):
            for bullet in exp.get("bullets", []):
                from resumeai.extractors.projects import TECH_KEYWORDS
                bullet_lower = bullet.lower()
                for tech in TECH_KEYWORDS:
                    if re.search(rf"\b{re.escape(tech)}\b", bullet_lower):
                        flat.add(tech)
        return flat

    # ── Scoring helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _score_skills(
        resume_skills: Set[str], jd_skills: Set[str]
    ) -> Tuple[float, List[str], List[str]]:
        if not jd_skills:
            return 1.0, [], []
        matched = sorted(resume_skills & jd_skills)
        missing = sorted(jd_skills - resume_skills)
        score = len(matched) / len(jd_skills)
        return min(score, 1.0), matched, missing

    @staticmethod
    def _score_experience(
        resume_years: Optional[int], required_years: Optional[int]
    ) -> Tuple[float, str]:
        if required_years is None:
            return 0.8, "Experience requirement not specified in JD"
        if resume_years is None:
            return 0.4, "Could not determine candidate's years of experience"
        if resume_years >= required_years:
            return 1.0, f"{resume_years} years found, {required_years} required ✓"
        ratio = resume_years / required_years
        return ratio, f"{resume_years} years found, {required_years} required (gap: {required_years - resume_years}yr)"

    @staticmethod
    def _score_education(
        education: List[Dict], required_degrees: List[str]
    ) -> Tuple[float, bool]:
        if not required_degrees:
            return 0.8, False  # No requirement stated

        required_min = max(
            (DEGREE_HIERARCHY.index(d) for d in required_degrees if d in DEGREE_HIERARCHY),
            default=0,
        )

        resume_max = 0
        for edu in education:
            degree_text = (edu.get("degree") or "").lower()
            for i, level in enumerate(DEGREE_HIERARCHY):
                if re.search(rf"\b{re.escape(level)}\b", degree_text):
                    resume_max = max(resume_max, i)

        if resume_max >= required_min:
            return 1.0, True
        elif resume_max > 0:
            return 0.6, False
        return 0.3, False

    @staticmethod
    def _score_certifications(
        resume_certs: List[str], jd_certs: List[str]
    ) -> float:
        if not jd_certs:
            return 0.8
        if not resume_certs:
            return 0.0
        matches = sum(
            1 for jc in jd_certs
            if any(jc in rc or rc in jc for rc in resume_certs)
        )
        return min(matches / len(jd_certs), 1.0)

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 85:   return "A"
        if score >= 70:   return "B"
        if score >= 55:   return "C"
        if score >= 40:   return "D"
        return "F"

    @staticmethod
    def _recommendation(score: float) -> str:
        if score >= 85:   return "Strong match — recommend for interview"
        if score >= 70:   return "Good match — recommend for screening call"
        if score >= 55:   return "Partial match — consider with reservations"
        if score >= 40:   return "Weak match — significant skill gaps present"
        return "Poor match — does not meet minimum requirements"
