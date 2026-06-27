"""
matching/jd_parser.py — Job Description Parser for Phase 2 (v2) and Phase 4.

Uses Central Skill Intelligence Engine for semantic parsing and domain classification.
"""
from __future__ import annotations

import re
from typing import List, Dict, Set, Any
from .schemas import ParsedJD
from resumeai.core.skill_intelligence import SkillIntelligenceEngine

# ── Public helpers wrapping the Intelligence Engine ───────────────────────────

def normalize_skill(raw: str) -> str:
    """Return canonical form of a skill string."""
    return SkillIntelligenceEngine().normalize_skill(raw)

def extract_skills_from_text(text: str) -> List[str]:
    """
    Extract canonical skills from text using phrase-first matching via Intelligence Engine.
    """
    return SkillIntelligenceEngine().extract_skills_from_text(text)


# ── Section header patterns ───────────────────────────────────────────────────
REQUIRED_HEADERS = re.compile(
    r"^(required skills?|requirements|required|must have|must-have|mandatory|qualifications?|"
    r"minimum qualifications?|basic qualifications?|what you.ll need|what we need):?\s*$",
    re.IGNORECASE,
)
PREFERRED_HEADERS = re.compile(
    r"^(preferred skills?|preferred|nice to have|nice-to-have|bonus|plus|desired|"
    r"additional qualifications?|preferred qualifications?|good to have|advantages?):?\s*$",
    re.IGNORECASE,
)
RESPONSIBILITIES_HEADERS = re.compile(
    r"^(responsibilities|what you.ll do|role|duties|your role|"
    r"day-to-day|you will|what you will do|key responsibilities):?\s*$",
    re.IGNORECASE,
)
EXPERIENCE_PATTERNS = [
    re.compile(r"(\d+)\+?\s*years?\s+(?:of\s+)?experience", re.IGNORECASE),
    re.compile(r"(\d+)[\s-]+(\d+)\s*years?", re.IGNORECASE),
    re.compile(r"(entry[\s-]level|junior|mid[\s-]level|senior|lead|staff|principal)", re.IGNORECASE),
    re.compile(r"(internship|intern|co-op|fresher|fresh graduate)", re.IGNORECASE),
]

EDUCATION_PATTERNS = [
    re.compile(r"(bachelor|b\.s\.|bs|master|m\.s\.|ms|phd|ph\.d|degree in computer science)", re.IGNORECASE),
    re.compile(r"(degree|diploma|certification) in", re.IGNORECASE),
]


def _split_sections(text: str) -> Dict[str, str]:
    """Split JD into named sections without mis-tagging bullet content as headers."""
    lines = text.splitlines()
    sections: Dict[str, List[str]] = {
        "required": [], "preferred": [], "responsibilities": [], "general": [],
    }
    current = "general"

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Only allow section switch on SHORT lines that are NOT bullet content
        is_bullet = bool(re.match(r"^[\-\•\*\◦\▸\▪\·\–\—]|^\d+[\.\)]", stripped))
        is_candidate = len(stripped) < 80 and not is_bullet

        if is_candidate and REQUIRED_HEADERS.match(stripped):
            current = "required"
            continue
        elif is_candidate and PREFERRED_HEADERS.match(stripped):
            current = "preferred"
            continue
        elif is_candidate and RESPONSIBILITIES_HEADERS.match(stripped):
            current = "responsibilities"
            continue

        sections[current].append(line)

    return {k: "\n".join(v) for k, v in sections.items()}


def _extract_bullets(text: str) -> List[str]:
    """Extract bullet-point lines from text."""
    bullets = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^[\-\•\*\◦\▸\▪\·\–\—]|^\d+[\.\)]", stripped):
            content = re.sub(r"^[\-\•\*\◦\▸\▪\·\–\—\d\.\)]+\s*", "", stripped).strip()
            if len(content) > 5:
                bullets.append(content)
    return bullets


def _extract_title(text: str) -> str:
    """Extract job title from first few non-bullet lines of JD."""
    lines = [l.strip() for l in text.splitlines()[:10] if l.strip()]
    title_kws = [
        "engineer", "developer", "analyst", "scientist", "manager",
        "architect", "lead", "intern", "associate", "consultant",
        "specialist", "designer", "devops", "sre", "backend",
        "frontend", "fullstack", "full-stack", "data", "software",
    ]
    for line in lines:
        if len(line) < 90 and not re.match(r"^[\-\•\*\d]", line):
            if any(kw in line.lower() for kw in title_kws):
                return line
    return lines[0] if lines else "Software Engineer"


def _extract_experience_reqs(text: str) -> List[str]:
    """Find experience requirement statements."""
    reqs: List[str] = []
    seen: Set[str] = set()
    for line in text.splitlines():
        for pat in EXPERIENCE_PATTERNS:
            if pat.search(line):
                clean = line.strip()
                if clean and clean not in seen and len(clean) > 5:
                    reqs.append(clean)
                    seen.add(clean)
                break
    return reqs[:10]


def _extract_education_reqs(text: str) -> List[str]:
    """Find education requirement statements."""
    reqs: List[str] = []
    seen: Set[str] = set()
    for line in text.splitlines():
        for pat in EDUCATION_PATTERNS:
            if pat.search(line):
                clean = line.strip()
                if clean and clean not in seen and len(clean) > 5:
                    reqs.append(clean)
                    seen.add(clean)
                break
    return reqs[:5]


# ── Public API ────────────────────────────────────────────────────────────────

def parse_job_description(text: str) -> ParsedJD:
    """
    Parse a raw job description string into a structured ParsedJD object.

    Skills are extracted using the curated CANONICAL_SKILLS dictionary.
    Generic words (engineer, intern, software, data, apis, problem, solving)
    are NEVER extracted as standalone skills.

    Args:
        text: Raw JD text (plain text, may contain bullets and sections)

    Returns:
        ParsedJD with title, required_skills, preferred_skills,
        experience_requirements, responsibilities, keywords
    """
    if not text or not text.strip():
        return ParsedJD()

    text = text.strip()
    sections = _split_sections(text)

    title = _extract_title(text)

    # Required skills: scan required section + general section (full text scan)
    required_text = sections.get("required", "") + "\n" + sections.get("general", "")
    all_required = extract_skills_from_text(required_text)
    
    # Fallback: if no required skills found, the JD might not have clear section headers
    # so we extract from the entire text
    if not all_required:
        all_required = extract_skills_from_text(text)

    # Preferred skills: scan preferred section only
    pref_skills = extract_skills_from_text(sections.get("preferred", ""))

    # Remove preferred from required
    pref_set = set(pref_skills)
    required_skills = [s for s in all_required if s not in pref_set]

    # Responsibilities
    responsibilities = _extract_bullets(sections.get("responsibilities", ""))
    if not responsibilities:
        responsibilities = _extract_bullets(sections.get("general", ""))[:8]

    # Experience requirements
    experience_requirements = _extract_experience_reqs(text)

    # Education requirements
    education_requirements = _extract_education_reqs(text)

    # Keywords: union of required + preferred skills (clean, canonical)
    keywords = sorted(set(required_skills) | set(pref_skills))

    parsed = ParsedJD(
        title=title,
        required_skills=required_skills,
        preferred_skills=pref_skills,
        experience_requirements=experience_requirements,
        education_requirements=education_requirements,
        responsibilities=responsibilities,
        keywords=keywords,
    )
    
    # Classify domain
    parsed.domain_classification = SkillIntelligenceEngine().classify_jd_domain(parsed)
    return parsed
