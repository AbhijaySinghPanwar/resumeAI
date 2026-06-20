"""
experience.py — Extract work experience entries from experience section blocks.

Handles:
  - Company | Role | Dates on one line
  - Company on one line, Role + Dates on next
  - Bullet points as responsibilities
  - Internship detection
"""

import re
from typing import Dict, List, Optional, Tuple

from resumeai.extractors.date_utils import extract_years, parse_date_range, is_date_line, PRESENT_TOKENS

BULLET_RE = re.compile(r"^[\-\*\•\·\◦\▸\►\–\—]\s+")
PIPE_SEP_RE = re.compile(r"\s*[|\u2013\u2014]\s*")

ROLE_KEYWORDS = [
    "engineer", "developer", "analyst", "manager", "intern", "consultant",
    "designer", "architect", "lead", "head", "officer", "associate",
    "specialist", "coordinator", "executive", "director", "scientist",
    "researcher", "administrator", "assistant", "trainee", "fellow",
]

COMPANY_SUFFIXES = [
    "ltd", "limited", "inc", "corp", "corporation", "llc", "llp",
    "pvt", "private", "technologies", "solutions", "systems", "services",
    "consulting", "group", "labs", "studio", "ventures", "holdings",
]


def extract_experience(raw_lines: List[str]) -> List[Dict]:
    content_lines = _get_content_lines(raw_lines)
    groups = _group_into_entries(content_lines)
    entries = []
    for group in groups:
        entry = _parse_entry(group)
        if entry:
            entries.append(entry)
    return entries


def _get_content_lines(raw_lines: List[str]) -> List[str]:
    lines = [l for l in raw_lines if l.strip()]
    if not lines:
        return []
    first_lower = lines[0].strip().lower()
    skip_keywords = [
        "experience", "employment", "work history", "career", "internship",
        "positions held", "professional background",
    ]
    if any(kw in first_lower for kw in skip_keywords) and len(lines[0].strip()) < 50:
        return lines[1:]
    return lines


def _is_entry_header(line: str) -> bool:
    """Heuristic: does this line look like the start of a new job entry?"""
    stripped = line.strip()
    if not stripped or BULLET_RE.match(stripped):
        return False

    lower = stripped.lower()

    # Contains pipe separator → likely "Company | Role | Date"
    if "|" in stripped or "–" in stripped:
        parts = PIPE_SEP_RE.split(stripped)
        if len(parts) >= 2:
            return True

    # Contains a role keyword and a year
    has_role = any(kw in lower for kw in ROLE_KEYWORDS)
    has_year = bool(re.search(r"\b(19|20)\d{2}\b", stripped))
    if has_role and has_year:
        return True

    # Contains a company suffix keyword
    if any(f" {sfx}" in lower or lower.endswith(sfx) for sfx in COMPANY_SUFFIXES):
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
            continue

        if _is_entry_header(stripped) and current:
            # Check that current group has some content (not just a header with no bullets)
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
        "company": None,
        "title": None,
        "location": None,
        "start_date": None,
        "end_date": None,
        "is_current": False,
        "bullets": [],
        "raw_lines": lines,
    }

    bullets = []
    header_lines = []

    for line in lines:
        if BULLET_RE.match(line.strip()):
            bullets.append(BULLET_RE.sub("", line.strip()).strip())
        else:
            header_lines.append(line.strip())

    entry["bullets"] = bullets

    # Parse header lines for company, role, dates, location
    header_text = " | ".join(header_lines)
    company, title, start, end, is_current, location = _parse_header(header_lines)

    entry["company"] = company
    entry["title"] = title
    entry["start_date"] = start
    entry["end_date"] = end
    entry["is_current"] = is_current
    entry["location"] = location

    return entry


def _parse_header(header_lines: List[str]) -> Tuple:
    company = None
    title = None
    start_date = None
    end_date = None
    is_current = False
    location = None

    for line in header_lines:
        # Try pipe/dash separation first
        parts = [p.strip() for p in PIPE_SEP_RE.split(line) if p.strip()]
        
        # Merge fragmented date ranges
        merged_parts = []
        for p in parts:
            if merged_parts and is_date_line(merged_parts[-1]) and is_date_line(p):
                merged_parts[-1] = merged_parts[-1] + " - " + p
            else:
                merged_parts.append(p)

        if len(merged_parts) >= 2:
            # Assign parts by content type
            for part in merged_parts:
                part_lower = part.lower()

                if is_date_line(part):
                    start_date, end_date, is_current = parse_date_range(part)
                elif any(kw in part_lower for kw in ROLE_KEYWORDS) and title is None:
                    title = part
                elif _looks_like_location(part) and location is None:
                    location = part
                elif company is None:
                    company = part
        else:
            # Single line: try to figure out what it is
            if is_date_line(line):
                start_date, end_date, is_current = parse_date_range(line)
            elif any(kw in line.lower() for kw in ROLE_KEYWORDS) and title is None:
                title = line.strip()
            elif company is None and not is_date_line(line):
                company = line.strip()

    return company, title, start_date, end_date, is_current, location


def _looks_like_location(text: str) -> bool:
    """Check if text looks like a location string."""
    if re.search(r"\b(remote|hybrid|on.?site|wfh)\b", text, re.IGNORECASE):
        return True
    if re.search(r"[A-Za-z]+,\s*[A-Za-z]+", text) and len(text) < 40:
        return True
    return False
