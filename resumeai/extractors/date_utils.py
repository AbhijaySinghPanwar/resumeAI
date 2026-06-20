"""
date_utils.py — Shared date parsing utilities for all extractors.

Handles the wide variety of date formats found on resumes:
  "May 2022", "2022", "2020 - 2022", "Jan 2019 – Present",
  "2019–2023", "08/2021", "Summer 2022", etc.
"""

import re
from typing import Optional, Tuple

# ── Month maps ────────────────────────────────────────────────────────────────
MONTH_MAP = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",
    "aug": "08", "august": "08",
    "sep": "09", "sept": "09", "september": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12",
}

PRESENT_TOKENS = {"present", "current", "now", "ongoing", "till date", "to date", "till now"}

# Year pattern: 4-digit year between 1970 and 2040
YEAR_RE = re.compile(r"\b(19[7-9]\d|20[0-3]\d)\b")

# Date range separators
RANGE_SEP_RE = re.compile(r"\s*[-–—to]+\s*", re.IGNORECASE)

# Month + year pattern
MONTH_YEAR_RE = re.compile(
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\s+(\d{4})",
    re.IGNORECASE,
)

# MM/YYYY or MM-YYYY
NUMERIC_DATE_RE = re.compile(r"\b(0?[1-9]|1[0-2])[/\-](\d{4})\b")


def parse_date(text: str) -> Optional[str]:
    """
    Parse a date string into a normalized form: "YYYY-MM" or "YYYY".
    Returns None if no date found.
    """
    text = text.strip().lower()

    if not text or text in PRESENT_TOKENS:
        return None

    # Month + Year
    m = MONTH_YEAR_RE.search(text)
    if m:
        month_str = m.group(1).lower()[:3]
        year = m.group(2)
        month_num = MONTH_MAP.get(month_str, "01")
        return f"{year}-{month_num}"

    # Numeric MM/YYYY
    m = NUMERIC_DATE_RE.search(text)
    if m:
        month_num = m.group(1).zfill(2)
        year = m.group(2)
        return f"{year}-{month_num}"

    # Year only
    m = YEAR_RE.search(text)
    if m:
        return m.group(1)

    return None


def parse_date_range(text: str) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Parse a date range string.
    Returns (start_date, end_date, is_current).

    Examples:
      "Jan 2020 – Present" → ("2020-01", None, True)
      "2019 - 2022"        → ("2019", "2022", False)
      "May 2021"           → ("2021-05", None, False)
    """
    text = text.strip()
    text_lower = text.lower()

    is_current = any(token in text_lower for token in PRESENT_TOKENS)

    # Try to split on range separator
    parts = RANGE_SEP_RE.split(text, maxsplit=1)

    if len(parts) == 2:
        start = parse_date(parts[0].strip())
        end_text = parts[1].strip()
        end = None if any(t in end_text.lower() for t in PRESENT_TOKENS) else parse_date(end_text)
        return start, end, is_current

    # Single date
    single = parse_date(text)
    return single, None, is_current


def extract_years(text: str) -> list:
    """Extract all 4-digit years from text."""
    return YEAR_RE.findall(text)


def is_date_line(text: str) -> bool:
    """Heuristic: does this line look like a date or date range?"""
    text_lower = text.lower().strip()
    has_year = bool(YEAR_RE.search(text))
    has_month = bool(MONTH_YEAR_RE.search(text))
    has_present = any(t in text_lower for t in PRESENT_TOKENS)
    return (has_year or has_month or has_present) and len(text) < 50
