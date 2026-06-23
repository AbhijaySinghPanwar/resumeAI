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


# ── Constants for Phase 2 Patch ────────────────────────────────────────────────
SKILL_ALIASES = {
    "mysql": "sql",
    "postgresql": "sql",
    "sqlite": "sql",
    "oracle": "sql",
    "database": "sql",

    "github": "git",
    "gitlab": "git",
    "version control": "git",

    "dsa": "data structures",
    "data structure and algorithms": "data structures",
    "data structures and algorithms": "data structures",

    "rest api": "rest apis",
    "api development": "rest apis",
    "backend api": "rest apis",

    "js": "javascript",
    "nodejs": "node.js",
    "problem-solving": "problem solving",

    "ai": "artificial intelligence",
    "machine learning": "artificial intelligence",
}

GENERIC_WORDS = {
    "backend", "developer", "engineer", "intern", "requirements",
    "responsibilities", "candidate", "position", "role", "team",
    "work", "experience", "company", "software", "data"
}


# ── Normalize helper ─────────────────────────────────────────────────────────

def _norm(skill: str) -> str:
    """Lowercase + strip + manual alias lookup."""
    s = skill.lower().strip()
    return SKILL_ALIASES.get(s, s)


# ── Unified resume skill extractor ───────────────────────────────────────────

def extract_all_resume_skills(parsed_resume: Dict[str, Any]) -> Set[str]:
    """
    Extract ALL canonical skills from a parsed resume dict.
    """
    found: Set[str] = set()

    # ── 1. Skills section ─────────────────────────────────────────────────
    skills_sec = parsed_resume.get("skills", {})
    for s in skills_sec.get("flat_list", []):
        found.add(s)
        for c in extract_skills_from_text(s):
            found.add(c)

    for cat in skills_sec.get("categories", []):
        for s in cat.get("skills", []):
            found.add(s)
            for c in extract_skills_from_text(s):
                found.add(c)

    # ── 2. Projects ───────────────────────────────────────────────────────
    for proj in parsed_resume.get("projects", []):
        for t in proj.get("technologies", []):
            found.add(t)
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

    found.discard("")
    found.discard(None)
    return found


def _is_match(jd_skill: str, resume_skills: Set[str], resume_skills_norm: Set[str]) -> bool:
    """
    Check if a JD skill matches any resume skill via:
    1. Exact string match (raw)
    2. Exact normalized/alias match (intersection)
    3. Fuzzy string matching
    4. Semantic SentenceTransformer similarity (> 0.75)
    """
    raw_jd = jd_skill.strip()
    jd_norm = _norm(jd_skill)

    # 1. Raw exact match
    if raw_jd in resume_skills:
        return True

    # 2. Normalized exact alias match
    if jd_norm in resume_skills_norm:
        return True

    # 3. Fuzzy match on normalized strings
    for rs_norm in resume_skills_norm:
        score = fuzz.token_sort_ratio(jd_norm, rs_norm)
        if score >= 85:
            return True

    # 4. Semantic similarity match (threshold > 0.75)
    try:
        from .embedding_engine import semantic_similarity
        # We compare against the raw original resume skills to preserve semantic context
        for rs in resume_skills:
            if semantic_similarity(raw_jd, rs) >= 0.75:
                return True
    except Exception:
        pass

    return False


def generate_skill_gap(
    parsed_resume: Dict[str, Any],
    parsed_jd: Any,  # ParsedJD or dict
) -> SkillGapResult:
    """
    Compute skill gap between a parsed resume and a parsed JD.
    """
    if hasattr(parsed_jd, "required_skills"):
        required = list(parsed_jd.required_skills)
        preferred = list(parsed_jd.preferred_skills)
    else:
        required = parsed_jd.get("required_skills", [])
        preferred = parsed_jd.get("preferred_skills", [])

    # Filter generic non-skill words from JD requirements
    required = [s for s in required if _norm(s) not in GENERIC_WORDS]
    preferred = [s for s in preferred if _norm(s) not in GENERIC_WORDS]

    resume_skills_raw = extract_all_resume_skills(parsed_resume)
    resume_skills_norm = {_norm(s) for s in resume_skills_raw}

    matched: List[str] = []
    missing: List[str] = []

    for jd_skill in required:
        if _is_match(jd_skill, resume_skills_raw, resume_skills_norm):
            matched.append(jd_skill)
        else:
            missing.append(jd_skill)

    recommended: List[str] = []
    for pref_skill in preferred:
        if not _is_match(pref_skill, resume_skills_raw, resume_skills_norm):
            recommended.append(pref_skill)

    total = len(required)
    match_pct = round((len(matched) / total * 100), 1) if total > 0 else 0.0

    return SkillGapResult(
        matched_skills=matched,
        missing_skills=missing,
        recommended_skills=recommended[:10],
        match_percentage=match_pct,
    )
