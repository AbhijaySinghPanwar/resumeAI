"""
leadership.py — Extract leadership / extracurricular entries.

Handles combined headers like "Positions of Responsibility / Extracurriculars".
Treats entries the same as experience: role + org + dates + bullets.
"""

import re
from typing import Dict, List, Optional, Tuple

from resumeai.extractors.date_utils import parse_date_range, is_date_line

BULLET_RE = re.compile(r"^[\-\*\•\·\◦\▸\►\–\—]\s+")
PIPE_SEP_RE = re.compile(r"\s*[|\u2013\u2014]\s*")

ROLE_KEYWORDS = [
    "president", "vice president", "vp", "secretary", "treasurer",
    "coordinator", "organizer", "head", "lead", "chair", "chairperson",
    "member", "volunteer", "mentor", "representative", "convener",
    "joint secretary", "general secretary", "captain", "manager",
    "director", "officer", "ambassador", "delegate", "executive",
]

ORG_KEYWORDS = [
    "club", "society", "association", "committee", "team", "council",
    "chapter", "group", "nss", "ncc", "rotaract", "enactus",
    "cell", "forum", "federation", "union",
]


def extract_leadership(raw_lines: List[str]) -> List[Dict]:
    content_lines = _get_content_lines(raw_lines)
    groups = _group_into_entries(content_lines)
    return [e for e in (_parse_entry(g) for g in groups) if e]


def _get_content_lines(raw_lines: List[str]) -> List[str]:
    lines = [l for l in raw_lines if l.strip()]
    if not lines:
        return []
    first_lower = lines[0].strip().lower()
    skip_keywords = [
        "leadership", "position", "responsibility", "extracurricular",
        "activities", "involvement", "volunteering", "volunteer", "community",
    ]
    if any(kw in first_lower for kw in skip_keywords) and len(lines[0].strip()) < 60:
        return lines[1:]
    return lines


def _is_entry_header(line: str) -> bool:
    stripped = line.strip()
    if not stripped or BULLET_RE.match(stripped):
        return False
    lower = stripped.lower()

    # Pipe separator → structured entry header
    if "|" in stripped:
        return True

    has_role = any(kw in lower for kw in ROLE_KEYWORDS)
    has_org = any(kw in lower for kw in ORG_KEYWORDS)
    has_year = bool(re.search(r"\b(19|20)\d{2}\b", stripped))

    if has_role or has_org:
        return True
    if has_year and not is_date_line(stripped):
        return True

    return False


def _group_into_entries(lines: List[str]) -> List[List[str]]:
    if not lines:
        return []
    groups: List[List[str]] = []
    current: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                groups.append(current)
                current = []
            continue

        if _is_entry_header(stripped) and current:
            groups.append(current)
            current = [stripped]
        else:
            current.append(stripped)

    if current:
        groups.append(current)
    return groups


def _parse_entry(lines: List[str]) -> Optional[Dict]:
    if not lines:
        return None

    entry: Dict = {
        "organization": None,
        "role": None,
        "start_date": None,
        "end_date": None,
        "bullets": [],
        "raw_lines": lines,
    }

    bullets = []
    header_lines = []

    for line in lines:
        stripped = line.strip()
        if BULLET_RE.match(stripped):
            bullets.append(BULLET_RE.sub("", stripped).strip())
        else:
            header_lines.append(stripped)

    entry["bullets"] = bullets

    role, org, start, end = _parse_header(header_lines)
    entry["role"] = role
    entry["organization"] = org
    entry["start_date"] = start
    entry["end_date"] = end

    return entry


def _parse_header(header_lines: List[str]) -> Tuple:
    role = None
    org = None
    start_date = None
    end_date = None

    for line in header_lines:
        parts = [p.strip() for p in PIPE_SEP_RE.split(line) if p.strip()]
        
        merged_parts = []
        for p in parts:
            if merged_parts and is_date_line(merged_parts[-1]) and is_date_line(p):
                merged_parts[-1] = merged_parts[-1] + " - " + p
            else:
                merged_parts.append(p)

        if len(merged_parts) >= 2:
            for part in merged_parts:
                part_lower = part.lower()
                if is_date_line(part):
                    start_date, end_date, _ = parse_date_range(part)
                elif any(kw in part_lower for kw in ROLE_KEYWORDS) and role is None:
                    role = part
                elif any(kw in part_lower for kw in ORG_KEYWORDS) and org is None:
                    org = part
                elif org is None and role is not None:
                    org = part
                elif role is None:
                    role = part
        else:
            stripped = line.strip()
            if is_date_line(stripped):
                start_date, end_date, _ = parse_date_range(stripped)
            elif any(kw in stripped.lower() for kw in ROLE_KEYWORDS) and role is None:
                role = stripped
            elif any(kw in stripped.lower() for kw in ORG_KEYWORDS) and org is None:
                org = stripped
            elif role is None:
                role = stripped
            elif org is None:
                org = stripped

    return role, org, start_date, end_date
