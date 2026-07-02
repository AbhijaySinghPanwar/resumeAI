"""
matching/jd_parser.py — Job Description Parser (Phase 4.2 + hotfix + ontology wiring).

Fixes in this version:
  - Section headers now match "Required Skills", "Preferred Skills", "Nice to Have"
    in addition to bare "required" / "preferred".
  - Plain-text skill lines (no bullet prefix, e.g. "Python\nFastAPI\n...") are
    now extracted via _extract_plain_lines(), not just bulleted lines.
  - OR alternatives ("Django or FastAPI") counted as one requirement group.
  - Inline preferred signals ("preferred", "nice to have") routed to preferred_skills.
  - Domain classification uses token-based matching.
  - Skill vocabulary (CANONICAL_SKILLS / aliases) now lives in
    resumeai/ontology/skill_ontology.json, the single source of truth shared
    with the resume-side extractor (extractors/projects.py) and the
    relationship-graph matcher (gap_analyzer.py). This module no longer
    defines its own skill dictionary -- see resumeai/ontology/registry.py.
"""
from __future__ import annotations

import re
from typing import List, Dict, Set, Optional, Tuple
from .schemas import ParsedJD
from resumeai.ontology.registry import get_registry

_registry = get_registry()

# Kept for backward compatibility with any external code importing this name
# directly (e.g. gap_analyzer.py's historical import). Prefer
# resumeai.ontology.registry.get_registry().alias_to_canonical_map() in new code.
_ALIAS_TO_CANONICAL: Dict[str, str] = _registry.alias_to_canonical_map()


def normalize_skill(raw: str) -> str:
    return _registry.normalize_skill(raw)


def extract_skills_from_text(text: str) -> List[str]:
    """Extract canonical skills from freeform text using phrase-first matching.
    Delegates to the shared ontology registry so JD-side and resume-side
    extraction always use the identical vocabulary."""
    return _registry.extract_skills_from_text(text)


# ── Domain classification ─────────────────────────────────────────────────────
DOMAIN_TOKENS: Dict[str, List[str]] = {
    "Backend": ["backend", "back-end", "back end", "server-side"],
    "Frontend": ["frontend", "front-end", "front end", "ui developer", "ux developer"],
    "Full Stack": ["fullstack", "full-stack", "full stack"],
    "Cloud": ["cloud", "platform engineer", "infrastructure", "sre", "site reliability"],
    "DevOps": ["devops", "devsecops"],
    "Machine Learning": ["machine learning", "ml engineer", "data science", "ai engineer",
                         "nlp", "computer vision", "deep learning"],
    "AI Engineering": ["ai engineer", "llm", "genai", "generative ai"],
    "Cyber Security": ["security engineer", "cybersecurity", "cyber security", "infosec", "appsec"],
    "Data Engineering": ["data engineer", "data pipeline", "etl", "analytics engineer"],
    "Embedded": ["embedded", "firmware", "rtos", "microcontroller"],
    "Game Development": ["game developer", "unity", "unreal"],
}


def classify_domain(title: str) -> Optional[str]:
    title_lower = title.lower()
    best_domain = None
    best_score = 0
    for domain, tokens in DOMAIN_TOKENS.items():
        for token in tokens:
            if token in title_lower:
                score = len(token)
                if score > best_score:
                    best_score = score
                    best_domain = domain
    return best_domain


