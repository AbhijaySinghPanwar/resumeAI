"""
skills.py — Extract skills from the skills section block.

Handles:
  - Categorized: "Languages: Python, Java, C++"
  - Flat comma/pipe-separated lists
  - Multi-line skill groups
"""

import re
from typing import Dict, List, Optional, Tuple

BULLET_RE = re.compile(r"^[\-\*\•\·\◦\▸\►\–\—]\s+")
CATEGORY_RE = re.compile(r"^([A-Za-z][A-Za-z\s/&()\-]{1,40}?)\s*[:\-]\s*(.+)")
SEPARATOR_RE = re.compile(r"[,|;•·◦\u2022\u25e6\u00b7]+")


def extract_skills(raw_lines: List[str]) -> Dict:
    content_lines = _get_content_lines(raw_lines)
    categories = []
    flat_list = []
    seen = set()

    for line in content_lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Remove leading bullet
        if BULLET_RE.match(stripped):
            stripped = BULLET_RE.sub("", stripped).strip()

        # Try category: value format
        cat_match = CATEGORY_RE.match(stripped)
        if cat_match:
            cat_name = cat_match.group(1).strip()
            skills_text = cat_match.group(2).strip()
            skills = _split_skills(skills_text)
            if skills:
                categories.append({
                    "category": cat_name,
                    "skills": skills,
                })
                for s in skills:
                    key = s.lower().strip()
                    if key not in seen:
                        flat_list.append(s)
                        seen.add(key)
                continue

        # Plain skills list
        skills = _split_skills(stripped)
        for s in skills:
            key = s.lower().strip()
            if key and key not in seen:
                flat_list.append(s)
                seen.add(key)

    return {
        "categories": categories,
        "flat_list": flat_list,
        "raw_lines": raw_lines,
    }


def _get_content_lines(raw_lines: List[str]) -> List[str]:
    lines = [l for l in raw_lines if l.strip()]
    if not lines:
        return []
    first_lower = lines[0].strip().lower()
    skip_keywords = [
        "skill", "technical", "competenc", "expertise", "technology",
        "tool", "language", "framework", "software", "proficien",
    ]
    if any(kw in first_lower for kw in skip_keywords) and len(lines[0].strip()) < 50:
        return lines[1:]
    return lines


def _split_skills(text: str) -> List[str]:
    """Split a skill string on commas, pipes, semicolons."""
    parts = SEPARATOR_RE.split(text)
    skills = []
    for part in parts:
        s = part.strip().strip("-–—").strip()
        if s and len(s) < 60:
            skills.append(s)
    return skills
