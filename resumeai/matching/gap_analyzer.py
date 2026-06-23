"""
matching/gap_analyzer.py — Skill Gap Analyzer v2.

Extracts skills from ALL resume sections:
  - skills.flat_list and skills.categories
  - projects: technologies array + text scan
  - experience: bullets text scan
  - certifications: name + issuer scan
  - leadership: bullets + descriptions
  - summary

Uses the same CANONICAL_SKILLS dictionary as the JD parser for consistency.
Fuzzy matching (rapidfuzz) handles aliases: DSA → Data Structures.
"""
from __future__ import annotations

from typing import Dict, Any, List, Set
from rapidfuzz import fuzz

from .schemas import SkillGapResult
from .jd_parser import extract_skills_from_text, normalize_skill, _ALIAS_TO_CANONICAL


# ── Normalize helper ─────────────────────────────────────────────────────────

def _norm(skill: str) -> str:
    """Lowercase + canonical lookup."""
    return normalize_skill(skill).lower()


# ── Unified resume skill extractor ───────────────────────────────────────────

def extract_all_resume_skills(parsed_resume: Dict[str, Any]) -> Set[str]:
    """
    Extract ALL canonical skills from a parsed resume dict.

    Sources (in priority order):
    1. skills.flat_list + skills.categories
    2. projects: technologies[] + name + description + bullets
    3. experience: bullets + description + title
    4. certifications: name + issuer
    5. leadership: bullets + description
    6. summary
    """
    found: Set[str] = set()

    # ── 1. Skills section ─────────────────────────────────────────────────
    skills_sec = parsed_resume.get("skills", {})
    for s in skills_sec.get("flat_list", []):
        canonical = normalize_skill(s)
        if canonical:
            found.add(canonical)
        # Also scan the string itself for compound skills
        for c in extract_skills_from_text(s):
            found.add(c)

    for cat in skills_sec.get("categories", []):
        for s in cat.get("skills", []):
            canonical = normalize_skill(s)
            if canonical:
                found.add(canonical)
            for c in extract_skills_from_text(s):
                found.add(c)

    # ── 2. Projects ───────────────────────────────────────────────────────
    for proj in parsed_resume.get("projects", []):
        # Technologies array
        for t in proj.get("technologies", []):
            canonical = normalize_skill(t)
            found.add(canonical)
        # Full text scan of project content
        proj_text = " ".join(filter(None, [
            proj.get("name", ""),
            proj.get("description", ""),
            " ".join(proj.get("bullets", [])),
            " ".join(proj.get("technologies", [])),
        ]))
        for c in extract_skills_from_text(proj_text):
            found.add(c)

    # ── 3. Experience ─────────────────────────────────────────────────────
    for exp in parsed_resume.get("experience", []):
        exp_text = " ".join(filter(None, [
            exp.get("title", ""),
            exp.get("description", ""),
            " ".join(exp.get("bullets", [])),
        ]))
        for c in extract_skills_from_text(exp_text):
            found.add(c)

    # ── 4. Certifications ─────────────────────────────────────────────────
    for cert in parsed_resume.get("certifications", []):
        cert_text = " ".join(filter(None, [
            cert.get("name", ""),
            cert.get("issuer", ""),
            cert.get("description", ""),
        ]))
        for c in extract_skills_from_text(cert_text):
            found.add(c)

    # ── 5. Leadership ─────────────────────────────────────────────────────
    for lead in parsed_resume.get("leadership", []):
        lead_text = " ".join(filter(None, [
            lead.get("role", ""),
            lead.get("organization", ""),
            " ".join(lead.get("bullets", [])),
        ]))
        for c in extract_skills_from_text(lead_text):
            found.add(c)

    # ── 6. Summary ────────────────────────────────────────────────────────
    summary = parsed_resume.get("summary", "") or ""
    if summary:
        for c in extract_skills_from_text(summary):
            found.add(c)

    # Remove None/empty
    found.discard("")
    found.discard(None)
    return found


def _fuzzy_match_skill(jd_skill: str, resume_skills_norm: Set[str], threshold: int = 82) -> bool:
    """
    Check if a JD skill fuzzy-matches any resume skill above threshold.
    Also checks canonical normalization both ways.
    """
    jd_norm = _norm(jd_skill)

    # Exact canonical match first
    if jd_norm in resume_skills_norm:
        return True

    # Fuzzy match
    for rs in resume_skills_norm:
        score = fuzz.token_sort_ratio(jd_norm, rs)
        if score >= threshold:
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
        parsed_jd: ParsedJD object or dict

    Returns:
        SkillGapResult with matched_skills, missing_skills, recommended_skills, match_percentage
    """
    if hasattr(parsed_jd, "required_skills"):
        required = list(parsed_jd.required_skills)
        preferred = list(parsed_jd.preferred_skills)
    else:
        required = parsed_jd.get("required_skills", [])
        preferred = parsed_jd.get("preferred_skills", [])

    # Extract ALL resume skills from all sections
    resume_skills_raw = extract_all_resume_skills(parsed_resume)
    resume_skills_norm = {_norm(s) for s in resume_skills_raw}

    matched: List[str] = []
    missing: List[str] = []

    for jd_skill in required:
        if _fuzzy_match_skill(jd_skill, resume_skills_norm):
            matched.append(jd_skill)
        else:
            missing.append(jd_skill)

    # Recommended: preferred skills that are also missing from resume
    recommended: List[str] = []
    for pref_skill in preferred:
        if not _fuzzy_match_skill(pref_skill, resume_skills_norm):
            recommended.append(pref_skill)

    total = len(required)
    match_pct = round((len(matched) / total * 100), 1) if total > 0 else 0.0

    return SkillGapResult(
        matched_skills=matched,
        missing_skills=missing,
        recommended_skills=recommended[:10],
        match_percentage=match_pct,
    )
