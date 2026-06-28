"""
matching/gap_analyzer.py — Skill Gap Analyzer (Phase 4.2 + hotfix).

Fixes:
- Scans other_section.blocks (catches Strengths & Interests, etc.)
- MySQL/MariaDB → SQL inference (database implies query language)
- PostgreSQL → SQL inference
- Node.js → JavaScript inference
- All 12 resume sections covered
- raw_lines fallback for pre-patch stored parses
"""
from __future__ import annotations

from typing import Dict, Any, List, Set
from rapidfuzz import fuzz

from .schemas import SkillGapResult
from .jd_parser import extract_skills_from_text, normalize_skill, _ALIAS_TO_CANONICAL


# ── Constants ─────────────────────────────────────────────────────────────────
SKILL_ALIASES = {
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
    "aws console": "aws",
}

# Skills that imply other skills (e.g. knowing MySQL means you know SQL)
SKILL_IMPLICATIONS: Dict[str, List[str]] = {
    "MySQL":        ["SQL"],
    "PostgreSQL":   ["SQL"],
    "SQLite":       ["SQL"],
    "Oracle":       ["SQL"],
    "MariaDB":      ["SQL"],
    "Node.js":      ["JavaScript"],
    "Express.js":   ["Node.js", "JavaScript"],
    "Next.js":      ["React", "JavaScript"],
    "React":        ["JavaScript"],
    "Angular":      ["JavaScript", "TypeScript"],
    "Vue.js":       ["JavaScript"],
    "Django":       ["Python"],
    "Flask":        ["Python"],
    "FastAPI":      ["Python"],
    "PyTorch":      ["Python"],
    "TensorFlow":   ["Python"],
    "Scikit-learn": ["Python"],
    "Pandas":       ["Python"],
    "NumPy":        ["Python"],
    "Spring Boot":  ["Java"],
    "Ruby on Rails": ["Ruby"],
    "Laravel":      ["PHP"],
}

GENERIC_WORDS = {
    "backend", "developer", "engineer", "intern", "requirements",
    "responsibilities", "candidate", "position", "role", "team",
    "work", "experience", "company", "software", "data",
}


def _norm(skill: str) -> str:
    """Lowercase + strip + manual alias lookup."""
    s = skill.lower().strip()
    return SKILL_ALIASES.get(s, s)


def _scan_text(*parts) -> Set[str]:
    """Helper: join non-None text parts and extract canonical skills."""
    text = " ".join(p for p in parts if p)
    return set(extract_skills_from_text(text)) if text.strip() else set()


def _expand_with_implications(found: Set[str]) -> Set[str]:
    """
    Expand a skill set with implied skills.
    e.g. MySQL → add SQL; Node.js → add JavaScript.
    """
    implied: Set[str] = set()
    for skill in list(found):
        for implied_skill in SKILL_IMPLICATIONS.get(skill, []):
            implied.add(implied_skill)
    return found | implied


