"""
matching/skill_matcher.py — Resume ↔ Job Matching Engine (Phase 2).

Computes a weighted match score from 4 components:
  - Skill Match (40%): resume skills vs JD required skills
  - Semantic Similarity (30%): embedding-based similarity of experience/projects vs responsibilities
  - Experience Alignment (15%): internship, project count, years heuristics
  - Education Alignment (15%): degree and field relevance

Uses sentence-transformers/all-MiniLM-L6-v2 for semantic similarity.
Model is a cached singleton — never reloaded per request.
"""
from __future__ import annotations

import re
from typing import Dict, Any, List, Tuple

from .schemas import MatchResult, ComponentScores
from .jd_parser import ParsedJD, _extract_skills_from_text
from .gap_analyzer import generate_skill_gap, _extract_resume_skills, _normalize


# ── Grade boundaries ──────────────────────────────────────────────────────────
def _score_to_grade(score: int) -> str:
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B+"
    if score >= 60: return "B"
    if score >= 50: return "C"
    return "D"


# ── Component 1: Skill Match (40%) ────────────────────────────────────────────

def _compute_skill_score(parsed_resume: Dict[str, Any], parsed_jd: ParsedJD) -> float:
    """
    Compare resume skills against JD required + preferred skills.
    Returns 0–100.
    """
    required = list(parsed_jd.required_skills)
    preferred = list(parsed_jd.preferred_skills)

    if not required and not preferred:
        return 60.0  # No skills specified in JD → neutral

    gap = generate_skill_gap(parsed_resume, parsed_jd)
    matched_count = len(gap.matched_skills)
    total_required = len(required)

    # Base score: fraction of required skills matched
    base = (matched_count / total_required * 100) if total_required > 0 else 50.0

    # Bonus: preferred skills also matched
    if preferred:
        resume_skills_norm = {_normalize(s) for s in _extract_resume_skills(parsed_resume)}
        pref_matched = sum(
            1 for s in preferred
            if _normalize(s) in resume_skills_norm
        )
        pref_bonus = (pref_matched / len(preferred)) * 15
        base = min(100.0, base + pref_bonus)

    return round(base, 1)


# ── Component 2: Semantic Similarity (30%) ────────────────────────────────────

def _build_resume_corpus(parsed_resume: Dict[str, Any]) -> List[str]:
    """
    Build a list of text snippets representing resume content
    (experience bullets + project descriptions + summary).
    """
    snippets: List[str] = []

    # Summary
    summary = parsed_resume.get("summary", "") or ""
    if summary.strip():
        snippets.append(summary.strip())

    # Experience bullets
    for exp in parsed_resume.get("experience", []):
        bullets = exp.get("bullets", [])
        if bullets:
            snippets.append(" ".join(bullets[:5]))
        if exp.get("description"):
            snippets.append(exp["description"][:300])

    # Projects
    for proj in parsed_resume.get("projects", []):
        parts = [proj.get("name", "")]
        if proj.get("description"):
            parts.append(proj["description"])
        if proj.get("bullets"):
            parts.extend(proj["bullets"][:3])
        if parts:
            snippets.append(" ".join(parts))

    # Skills as a sentence for broad coverage
    skills_flat = parsed_resume.get("skills", {}).get("flat_list", [])
    if skills_flat:
        snippets.append("Skills: " + ", ".join(skills_flat[:20]))

    return [s for s in snippets if len(s.strip()) > 15]


def _compute_semantic_score(parsed_resume: Dict[str, Any], parsed_jd: ParsedJD) -> float:
    """
    Compute semantic similarity between resume content and JD responsibilities.
    Returns 0–100.
    """
    responsibilities = parsed_jd.responsibilities
    jd_keywords = parsed_jd.keywords

    if not responsibilities and not jd_keywords:
        return 55.0  # No responsibilities specified → neutral

    resume_snippets = _build_resume_corpus(parsed_resume)
    if not resume_snippets:
        return 20.0

    # Build query corpus: responsibilities + keyword summary
    query_texts: List[str] = []
    if responsibilities:
        query_texts.extend(responsibilities[:10])
    if jd_keywords:
        query_texts.append("Required skills: " + ", ".join(jd_keywords[:20]))

    try:
        from .embedding_engine import max_similarity_scores
        scores = max_similarity_scores(query_texts, resume_snippets)
        if not scores:
            return 40.0
        avg_sim = sum(scores) / len(scores)
        # Scale from [0, 1] to [0, 100]
        return round(min(100.0, avg_sim * 100 * 1.2), 1)  # slight boost for partial matches
    except Exception:
        # Graceful degradation: keyword overlap fallback
        return _semantic_fallback(resume_snippets, query_texts)


def _semantic_fallback(resume_snippets: List[str], jd_texts: List[str]) -> float:
    """Keyword-overlap fallback when embeddings are unavailable."""
    resume_text = " ".join(resume_snippets).lower()
    jd_text = " ".join(jd_texts).lower()

    jd_words = set(re.findall(r"\b\w{4,}\b", jd_text))
    if not jd_words:
        return 40.0

    matches = sum(1 for w in jd_words if w in resume_text)
    return round(min(95.0, (matches / len(jd_words)) * 100 * 1.5), 1)


# ── Component 3: Experience Alignment (15%) ───────────────────────────────────