# ── Section header patterns ───────────────────────────────────────────────────
# Now includes "Required Skills", "Preferred Skills", "Nice to Have Skills" etc.
REQUIRED_HEADERS = re.compile(
    r"^(required(?:\s+skills?)?|requirements?|must[\s\-]have(?:\s+skills?)?|mandatory(?:\s+skills?)?|"
    r"qualifications?|minimum\s+qualifications?|basic\s+qualifications?|"
    r"what\s+you.?ll?\s+need|what\s+we\s+(?:need|require)|technical\s+requirements?|"
    r"key\s+requirements?|core\s+skills?|technical\s+skills?\s+required):?\s*$",
    re.IGNORECASE,
)
PREFERRED_HEADERS = re.compile(
    r"^(preferred(?:\s+skills?)?|nice[\s\-]to[\s\-]have(?:\s+skills?)?|bonus(?:\s+skills?)?|"
    r"plus(?:\s+skills?)?|desired(?:\s+skills?)?|optional(?:\s+skills?)?|"
    r"additional\s+qualifications?|good[\s\-]to[\s\-]have(?:\s+skills?)?|"
    r"advantages?|preferred\s+qualifications?|would[\s\-]be\s+(?:a\s+)?plus):?\s*$",
    re.IGNORECASE,
)
RESPONSIBILITIES_HEADERS = re.compile(
    r"^(responsibilities?|what\s+you.?ll?\s+do|role|duties|your\s+role|"
    r"day[\s\-]to[\s\-]day|you\s+will|what\s+you\s+will\s+do|key\s+responsibilities?|"
    r"job\s+description|about\s+the\s+role|the\s+role|overview):?\s*$",
    re.IGNORECASE,
)
EXPERIENCE_PATTERNS = [
    re.compile(r"(\d+)\+?\s*years?\s+(?:of\s+)?experience", re.IGNORECASE),
    re.compile(r"(\d+)[\s-]+(\d+)\s*years?", re.IGNORECASE),
    re.compile(r"(entry[\s-]level|junior|mid[\s-]level|senior|lead|staff|principal)", re.IGNORECASE),
    re.compile(r"(internship|intern|co-op|fresher|fresh\s+graduate)", re.IGNORECASE),
]
EDUCATION_PATTERNS = [
    re.compile(r"(bachelor|b\.s\.|bs|master|m\.s\.|ms|phd|ph\.d|degree\s+in)", re.IGNORECASE),
    re.compile(r"(degree|diploma|certification)\s+in", re.IGNORECASE),
]
PREFERRED_INLINE_RE = re.compile(
    r"\b(preferred|nice\s+to\s+have|nice-to-have|desired|optional|plus|bonus|advantage)\b",
    re.IGNORECASE,
)
OR_SPLIT_RE = re.compile(r"\s+(?:or|OR|/)\s+")

# Lines to skip when scanning for plain skills
_SKIP_LINE_RE = re.compile(
    r"^(job\s+title|location|about\s+us|company|department|salary|compensation|"
    r"benefits?|how\s+to\s+apply|equal\s+opportunity|we\s+offer|what\s+we\s+offer)",
    re.IGNORECASE,
)


def _split_sections(text: str) -> Dict[str, List[str]]:
    """
    Split JD text into named sections.
    Returns a dict of section_name → list of content lines.
    """
    lines = text.splitlines()
    sections: Dict[str, List[str]] = {
        "required": [], "preferred": [], "responsibilities": [], "general": [],
    }
    current = "general"

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        is_bullet = bool(re.match(r"^[\-\•\*\◦\▸\▪\·\–\—]|^\d+[\.\)]", stripped))
        # Section headers are typically short non-bullet lines
        is_candidate_header = len(stripped) < 80 and not is_bullet

        if is_candidate_header and REQUIRED_HEADERS.match(stripped):
            current = "required"
            continue
        elif is_candidate_header and PREFERRED_HEADERS.match(stripped):
            current = "preferred"
            continue
        elif is_candidate_header and RESPONSIBILITIES_HEADERS.match(stripped):
            current = "responsibilities"
            continue

        sections[current].append(line)

    return sections


def _extract_bullets(lines: List[str]) -> List[str]:
    """Extract bullet-prefixed lines from a list of lines."""
    bullets = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^[\-\•\*\◦\▸\▪\·\–\—]|^\d+[\.\)]", stripped):
            content = re.sub(r"^[\-\•\*\◦\▸\▪\·\–\—\d\.\)]+\s*", "", stripped).strip()
            if len(content) > 3:
                bullets.append(content)
    return bullets


def _extract_plain_skill_lines(lines: List[str]) -> List[str]:
    """
    Extract plain-text lines that look like skill names (no bullet prefix).
    These appear in JDs that list skills one-per-line without bullets, e.g.:
        Python
        FastAPI
        REST APIs
    Filters out section headers, metadata lines, and long sentences.
    """
    plain_skills = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip bullet lines (handled by _extract_bullets)
        if re.match(r"^[\-\•\*\◦\▸\▪\·\–\—]|^\d+[\.\)]", stripped):
            continue
        # Skip known metadata lines
        if _SKIP_LINE_RE.match(stripped):
            continue
        # Skip very long lines (sentences, not skill names)
        if len(stripped) > 60:
            continue
        # Skip lines that look like section headers (already consumed)
        if (REQUIRED_HEADERS.match(stripped) or PREFERRED_HEADERS.match(stripped)
                or RESPONSIBILITIES_HEADERS.match(stripped)):
            continue
        # Accept: short lines that resolve to at least one canonical skill
        skills = extract_skills_from_text(stripped)
        if skills:
            plain_skills.append(stripped)
    return plain_skills