def extract_all_resume_skills(parsed_resume: Dict[str, Any]) -> Set[str]:
    """
    Extract ALL canonical skills from a parsed resume dict.
    Covers every section including:
    - Skills (flat_list + categories)
    - Projects (technologies + bullets + raw_lines fallback)
    - Experience
    - Certifications
    - Leadership
    - Achievements
    - Hackathons
    - Research / Publications
    - Open Source
    - Technical Blogs
    - Education (field + coursework)
    - Summary
    - other_section.blocks (catches Strengths & Interests etc.)

    Also expands with implied skills (MySQL→SQL, Node.js→JavaScript).
    """
    found: Set[str] = set()

    # ── 1. Skills section ─────────────────────────────────────────────────
    skills_sec = parsed_resume.get("skills", {}) or {}
    flat_list = skills_sec.get("flat_list", []) or []
    for s in flat_list:
        if s:
            found.add(s)
            found.update(extract_skills_from_text(s))

    for cat in (skills_sec.get("categories", []) or []):
        # Support both "name" and "category" keys (extractor uses "category")
        for cat_skill in (cat.get("skills", []) or []):
            if cat_skill:
                found.add(cat_skill)
                found.update(extract_skills_from_text(cat_skill))
        # Scan category name too (e.g. "Frameworks & Tools")
        cat_name = cat.get("name", "") or cat.get("category", "") or ""
        if cat_name:
            found.update(extract_skills_from_text(cat_name))

    # Also scan skills raw_lines if present
    for raw in (skills_sec.get("raw_lines", []) or []):
        if raw:
            found.update(extract_skills_from_text(raw))

    # ── 2. Projects (with raw_lines fallback for tech recovery) ───────────
    for proj in (parsed_resume.get("projects", []) or []):
        for t in (proj.get("technologies", []) or []):
            if t:
                found.add(t)
                found.update(extract_skills_from_text(str(t)))

        proj_text = " ".join(filter(None, [
            proj.get("name", ""),
            proj.get("description", ""),
            " ".join(proj.get("bullets", []) or []),
            " ".join(str(x) for x in (proj.get("technologies", []) or [])),
        ]))
        found.update(extract_skills_from_text(proj_text))

        raw_lines = proj.get("raw_lines", []) or []
        if raw_lines:
            raw_text = " ".join(raw_lines)
            found.update(extract_skills_from_text(raw_text))

    # ── 3. Experience ─────────────────────────────────────────────────────
    for exp in (parsed_resume.get("experience", []) or []):
        found.update(_scan_text(
            exp.get("title", ""),
            exp.get("company", ""),
            exp.get("description", ""),
            " ".join(exp.get("bullets", []) or []),
        ))

    # ── 4. Certifications ─────────────────────────────────────────────────
    for cert in (parsed_resume.get("certifications", []) or []):
        found.update(_scan_text(
            cert.get("name", ""),
            cert.get("issuer", ""),
            cert.get("description", ""),
        ))

    # ── 5. Leadership ─────────────────────────────────────────────────────
    for lead in (parsed_resume.get("leadership", []) or []):
        found.update(_scan_text(
            lead.get("role", ""),
            lead.get("organization", ""),
            " ".join(lead.get("bullets", []) or []),
            lead.get("description", ""),
        ))

    # ── 6. Achievements ───────────────────────────────────────────────────
    for ach in (parsed_resume.get("achievements", []) or []):
        if isinstance(ach, str):
            found.update(extract_skills_from_text(ach))
        elif isinstance(ach, dict):
            found.update(_scan_text(
                ach.get("title", ""),
                ach.get("description", ""),
            ))

    # ── 7. Hackathons ─────────────────────────────────────────────────────
    for hack in (parsed_resume.get("hackathons", []) or []):
        if isinstance(hack, dict):
            found.update(_scan_text(
                hack.get("name", ""),
                hack.get("description", ""),
                " ".join(hack.get("technologies", []) or []),
                " ".join(hack.get("bullets", []) or []),
            ))

    # ── 8. Research / Publications ────────────────────────────────────────
    for res in (parsed_resume.get("research", []) or []):
        if isinstance(res, dict):
            found.update(_scan_text(
                res.get("title", ""),
                res.get("description", ""),
                " ".join(res.get("technologies", []) or []),
            ))

    for pub in (parsed_resume.get("publications", []) or []):
        if isinstance(pub, dict):
            found.update(_scan_text(
                pub.get("title", ""),
                pub.get("abstract", ""),
                pub.get("description", ""),
            ))

    # ── 9. Open Source ────────────────────────────────────────────────────
    for oss in (parsed_resume.get("open_source", []) or []):
        if isinstance(oss, dict):
            found.update(_scan_text(
                oss.get("name", ""),
                oss.get("description", ""),
                " ".join(oss.get("technologies", []) or []),
                " ".join(oss.get("bullets", []) or []),
            ))

    # ── 10. Technical Blogs ───────────────────────────────────────────────
    for blog in (parsed_resume.get("blogs", []) or []):
        if isinstance(blog, dict):
            found.update(_scan_text(blog.get("title", ""), blog.get("description", "")))
        elif isinstance(blog, str):
            found.update(extract_skills_from_text(blog))

    # ── 11. Coursework / Education ────────────────────────────────────────
    for edu in (parsed_resume.get("education", []) or []):
        if isinstance(edu, dict):
            coursework = edu.get("coursework", "") or ""
            found.update(_scan_text(
                edu.get("field_of_study", ""),
                coursework if isinstance(coursework, str) else " ".join(coursework),
            ))

    # ── 12. Summary ───────────────────────────────────────────────────────
    summary = parsed_resume.get("summary", "") or ""
    if summary:
        found.update(extract_skills_from_text(summary))

    # ── 13. other_section.blocks ─────────────────────────────────────────
    # This catches "Strengths & Interests", "Achievements", and any other
    # unclassified sections from the parser.
    other_sec = parsed_resume.get("other_section", {}) or {}
    for block in (other_sec.get("blocks", []) or []):
        if isinstance(block, dict):
            # Scan block title + all content lines
            block_text = " ".join(filter(None, [
                block.get("title", ""),
                block.get("content", ""),
                " ".join(block.get("lines", []) or []),
                " ".join(block.get("bullets", []) or []),
            ]))
            if block_text.strip():
                found.update(extract_skills_from_text(block_text))
        elif isinstance(block, str):
            found.update(extract_skills_from_text(block))

    found.discard("")
    found.discard(None)

    # ── Expand with implied skills ────────────────────────────────────────
    found = _expand_with_implications(found)

    return found


