"""
education.py — Extract education entries from education section blocks.

Handles:
  - Year-prefixed lines: "2019 – 2023   B.Tech, Computer Science"
  - Standard lines: "B.Tech in Computer Science | IIT Bombay | 2019-2023"
  - Multi-line entries: institution on one line, degree on next
"""

import re
from typing import Dict, List, Optional

from resumeai.extractors.date_utils import extract_years, parse_date_range


DEGREE_KEYWORDS = [
    "b.tech", "m.tech", "b.e", "m.e", "btech", "mtech",
    "bachelor", "master", "b.sc", "m.sc", "bsc", "msc",
    "b.com", "m.com", "bcom", "mcom", "b.a", "m.a", "ba", "ma",
    "ph.d", "phd", "doctorate", "mba", "pgdm", "pg diploma",
    "diploma", "associate", "b.s", "m.s", "bs", "ms",
    "b.eng", "m.eng", "llb", "llm", "mbbs", "bds",
    "higher secondary", "secondary", "10th", "12th",
    "ssc", "hsc", "cbse", "icse",
]

GPA_RE = re.compile(
    r"(?:gpa|cgpa|grade|score|percentage|percent|%)[:\s]*"
    r"([\d]+\.?[\d]*)\s*(?:/\s*[\d]+\.?[\d]*)?",
    re.IGNORECASE,
)

HONORS_KEYWORDS = [
    "distinction", "honors", "honours", "cum laude", "summa", "magna",
    "first class", "second class", "merit", "gold medal", "silver medal",
    "valedictorian",
]

YEAR_PREFIX_RE = re.compile(r"^(\d{4})\s*[-–—to]+\s*(\d{4}|present|current)", re.IGNORECASE)


def extract_education(raw_lines: List[str]) -> List[Dict]:
    """
    Parse education section lines into a list of education entry dicts.
    """
    entries: List[Dict] = []
    # Skip the header line (first line is the section header)
    content_lines = _get_content_lines(raw_lines)

    # Group lines into logical entries
    groups = _group_into_entries(content_lines)

    for group in groups:
        entry = _parse_entry(group)
        if entry:
            entries.append(entry)

    return entries


def _get_content_lines(raw_lines: List[str]) -> List[str]:
    """Skip empty lines and the section header (first non-empty line)."""
    lines = [l for l in raw_lines if l.strip()]
    if not lines:
        return []
    # Check if first line is the header itself
    first = lines[0].strip().lower()
    if any(kw in first for kw in ["education", "academic", "qualification", "scholastic"]):
        return lines[1:]
    return lines


def _group_into_entries(lines: List[str]) -> List[List[str]]:
    """
    Group lines into per-institution groups.
    A new group starts when we see a line that looks like a new institution header.
    """
    if not lines:
        return []

    groups: List[List[str]] = []
    current: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            # Empty line may signal end of an entry
            if current:
                groups.append(current)
                current = []
            continue

        # Year-prefix pattern starts a new entry
        if YEAR_PREFIX_RE.match(stripped):
            if current:
                groups.append(current)
            current = [stripped]
            continue

        # Line containing a degree keyword: might be start of new entry
        lower = stripped.lower()
        is_degree_line = any(re.search(rf"\b{re.escape(kw)}\b", lower) for kw in DEGREE_KEYWORDS)
        # Lines that look like GPA/percentage are continuation lines
        is_detail_line = bool(GPA_RE.search(stripped))

        if is_degree_line and not is_detail_line and current:
            # Check if current group already has a degree — if so, new entry
            current_text = " ".join(current).lower()
            if any(re.search(rf"\b{re.escape(kw)}\b", current_text) for kw in DEGREE_KEYWORDS):
                groups.append(current)
                current = [stripped]
                continue

        current.append(stripped)

    if current:
        groups.append(current)

    return groups


def _parse_entry(lines: List[str]) -> Optional[Dict]:
    if not lines:
        return None

    entry: Dict = {
        "institution": None,
        "degree": None,
        "field_of_study": None,
        "start_date": None,
        "end_date": None,
        "gpa": None,
        "honors": [],
        "raw_lines": lines,
    }

    combined = " ".join(lines)

    # Extract dates
    years = extract_years(combined)
    if years:
        if len(years) >= 2:
            entry["start_date"] = years[0]
            entry["end_date"] = years[1]
        else:
            entry["end_date"] = years[0]

    # Check for year-prefixed first line
    m = YEAR_PREFIX_RE.match(lines[0])
    if m:
        entry["start_date"] = m.group(1)
        end = m.group(2)
        entry["end_date"] = None if end.lower() in {"present", "current"} else end
        remainder = lines[0][m.end():].strip().lstrip(",").strip()
        if remainder:
            lines = [remainder] + lines[1:]

    # Extract GPA
    gpa_m = GPA_RE.search(combined)
    if gpa_m:
        entry["gpa"] = gpa_m.group(1)

    # Extract honors
    combined_lower = combined.lower()
    entry["honors"] = [h for h in HONORS_KEYWORDS if h in combined_lower]

    # Extract degree and institution
    entry["degree"], entry["field_of_study"], entry["institution"] = _extract_degree_institution(lines)

    return entry


def _extract_degree_institution(lines: List[str]):
    """Return (degree, field_of_study, institution)."""
    degree = None
    field_of_study = None
    institution = None

    for line in lines:
        lower = line.lower()
        # Look for degree
        for kw in DEGREE_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", lower) and degree is None:
                degree = _clean_degree(line)
                # Try to split field of study
                parts = re.split(r"(?:in|of|,)\s+", line, maxsplit=1, flags=re.IGNORECASE)
                if len(parts) == 2:
                    degree = parts[0].strip()
                    field_of_study = _clean_field(parts[1])
                break

        # Look for institution (contains "university", "college", "institute", "school", "iit", "nit")
        inst_keywords = ["university", "college", "institute", "school", "iit", "nit",
                         "academy", "polytechnic", "faculty"]
        if any(kw in lower for kw in inst_keywords) and institution is None:
            institution = _clean_institution(line)

    return degree, field_of_study, institution


def _clean_degree(text: str) -> str:
    # Remove year artifacts and excess whitespace
    text = re.sub(r"\b\d{4}\b", "", text)
    text = re.sub(r"[-–—]+", "", text)
    return text.strip().strip(",").strip()


def _clean_field(text: str) -> str:
    text = re.sub(r"\b\d{4}\b", "", text)
    text = re.sub(r"[-–—|]+", "", text)
    return text.strip().strip(",").strip()


def _clean_institution(text: str) -> str:
    text = re.sub(r"\b\d{4}\b", "", text)
    text = re.sub(r"[-–—]+", "", text)
    return text.strip().strip(",").strip()
