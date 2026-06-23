"""
matching/gap_analyzer.py — Skill Gap Analyzer for Phase 2.

Computes matched_skills, missing_skills, recommended_skills
given a parsed resume and parsed JD.
"""
from __future__ import annotations

from typing import Dict, Any, List, Set
from rapidfuzz import fuzz, process as rfprocess

from .schemas import SkillGapResult
from .jd_parser import SKILL_NORMALIZATION


# ── Normalization helpers ─────────────────────────────────────────────────────

def _normalize(skill: str) -> str:
    """Lowercase + normalize a skill string."""
    key = skill.strip().lower()
    return SKILL_NORMALIZATION.get(key, skill.strip()).lower()


def _extract_resume_skills(parsed_resume: Dict[str, Any]) -> Set[str]:
    """
    Extract all skills from the resume dict.
    Sources: skills.flat_list, skills.categories, projects (tech arrays + text),
             experience (bullets), summary.
    """
    raw_skills: Set[str] = set()

    # Primary: skills section
    skills_sec = parsed_resume.get("skills", {})
    flat = skills_sec.get("flat_list", [])
    for s in flat:
        raw_skills.add(s.strip())

    cats = skills_sec.get("categories", [])
    for cat in cats:
        for s in cat.get("skills", []):
            raw_skills.add(s.strip())

    # Secondary: projects technologies array + scan text
    from .jd_parser import _extract_skills_from_text
    for proj in parsed_resume.get("projects", []):
        for t in proj.get("technologies", []):
            raw_skills.add(t.strip())
        # Scan project text
        proj_text = " ".join([
            proj.get("name", ""),
            proj.get("description", ""),
            " ".join(proj.get("bullets", [])),
        ])
        for skill in _extract_skills_from_text(proj_text):
            raw_skills.add(skill)

    # Tertiary: experience bullets
    for exp in parsed_resume.get("experience", []):
        exp_text = " ".join(exp.get("bullets", []))
        for skill in _extract_skills_from_text(exp_text):
            raw_skills.add(skill)

    # Summary scan
    summary = parsed_resume.get("summary", "") or ""
    for skill in _extract_skills_from_text(summary):
        raw_skills.add(skill)

    return raw_skills


def _fuzzy_match(skill: str, candidates: Set[str], threshold: int = 82) -> bool:
    """
    Return True if skill fuzzy-matches any candidate above threshold.
    Uses token_sort_ratio for robustness against word-order differences.
    """
    if not candidates:
        return False
    skill_norm = skill.lower().strip()
    for cand in candidates:
        ratio = fuzz.token_sort_ratio(skill_norm, cand.lower().strip())
        if ratio >= threshold:
            return True
    return False


def generate_skill_gap(
    parsed_resume: Dict[str, Any],
    parsed_jd: Any,  # ParsedJD or dict
) -> SkillGapResult:
    """
    Compute skill gap between a parsed resume and a parsed JD.

    Args:
        parsed_resume: Dict from ResumeParser.parse_*()
        parsed_jd: ParsedJD object or dict with required_skills, preferred_skills

    Returns:
        SkillGapResult with matched_skills, missing_skills, recommended_skills
    """
    # Normalize JD input
    if hasattr(parsed_jd, "required_skills"):
        required = list(parsed_jd.required_skills)
        preferred = list(parsed_jd.preferred_skills)
    else:
        required = parsed_jd.get("required_skills", [])
        preferred = parsed_jd.get("preferred_skills", [])

    # Extract all resume skills
    resume_skills = _extract_resume_skills(parsed_resume)
    resume_skills_normalized = {_normalize(s) for s in resume_skills}

    matched: List[str] = []
    missing: List[str] = []

    for jd_skill in required:
        jd_norm = _normalize(jd_skill)
        # Exact match first
        if jd_norm in resume_skills_normalized:
            matched.append(jd_skill)
        # Fuzzy match fallback
        elif _fuzzy_match(jd_norm, resume_skills_normalized):
            matched.append(jd_skill)
        else:
            missing.append(jd_skill)

    # Recommended: preferred skills that are also missing
    recommended: List[str] = []
    for pref_skill in preferred:
        pref_norm = _normalize(pref_skill)
        if pref_norm not in resume_skills_normalized and not _fuzzy_match(pref_norm, resume_skills_normalized):
            recommended.append(pref_skill)

    total = len(required)
    match_pct = round((len(matched) / total * 100), 1) if total > 0 else 0.0

    return SkillGapResult(
        matched_skills=matched,
        missing_skills=missing,
        recommended_skills=recommended[:10],
        match_percentage=match_pct,
    )
