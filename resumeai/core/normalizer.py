"""
normalizer.py — Deterministic artifact normalization for PDF-extracted text.

Every transformation is logged. Nothing is silently discarded.
This module is pure: no side effects, no global state.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class NormalizationResult:
    original: str
    normalized: str
    transformations: List[str] = field(default_factory=list)

    @property
    def was_modified(self) -> bool:
        return self.original != self.normalized


# ── Unicode character sets ────────────────────────────────────────────────────

# Zero-width and invisible characters
ZERO_WIDTH_CHARS = {
    "\u200b",  # zero-width space
    "\u200c",  # zero-width non-joiner
    "\u200d",  # zero-width joiner
    "\ufeff",  # byte order mark / zero-width no-break space
    "\u00ad",  # soft hyphen
    "\u200e",  # left-to-right mark
    "\u200f",  # right-to-left mark
    "\u2028",  # line separator
    "\u2029",  # paragraph separator
}

# Unicode dashes → ASCII hyphen
DASH_CHARS = {
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2012": "-",  # figure dash
    "\u2015": "-",  # horizontal bar
    "\u2212": "-",  # minus sign
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\ufe58": "-",  # small em dash
    "\ufe63": "-",  # small hyphen-minus
    "\uff0d": "-",  # fullwidth hyphen-minus
}

# Unicode ampersands → ASCII &
AMPERSAND_CHARS = {
    "\ufe60": "&",  # small ampersand
    "\uff06": "&",  # fullwidth ampersand
    "\u0026": "&",  # already ASCII (no-op, just for completeness)
}

# Unicode bullet-like characters → ASCII hyphen (for content lines)
BULLET_CHARS = {
    "\u2022", "\u2023", "\u2024", "\u2025",
    "\u2043", "\u204c", "\u204d", "\u2219",
    "\u25aa", "\u25ab", "\u25b8", "\u25cf",
    "\u25e6", "\u2756", "\u2762", "\u29bf",
}

# Smart quotes → straight quotes
QUOTE_MAP = {
    "\u2018": "'", "\u2019": "'",  # single
    "\u201c": '"', "\u201d": '"',  # double
    "\u201a": ",",  # low-9 quotation mark (often misused as comma)
}

# Spaced-character pattern: "L e a d e r s h i p" → "Leadership"
# Matches sequences of single chars separated by single spaces
_SPACED_CHARS_RE = re.compile(r"(?<!\w)([A-Za-z] ){3,}[A-Za-z](?!\w)")


def _collapse_spaced_chars(text: str) -> Tuple[str, bool]:
    """
    Detect and collapse spaced-out characters from PDF extraction artifacts.
    e.g. "L e a d e r s h i p" → "Leadership"
    Returns (result, was_modified).
    """
    def collapse(match: re.Match) -> str:
        return match.group(0).replace(" ", "")

    result = _SPACED_CHARS_RE.sub(collapse, text)
    return result, result != text


def normalize_line(raw: str) -> NormalizationResult:
    """
    Apply deterministic artifact normalization to a single line.

    Transformations applied in order:
      1. Strip leading/trailing whitespace
      2. Remove zero-width / invisible characters
      3. Normalize Unicode dashes to ASCII hyphen
      4. Normalize Unicode ampersands to ASCII &
      5. Normalize smart quotes
      6. Collapse spaced-out characters (PDF artifact)
      7. Collapse internal whitespace runs to single space
      8. Strip bullet characters from line start (for content lines)

    All transformations are logged.
    """
    text = raw
    log: List[str] = []

    # 1. Strip leading/trailing whitespace
    stripped = text.strip()
    if stripped != text:
        log.append("stripped_whitespace")
        text = stripped

    # 2. Remove zero-width characters
    cleaned = "".join(c for c in text if c not in ZERO_WIDTH_CHARS)
    if cleaned != text:
        removed = [repr(c) for c in text if c in ZERO_WIDTH_CHARS]
        log.append(f"removed_zero_width:{','.join(set(removed))}")
        text = cleaned

    # 3. Normalize Unicode dashes
    dash_result = text
    for ch, replacement in DASH_CHARS.items():
        if ch in dash_result:
            dash_result = dash_result.replace(ch, replacement)
    if dash_result != text:
        log.append("normalized_unicode_dashes")
        text = dash_result

    # 4. Normalize Unicode ampersands
    amp_result = text
    for ch, replacement in AMPERSAND_CHARS.items():
        if ch in amp_result and ch != "\u0026":
            amp_result = amp_result.replace(ch, replacement)
    if amp_result != text:
        log.append("normalized_unicode_ampersands")
        text = amp_result

    # 5. Normalize smart quotes
    quote_result = text
    for ch, replacement in QUOTE_MAP.items():
        if ch in quote_result:
            quote_result = quote_result.replace(ch, replacement)
    if quote_result != text:
        log.append("normalized_smart_quotes")
        text = quote_result

    # 6. Collapse spaced-out characters
    spaced_result, was_spaced = _collapse_spaced_chars(text)
    if was_spaced:
        log.append("collapsed_spaced_characters")
        text = spaced_result

    # 7. Collapse internal whitespace
    ws_result = re.sub(r"[ \t]+", " ", text)
    if ws_result != text:
        log.append("collapsed_internal_whitespace")
        text = ws_result

    # 8. Strip leading bullet characters (marks content, doesn't affect header detection)
    if text and text[0] in BULLET_CHARS:
        text = text[1:].lstrip()
        log.append("stripped_leading_bullet")

    return NormalizationResult(
        original=raw,
        normalized=text,
        transformations=log,
    )


def normalize_for_matching(text: str) -> str:
    """
    Return a case-folded, fully normalized string suitable for alias lookup.
    Does NOT modify the stored normalized text — only for comparison.
    """
    result = normalize_line(text)
    return result.normalized.lower().strip()


def is_likely_empty(text: str) -> bool:
    """Return True if the line contains no meaningful content after normalization."""
    normalized = normalize_for_matching(text)
    return len(normalized) == 0 or all(c in "-–—_=*#~" for c in normalized)