def _extract_skills_from_section(lines: List[str], include_preferred_inline: bool = True):
    """
    Extract (required_skills, preferred_skills) from a list of section lines.
    Handles both bulleted and plain-text skill lists.
    Also handles OR alternatives and inline preferred signals.
    """
    required: List[str] = []
    preferred: List[str] = []

    all_content_lines = _extract_bullets(lines) + _extract_plain_skill_lines(lines)

    for content in all_content_lines:
        is_preferred = include_preferred_inline and bool(PREFERRED_INLINE_RE.search(content))

        # Check for OR alternatives
        or_parts = OR_SPLIT_RE.split(content)
        if len(or_parts) > 1:
            group_skills = []
            for part in or_parts:
                group_skills.extend(extract_skills_from_text(part))
            group_skills = list(dict.fromkeys(group_skills))
            if group_skills:
                if is_preferred:
                    preferred.extend(group_skills)
                else:
                    required.extend(group_skills)
        else:
            skills = extract_skills_from_text(content)
            if is_preferred:
                preferred.extend(skills)
            else:
                required.extend(skills)

    return required, preferred


def _extract_title(text: str) -> str:
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
                # Strip "Job Title:" prefix if present
                cleaned = re.sub(r"^job\s+title\s*:\s*", "", line, flags=re.IGNORECASE).strip()
                return cleaned
    return lines[0] if lines else "Software Engineer"


def _extract_experience_reqs(text: str) -> List[str]:
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
    Parse a raw job description into a structured ParsedJD object.

    Supports both bulleted and plain-text skill lists:
      Bulleted:      • Python\n• FastAPI
      Plain text:    Python\nFastAPI
      Mixed:         • Python\nFastAPI\n• Docker
    """
    if not text or not text.strip():
        return ParsedJD()

    text = text.strip()
    sections = _split_sections(text)

    title = _extract_title(text)

    # --- Required section ---
    req_from_req, pref_from_req = _extract_skills_from_section(sections["required"])
    req_from_gen, pref_from_gen = _extract_skills_from_section(sections["general"])

    all_required_raw = req_from_req + req_from_gen

    # --- Preferred section ---
    pref_lines = sections["preferred"]
    pref_bullets = _extract_bullets(pref_lines)
    pref_plain   = _extract_plain_skill_lines(pref_lines)
    pref_from_pref: List[str] = []
    for content in pref_bullets + pref_plain:
        pref_from_pref.extend(extract_skills_from_text(content))

    all_preferred_raw = list(dict.fromkeys(
        pref_from_req + pref_from_gen + pref_from_pref
    ))
    pref_set = set(all_preferred_raw)

    # Also do a full-text extract as safety net to catch anything missed
    full_text_skills = extract_skills_from_text(text)

    # Merge: section-aware takes priority; add anything from full-text not already captured
    already_captured = set(all_required_raw) | pref_set
    extra_from_full = [s for s in full_text_skills if s not in already_captured]

    # Put extras in required (conservative: if we don't know where it belongs, it's required)
    all_required_combined = list(dict.fromkeys(all_required_raw + extra_from_full))
    required_skills = [s for s in all_required_combined if s not in pref_set]

    # --- Responsibilities ---
    responsibilities = _extract_bullets(sections["responsibilities"])
    if not responsibilities:
        responsibilities = _extract_bullets(sections["general"])[:10]

    experience_requirements = _extract_experience_reqs(text)
    education_requirements  = _extract_education_reqs(text)
    keywords = sorted(set(required_skills) | pref_set)

    return ParsedJD(
        title=title,
        required_skills=required_skills,
        preferred_skills=all_preferred_raw,
        experience_requirements=experience_requirements,
        education_requirements=education_requirements,
        responsibilities=responsibilities,
        keywords=keywords,
    )