def _compute_experience_score(parsed_resume: Dict[str, Any], parsed_jd: ParsedJD) -> float:
    """
    Heuristic experience alignment based on years, internships, projects.
    Returns 0–100.
    """
    score = 30.0  # base for having any content

    experience = parsed_resume.get("experience", [])
    projects = parsed_resume.get("projects", [])
    exp_reqs = parsed_jd.experience_requirements

    # Count formal experience entries
    if len(experience) >= 3:
        score += 30
    elif len(experience) == 2:
        score += 20
    elif len(experience) == 1:
        score += 10

    # Projects count toward experience (especially for freshers)
    if len(projects) >= 3:
        score += 20
    elif len(projects) >= 1:
        score += 10

    # Check if experience meets JD requirements
    if exp_reqs:
        exp_text = " ".join(exp_reqs).lower()
        is_entry_level = any(kw in exp_text for kw in [
            "entry", "junior", "fresher", "fresh graduate", "0-1", "0-2", "internship"
        ])
        has_internships = any(e.get("title", "").lower() in ("intern", "internship")
                               or "intern" in e.get("title", "").lower()
                               for e in experience)
        if is_entry_level:
            score = min(100, score + 20)  # Entry-level roles more forgiving
        if has_internships:
            score = min(100, score + 15)

    return round(min(100.0, score), 1)


# ── Component 4: Education Alignment (15%) ────────────────────────────────────

DEGREE_KEYWORDS = {
    "b.tech", "btech", "bachelor", "b.s.", "b.e.", "b.sc",
    "m.tech", "mtech", "master", "m.s.", "m.e.", "m.sc",
    "phd", "ph.d", "doctorate",
    "mba",
}

CS_FIELDS = {
    "computer science", "cs", "software engineering", "information technology",
    "it", "electronics", "electrical", "ece", "cse", "information systems",
    "artificial intelligence", "data science", "mathematics", "statistics",
}


def _compute_education_score(parsed_resume: Dict[str, Any], parsed_jd: ParsedJD) -> float:
    """
    Score based on degree relevance to JD.
    Returns 0–100.
    """
    education = parsed_resume.get("education", [])
    if not education:
        return 30.0  # Missing education section — mild penalty

    score = 40.0  # base for having education

    for edu in education:
        degree_str = (edu.get("degree", "") or "").lower()
        field_str = (edu.get("field_of_study", "") or "").lower()
        inst_str = (edu.get("institution", "") or "").lower()
        combined = f"{degree_str} {field_str} {inst_str}"

        # Has a relevant degree?
        if any(kw in combined for kw in DEGREE_KEYWORDS):
            score += 20
            break

    for edu in education:
        field_str = (edu.get("field_of_study", "") or "").lower()
        degree_str = (edu.get("degree", "") or "").lower()
        combined = f"{degree_str} {field_str}"
        if any(kw in combined for kw in CS_FIELDS):
            score += 25
            break

    # GPA bonus
    for edu in education:
        gpa_str = edu.get("gpa", "") or ""
        if gpa_str:
            try:
                nums = re.findall(r"[\d.]+", gpa_str)
                if nums:
                    gpa_val = float(nums[0])
                    if gpa_val > 4.0:  # /10 scale
                        if gpa_val >= 9.0:
                            score += 15
                        elif gpa_val >= 8.0:
                            score += 10
                    else:  # /4.0 scale
                        if gpa_val >= 3.7:
                            score += 15
                        elif gpa_val >= 3.3:
                            score += 10
            except (ValueError, IndexError):
                pass

    return round(min(100.0, score), 1)


# ── Main Matcher Class ────────────────────────────────────────────────────────

class SkillMatcher:
    """
    Resume ↔ Job Matching Engine.

    Usage:
        matcher = SkillMatcher()  # Singleton-safe — cheap to instantiate
        result = matcher.calculate_match_score(parsed_resume, parsed_jd)
    """

    # Weights (must sum to 1.0)
    WEIGHTS = {
        "skills": 0.40,
        "semantic": 0.30,
        "experience": 0.15,
        "education": 0.15,
    }

    def calculate_match_score(
        self,
        parsed_resume: Dict[str, Any],
        parsed_jd: ParsedJD,
    ) -> MatchResult:
        """
        Compute a comprehensive match score.

        Args:
            parsed_resume: Dict from ResumeParser.parse_*()
            parsed_jd: ParsedJD from parse_job_description()

        Returns:
            MatchResult with match_score, match_grade, component_scores,
            matched_skills, missing_skills, recommended_learning
        """
        # Component scores
        skill_score = _compute_skill_score(parsed_resume, parsed_jd)
        semantic_score = _compute_semantic_score(parsed_resume, parsed_jd)
        experience_score = _compute_experience_score(parsed_resume, parsed_jd)
        education_score = _compute_education_score(parsed_resume, parsed_jd)

        # Weighted overall
        overall = (
            skill_score * self.WEIGHTS["skills"]
            + semantic_score * self.WEIGHTS["semantic"]
            + experience_score * self.WEIGHTS["experience"]
            + education_score * self.WEIGHTS["education"]
        )
        overall = int(round(min(100.0, max(0.0, overall))))

        # Skill gap
        from .gap_analyzer import generate_skill_gap
        gap = generate_skill_gap(parsed_resume, parsed_jd)

        # Learning roadmap
        from .roadmap_generator import generate_learning_roadmap
        roadmap = generate_learning_roadmap(gap.missing_skills)

        return MatchResult(
            match_score=overall,
            match_grade=_score_to_grade(overall),
            component_scores=ComponentScores(
                skills=skill_score,
                semantic=semantic_score,
                experience=experience_score,
                education=education_score,
            ),
            matched_skills=gap.matched_skills,
            missing_skills=gap.missing_skills,
            recommended_skills=gap.recommended_skills,
            recommended_learning=roadmap,
        )
