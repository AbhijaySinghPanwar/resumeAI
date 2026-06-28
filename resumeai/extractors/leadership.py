"""
extractors/leadership.py — Phase 1.6 Leadership / Awards / Scholarships Extraction.

Phase 1.6 improvements:
  - Continuation lines are NEVER treated as new entries.
  - Entity classification splits entries into semantic subtypes:
      positions_of_responsibility, volunteer, awards, scholarships, leadership
  - Each entry is one clean object: {role, organization, start_date, end_date,
    subtype, bullets, raw_lines}
  - Backward-compatible: output shape unchanged, subtype is a new optional field.
"""

import re
from typing import Dict, List, Optional, Tuple

from resumeai.extractors.date_utils import parse_date_range, is_date_line
from resumeai.extractors._continuation import is_continuation

BULLET_RE   = re.compile(r"^[\-\*\•\·\◦\▸\►\–\—]\s+")
PIPE_SEP_RE = re.compile(r"\s*[|\u2013\u2014]\s*")
DATE_RE     = re.compile(r"\b(19|20)\d{2}\b")

# ── Entity subtype classification keywords ────────────────────────────────────
AWARD_KEYWORDS = [
    "award", "winner", "won", "prize", "medal", "topper", "rank",
    "first place", "second place", "third place", "merit", "honor",
    "honours", "distinction", "recognition", "achievement",
    "best", "outstanding", "excellence", "accolade", "trophy",
]
SCHOLARSHIP_KEYWORDS = [
    "scholarship", "fellow", "fellowship", "grant", "stipend",
    "funded", "sponsored", "bursary", "exchange scholar",
]
VOLUNTEER_KEYWORDS = [
    "volunteer", "nss", "ncc", "community service", "social work",
    "charity", "nonprofit", "non-profit", "humanitarian",
    "rotaract", "rotary", "enactus",
]

# Past-tense description starters — these describe an entry, not start a new one
DESCRIPTION_STARTERS = re.compile(
    r"^(awarded|won|received|selected|chosen|recognized|appointed|"
    r"represented|contributed|ranked|achieved|earned|secured)\b",
    re.IGNORECASE,
)
ROLE_KEYWORDS = [
    "president", "vice president", "vp", "secretary", "treasurer",
    "coordinator", "organizer", "head", "lead", "chair", "chairperson",
    "member", "mentor", "representative", "convener", "joint secretary",
    "general secretary", "captain", "manager", "director", "officer",
    "ambassador", "delegate", "executive",
    "core", "junior core", "senior core",  # e.g. "Junior Core, PR Domain"
    "domain head", "technical head", "pr",
]
ORG_KEYWORDS = [
    "club", "society", "association", "committee", "team", "council",
    "chapter", "group", "nss", "ncc", "rotaract", "enactus",
    "cell", "forum", "federation", "union", "iit", "nit", "vit",
    "department", "college", "university", "institute", "foundation",
]


def _classify_subtype(lines: List[str]) -> str:
    """Classify an entry into a semantic subtype based on its content."""
    combined = " ".join(lines).lower()
    if any(kw in combined for kw in SCHOLARSHIP_KEYWORDS):
        return "scholarship"
    if any(kw in combined for kw in AWARD_KEYWORDS):
        return "award"
    if any(kw in combined for kw in VOLUNTEER_KEYWORDS):
        return "volunteer"
    if any(kw in combined for kw in ROLE_KEYWORDS):
        return "position_of_responsibility"
    return "leadership"


def _get_content_lines(raw_lines: List[str]) -> List[str]:
    lines = [l for l in raw_lines if l.strip()]
    if not lines:
        return []
    first_lower = lines[0].strip().lower()
    skip_kw = [
        "leadership", "position", "responsibility", "extracurricular",
        "activities", "involvement", "volunteering", "volunteer",
        "community", "awards", "honors", "scholarships", "achievements",
        "recognitions", "distinctions",
    ]
    if any(kw in first_lower for kw in skip_kw) and len(lines[0].strip()) < 60:
        return lines[1:]
    return lines