def _is_match(jd_skill: str, resume_skills: Set[str], resume_skills_norm: Set[str]) -> bool:
    """
    Check if a JD skill matches any resume skill via:
    1. Exact string match (raw)
    2. Exact normalized/alias match
    3. Fuzzy string matching (>=82 token sort ratio)
    """
    raw_jd = jd_skill.strip()
    jd_norm = _norm(jd_skill)

    # 1. Raw exact match
    if raw_jd in resume_skills:
        return True

    # 2. Normalized exact alias match
    if jd_norm in resume_skills_norm:
        return True

    # 3. Fuzzy match on normalized strings (lowered threshold: 82)
    for rs_norm in resume_skills_norm:
        score = fuzz.token_sort_ratio(jd_norm, rs_norm)
        if score >= 82:
            return True

    # 4. Semantic similarity match (only when embeddings available)
    try:
        from .embedding_engine import semantic_similarity, is_available
        if is_available():
            for rs in resume_skills:
                if semantic_similarity(raw_jd, rs) >= 0.75:
                    return True
    except Exception:
        pass

    return False


def generate_skill_gap(
    parsed_resume: Dict[str, Any],
    parsed_jd: Any,
) -> SkillGapResult:
    """Compute skill gap between a parsed resume and a parsed JD."""
    if isinstance(parsed_jd, dict):
        required = parsed_jd.get("required_skills", [])
        preferred = parsed_jd.get("preferred_skills", [])
    else:
        required = list(getattr(parsed_jd, "required_skills", []))
        preferred = list(getattr(parsed_jd, "preferred_skills", []))

    required = [s for s in required if _norm(s) not in GENERIC_WORDS]
    preferred = [s for s in preferred if _norm(s) not in GENERIC_WORDS]

    resume_skills_raw = extract_all_resume_skills(parsed_resume)
    resume_skills_norm = {_norm(s) for s in resume_skills_raw}

    matched: List[str] = []
    missing: List[str] = []

    if not required and preferred:
        benchmark_skills = preferred
        is_preferred_only = True
    else:
        benchmark_skills = required
        is_preferred_only = False

    for jd_skill in benchmark_skills:
        if _is_match(jd_skill, resume_skills_raw, resume_skills_norm):
            matched.append(jd_skill)
        else:
            missing.append(jd_skill)

    recommended: List[str] = []
    if not is_preferred_only:
        for pref_skill in preferred:
            if not _is_match(pref_skill, resume_skills_raw, resume_skills_norm):
                recommended.append(pref_skill)

    total = len(benchmark_skills)
    match_pct = round((len(matched) / total * 100), 1) if total > 0 else 0.0

    return SkillGapResult(
        matched_skills=matched,
        missing_skills=missing,
        recommended_skills=recommended[:10],
        match_percentage=match_pct,
    )
