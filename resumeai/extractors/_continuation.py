"""
_continuation.py — Shared continuation-line detection for all extractors.

A "continuation line" is a line that CONTINUES the previous block rather
than starting a new one. This is the central cause of split certifications,
split project descriptions, and split bullets across all resume formats.

Continuation signals (any one is sufficient):
  1. Starts with lowercase letter (not a heading or new entry)
  2. Starts with conjunction / preposition (and, or, with, for, using, via...)
  3. Starts with punctuation that implies continuation (, . ; : )
  4. Is a URL (always attaches to the current block)
  5. Is a GitHub / Live Demo / Repository link label
  6. Is a known link-label line (see LINK_LABEL_RE)
  7. Very short word-fragment (1-2 words, no capitals, no tech keywords)
"""

import re
from typing import Optional

# Link label lines — always attach to current block
LINK_LABEL_RE = re.compile(
    r"^(github\s*(link|repo(?:sitory)?)?|live\s*demo|demo|repository|"
    r"source\s*code|working\s*(project\s*)?link|deployed\s*link|"
    r"project\s*link|website|portfolio|view\s*project|view\s*demo|"
    r"click\s*here|here|deployment|app\s*link|"
    r"source|repo)\s*[:\-]?\s*(https?://\S+)?$",
    re.IGNORECASE,
)

# URL anywhere in line → continuation
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

# Starts with these words → almost always continuation
CONTINUATION_STARTERS = re.compile(
    r"^(and|or|with|for|using|via|through|by|to|into|from|on|at|in|"
    r"as|such|including|e\.g\.|i\.e\.|also|while|when|where|which|"
    r"that|based|focused|designed|built|made|implemented|integrated|"
    r"leverag|utiliz|employ)\b",
    re.IGNORECASE,
)

# Starts with punctuation → continuation
PUNCT_CONTINUATION_RE = re.compile(r"^[,\.;\:\-\–\—\(\)]")


def is_continuation(line: str, prev_line: Optional[str] = None) -> bool:
    """
    Return True if `line` is a continuation of the previous block.
    """
    stripped = line.strip()
    if not stripped:
        return False

    # 1. Previous line ended with a hyphen → this is a wrapped word
    if prev_line and prev_line.rstrip().endswith("-"):
        return True

    # 2. URL → always continuation
    if URL_RE.search(stripped):
        return True

    # 3. Known link label → always continuation
    if LINK_LABEL_RE.match(stripped):
        return True

    # 4. Starts with punctuation
    if PUNCT_CONTINUATION_RE.match(stripped):
        return True

    # 5. Starts with lowercase (but not a list item like "• …")
    first_char = stripped[0]
    if first_char.islower():
        return True

    # 6. Starts with continuation conjunctions / prepositions
    if CONTINUATION_STARTERS.match(stripped):
        return True

    # 7. Single-word fragment ending with period → sentence continuation
    #    e.g. "Studio." "orations." "interaction." "performance."
    words = stripped.split()
    if len(words) == 1 and stripped.endswith(".") and not stripped[0].isupper() is False:
        # One word ending in period that is NOT a known section header → continuation
        known_sections = {"education", "experience", "skills", "projects", "certifications",
                          "leadership", "awards", "summary", "contact", "references"}
        if stripped.rstrip(".").lower() not in known_sections and len(stripped) < 25:
            return True

    return False


def is_link_label_line(line: str) -> bool:
    """True if the entire line is a link label (GitHub, Live Demo, etc.)."""
    return bool(LINK_LABEL_RE.match(line.strip()))
