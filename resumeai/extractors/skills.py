"""
extractors/skills.py — Phase 1.5 Skills Extraction.

Phase 1.5 fixes:
  - Category HEADERS (Programming, Databases, Frameworks, etc.) are NOT emitted
    as skills. Only the child skills within each category are.
  - "Strengths & Interests" and soft-skill lines are filtered out.
  - Skill normalization applied (AWSConsole → AWS, DSA → Data Structures, etc.)
  - flat_list contains only real skills, deduplicated.
"""

import re
from typing import Dict, List, Set

BULLET_RE    = re.compile(r"^[\-\*\•\·\◦\▸\►\–\—]\s+")
CATEGORY_RE  = re.compile(r"^([A-Za-z][A-Za-z\s/&()\-]{1,40}?)\s*[:\-]\s*(.+)")
SEPARATOR_RE = re.compile(r"[,|;•·◦\u2022\u25e6\u00b7]+")

# ── Section-header words to SKIP as section names ─────────────────────────────
# These are the CATEGORY NAMES in the skills section, not actual skills.
# e.g., "Programming: C/C++, Python" → emit C/C++, Python (not "Programming")
SKIP_HEADERS: Set[str] = {
    "programming", "languages", "language", "programming languages",
    "frameworks", "framework", "frameworks & tools", "frameworks and tools",
    "tools", "tool", "libraries", "library",
    "databases", "database", "db",
    "core subjects", "core cs subjects", "cs subjects", "subjects",
    "technical skills", "technical", "skills", "tech skills",
    "competencies", "expertise", "proficiencies",
    "soft skills", "soft skill", "strengths", "interests",
    "strengths & interests", "strengths and interests",
    "areas of interest", "area of interest",
    "cloud", "cloud platforms", "devops", "others", "other",
    "web development", "web", "mobile", "backend", "frontend",
    "section header",
}

# Soft/non-technical terms to filter OUT of flat_list
NOISE_SKILLS: Set[str] = {
    "strengths & interests", "strengths and interests",
    "web development",       # this is a DOMAIN, not a skill
    "fast learning",         # soft skill
    "teamwork",              # soft skill
    "adaptability",          # soft skill
    "problem solving",       # keep this one — it IS a valid technical skill
    "communication",         # soft skill
    "leadership",            # section name, not a skill here
}

# ── Skill normalization ────────────────────────────────────────────────────────
SKILL_NORMALIZE: Dict[str, str] = {
    # Space-squashed variants (from PDF extraction)
    "awsconsole":                "AWS",
    "aws console":               "AWS",
    "softwareengineering":       "Software Engineering",
    "cloudcomputing":            "Cloud Computing",
    "fastlearning":              "Fast Learning",
    "webdevelopment":            "Web Development",
    "problemsolving":            "Problem Solving",
    # Canonical aliases
    "dsa":                       "Data Structures & Algorithms",
    "oop":                       "Object-Oriented Programming",
    "oops":                      "Object-Oriented Programming",
    "dbms":                      "Database Management Systems",
    "rdbms":                     "Database Management Systems",
    "nodejs":                    "Node.js",
    "node.js":                   "Node.js",
    "node":                      "Node.js",
    "reactjs":                   "React.js",
    "react":                     "React.js",
    "expressjs":                 "Express.js",
    "express":                   "Express.js",
    "mongodb":                   "MongoDB",
    "mysql":                     "MySQL",
    "postgresql":                "PostgreSQL",
    "postgres":                  "PostgreSQL",
    "github":                    "GitHub",
    "git":                       "Git",
    "javascript":                "JavaScript",
    "typescript":                "TypeScript",
    "python":                    "Python",
    "c/c++":                     "C/C++",
    "html/css":                  "HTML/CSS",
    "html":                      "HTML",
    "css":                       "CSS",
    "rest api":                  "REST APIs",
    "rest apis":                 "REST APIs",
    "jwt authentication":        "JWT",
    "jwt auth":                  "JWT",
    "llms":                      "LLM",
    "aws management console":    "AWS",
}


def _normalize_skill(raw: str) -> str:
    """Normalize a raw skill string to its canonical form."""
    key = raw.strip().lower()
    return SKILL_NORMALIZE.get(key, raw.strip())


def _is_noise(skill: str) -> bool:
    """Return True if this value should be excluded from the skills output."""
    lower = skill.strip().lower()
    if lower in NOISE_SKILLS:
        return True
    # Filter section-header words that leaked into skills (e.g. "Strengths & Interests")
    if lower in SKIP_HEADERS:
        return True
    # Filter very short non-skills
    if len(lower) < 2:
        return True
    # Filter pure numbers
    if lower.isdigit():
        return True
    return False


def _split_skills(text: str) -> List[str]:
    """Split on commas, pipes, semicolons and clean each part."""
    parts = SEPARATOR_RE.split(text)
    skills = []
    for part in parts:
        s = part.strip().strip("-–—").strip()
        if s and 1 < len(s) < 60:
            skills.append(s)
    return skills


def _get_content_lines(raw_lines: List[str]) -> List[str]:
    lines = [l for l in raw_lines if l.strip()]
    if not lines:
        return []
    # Skip the section header line (e.g., "Technical Skills", "Skills")
    first_lower = lines[0].strip().lower()
    skip_kws = [
        "skill", "technical", "competenc", "expertise", "technology",
        "tool", "language", "framework", "software", "proficien",
    ]
    if any(kw in first_lower for kw in skip_kws) and len(lines[0].strip()) < 50:
        return lines[1:]
    return lines


def extract_skills(raw_lines: List[str]) -> Dict:
    content_lines = _get_content_lines(raw_lines)
    categories: List[Dict] = []
    flat_list: List[str] = []
    seen: Set[str] = set()

    for line in content_lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Remove leading bullet
        if BULLET_RE.match(stripped):
            stripped = BULLET_RE.sub("", stripped).strip()

        # ── Check for "Category: skill1, skill2" format ────────────────
        cat_match = CATEGORY_RE.match(stripped)
        if cat_match:
            cat_name = cat_match.group(1).strip()
            skills_text = cat_match.group(2).strip()

            # Skip if the category name itself is a noise/header word
            if cat_name.lower() in SKIP_HEADERS:
                # Still extract the child skills into flat_list
                raw_skills = _split_skills(skills_text)
                for s in raw_skills:
                    norm = _normalize_skill(s)
                    key = norm.lower()
                    if key and key not in seen and not _is_noise(norm):
                        flat_list.append(norm)
                        seen.add(key)
                continue

            # Valid category — extract its child skills
            raw_skills = _split_skills(skills_text)
            clean_skills = []
            for s in raw_skills:
                norm = _normalize_skill(s)
                key = norm.lower()
                if key and key not in seen and not _is_noise(norm):
                    clean_skills.append(norm)
                    flat_list.append(norm)
                    seen.add(key)

            if clean_skills:
                categories.append({
                    "category": cat_name,
                    "skills": clean_skills,
                })
            continue

        # ── Plain skill line (no category prefix) ─────────────────────
        # e.g., "Strengths & Interests" alone on a line → skip entirely
        if stripped.lower() in SKIP_HEADERS or stripped.lower() in NOISE_SKILLS:
            continue

        raw_skills = _split_skills(stripped)
        for s in raw_skills:
            norm = _normalize_skill(s)
            key = norm.lower()
            if key and key not in seen and not _is_noise(norm):
                flat_list.append(norm)
                seen.add(key)

    return {
        "categories": categories,
        "flat_list":  flat_list,
        "raw_lines":  raw_lines,
    }
