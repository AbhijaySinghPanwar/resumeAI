"""
summary.py — Extract the professional summary/objective block.
"""

from typing import List, Optional


def extract_summary(raw_lines: List[str]) -> Optional[str]:
    content_lines = _get_content_lines(raw_lines)
    if not content_lines:
        return None
    return " ".join(line.strip() for line in content_lines if line.strip())


def _get_content_lines(raw_lines: List[str]) -> List[str]:
    lines = [l for l in raw_lines if l.strip()]
    if not lines:
        return []
    first_lower = lines[0].strip().lower()
    skip_keywords = [
        "summary", "objective", "profile", "about", "overview",
        "introduction", "professional summary", "career objective",
    ]
    if any(kw in first_lower for kw in skip_keywords) and len(lines[0].strip()) < 50:
        return lines[1:]
    return lines