def _is_entry_header(line: str, prev_line: str = "") -> bool:
    """
    True if this line starts a new leadership/award/scholarship entry.
    Never returns True for continuation lines or pure date lines.
    """
    stripped = line.strip()
    if not stripped:
        return False
    if BULLET_RE.match(stripped):
        return False

    # Pure date line → metadata for the CURRENT entry, never a new one
    if is_date_line(stripped):
        return False

    # Continuation line → definitely NOT a header
    if is_continuation(stripped, prev_line):
        return False

    # Description starters ("Awarded...", "Won first place...") are not new entries
    if DESCRIPTION_STARTERS.match(stripped):
        return False

    lower = stripped.lower()

    # Pipe separator usually means role | org | date → structured entry header
    if "|" in stripped:
        # But only if it contains a role/org keyword or award keyword
        if any(kw in lower for kw in ROLE_KEYWORDS + ORG_KEYWORDS + AWARD_KEYWORDS + SCHOLARSHIP_KEYWORDS):
            return True
        return False

    has_role    = any(kw in lower for kw in ROLE_KEYWORDS)
    has_org     = any(kw in lower for kw in ORG_KEYWORDS)
    has_award   = any(kw in lower for kw in AWARD_KEYWORDS)
    has_scholar = any(kw in lower for kw in SCHOLARSHIP_KEYWORDS)

    if has_role or has_org or has_award or has_scholar:
        return True

    return False


def _group_into_entries(lines: List[str]) -> List[List[str]]:
    """
    Group lines into entry blocks.
    
    Key rule: continuation lines always append to the current entry.
    Blank lines do NOT force a new entry — only a genuine new header does.
    """
    if not lines:
        return []

    groups: List[List[str]] = []
    current: List[str] = []
    prev_nonempty = ""

    for line in lines:
        stripped = line.strip()

        if not stripped:
            # Blank line: preserve but don't force a split
            if current:
                current.append("")
            continue

        if _is_entry_header(stripped, prev_nonempty) and current:
            # Strip trailing blanks from current group
            while current and not current[-1]:
                current.pop()
            groups.append(current)
            current = [stripped]
        else:
            current.append(stripped)

        prev_nonempty = stripped

    if current:
        while current and not current[-1]:
            current.pop()
        groups.append(current)

    return [g for g in groups if g]


def _parse_entry(lines: List[str]) -> Optional[Dict]:
    if not lines:
        return None

    bullets: List[str] = []
    header_lines: List[str] = []
    description_parts: List[str] = []

    prev = ""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            prev = stripped
            continue
        if BULLET_RE.match(stripped):
            content = BULLET_RE.sub("", stripped).strip()
            # Merge hyphen-continuation
            if bullets and prev.rstrip().endswith("-"):
                bullets[-1] = bullets[-1].rstrip("-") + content
            elif content:
                bullets.append(content)
        elif is_continuation(stripped, prev) and (bullets or description_parts or header_lines):
            # Continuation: merge into last bullet or description
            if bullets:
                bullets[-1] = bullets[-1].rstrip("-") + " " + stripped
            elif description_parts:
                description_parts[-1] += " " + stripped
            else:
                description_parts.append(stripped)
        else:
            header_lines.append(stripped)
        prev = stripped

    subtype = _classify_subtype(lines)
    role, org, start, end = _parse_header(header_lines)

    # If role/org not found from structured parse, use first header line as role
    if not role and header_lines:
        role = header_lines[0]

    return {
        "role":         role,
        "organization": org,
        "start_date":   start,
        "end_date":     end,
        "subtype":      subtype,
        "bullets":      bullets,
        "raw_lines":    lines,
    }


def _parse_header(header_lines: List[str]) -> Tuple:
    role = org = start_date = end_date = None

    for line in header_lines:
        parts = [p.strip() for p in PIPE_SEP_RE.split(line) if p.strip()]

        # Merge adjacent date fragments
        merged: List[str] = []
        for p in parts:
            if merged and is_date_line(merged[-1]) and is_date_line(p):
                merged[-1] = merged[-1] + " - " + p
            else:
                merged.append(p)

        if len(merged) >= 2:
            for part in merged:
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


def extract_leadership(raw_lines: List[str]) -> List[Dict]:
    content_lines = _get_content_lines(raw_lines)
    groups        = _group_into_entries(content_lines)
    return [e for e in (_parse_entry(g) for g in groups) if e]


def classify_leadership_entries(entries: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Split a flat leadership list into semantic buckets.
    Returns dict with keys: positions_of_responsibility, volunteer, awards,
    scholarships, leadership (catch-all).
    Useful for frontend display; existing API consumers continue to receive
    the flat list.
    """
    result: Dict[str, List[Dict]] = {
        "positions_of_responsibility": [],
        "volunteer": [],
        "awards": [],
        "scholarships": [],
        "leadership": [],
    }
    for entry in entries:
        st = entry.get("subtype", "leadership")
        if st == "position_of_responsibility":
            result["positions_of_responsibility"].append(entry)
        elif st == "volunteer":
            result["volunteer"].append(entry)
        elif st == "award":
            result["awards"].append(entry)
        elif st == "scholarship":
            result["scholarships"].append(entry)
        else:
            result["leadership"].append(entry)
    return result
