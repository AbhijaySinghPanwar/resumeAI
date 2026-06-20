"""
header_detector.py — Standalone header detection engine.

Takes a single line (and optional context) and returns a structured
HeaderDetectionResult. No document state. No side effects. Pure function.

Detection pipeline:
  Stage 1: Artifact normalization (via normalizer.py)
  Stage 2: Structural signal scoring
  Stage 3: Exact alias matching
  Stage 4: Combined header resolution
  Stage 5: Fuzzy matching fallback
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from rapidfuzz import fuzz, process

# Date range pattern — lines matching this are content, never headers
# e.g. "June 2021 – Present", "Jan 2020 - Dec 2022", "2019 - 2023"
_DATE_RANGE_DISQUALIFIER = re.compile(
    r"^(?:"
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\s+\d{4}"   # "June 2021"
    r"|"
    r"\d{4}\s*[-–—]\s*(?:\d{4}|present|current)"  # "2019 - 2023"
    r")"
    r"(?:\s*[-–—]\s*(?:\d{4}|present|current))?$",  # optional range end
    re.IGNORECASE,
)

from resumeai.core.constants import (
    ALIAS_LOOKUP,
    ALIAS_WEIGHTS,
    CANONICAL_SECTIONS,
    COMBINED_SEPARATORS,
    FUZZY_ACCEPT_THRESHOLD,
    FUZZY_AMBIGUOUS_THRESHOLD,
    HEADER_CONFIDENCE_ACCEPT,
    HEADER_CONFIDENCE_AMBIGUOUS,
    MAX_HEADER_LENGTH,
    MIN_ALL_CAPS_LENGTH,
    SECTION_PRIORITY,
    normalize_alias,
)
from resumeai.core.normalizer import NormalizationResult, normalize_for_matching, normalize_line


@dataclass
class FuzzyCandidate:
    alias: str
    canonical_section: str
    score: float   # 0.0–1.0
    method: str    # "token_ratio" | "partial_ratio" | "edit_distance"


@dataclass
class HeaderDetectionResult:
    # Input
    original_line: str
    line_number: int

    # Normalization
    normalization: NormalizationResult

    # Decision
    is_header: bool
    confidence: float                          # 0.0–1.0
    canonical_section: Optional[str]           # None if unrecognized
    match_method: str                          # "exact"|"fuzzy"|"combined"|"structural_only"|"none"

    # Combined header data
    combined_sections: List[str] = field(default_factory=list)

    # Diagnostics
    structural_score: float = 0.0
    alias_score: float = 0.0
    fuzzy_candidates: List[FuzzyCandidate] = field(default_factory=list)
    signals_fired: List[str] = field(default_factory=list)

    @property
    def normalized_line(self) -> str:
        return self.normalization.normalized

    @property
    def is_unrecognized_header(self) -> bool:
        """Header-like line that couldn't be mapped to a canonical section."""
        return (
            self.is_header
            and self.canonical_section is None
            and self.confidence >= HEADER_CONFIDENCE_AMBIGUOUS
        )


# ── Stage 2: Structural signal scoring ───────────────────────────────────────

def _structural_score(normalized: str, prev_line: str = "", next_line: str = "", line_number: int = -1) -> Tuple[float, List[str]]:
    """
    Score how header-like a line looks based purely on its structure.
    Returns (score 0.0–1.0, list of signals that fired).
    """
    text = normalized.strip()
    signals: List[str] = []
    score = 0.0

    if not text:
        return 0.0, []

    # Hard disqualifiers: lines that cannot be headers
    if len(text) > MAX_HEADER_LENGTH:
        return 0.0, ["disqualified:too_long"]

    # Candidate Name Detection Rule
    words = text.split()
    if 0 <= line_number <= 2 and 1 <= len(words) <= 4:
        next_lower = next_line.lower()
        # Ensure we can use PHONE_RE, wait, PHONE_RE is in contact.py
        # Let's just do a simple digit check for phone since we don't want to import contact.py here to avoid circular dependencies
        import re
        if (
            "@" in next_lower
            or "linkedin" in next_lower
            or "github" in next_lower
            or re.search(r"\d{7,}", next_lower)  # 7+ consecutive digits (basic phone check)
            or re.search(r"\+\d{1,3}\s*\d{3}", next_lower) # +91 963...
        ):
            return 0.0, ["disqualified:candidate_name"]

    # Date range lines are always content, never headers
    if _DATE_RANGE_DISQUALIFIER.match(text.strip()):
        return 0.0, ["disqualified:date_range_pattern"]

    # Terminal punctuation strongly suggests content, not a header
    if text.endswith((".", ",", ";", "!", "?")):
        return 0.0, ["disqualified:terminal_punctuation"]

    # Contains sentence-like structures (multiple words with lowercase mid-sentence)
    words = text.split()
    if len(words) > 8:
        return 0.0, ["disqualified:too_many_words"]

    # ── Positive signals ──────────────────────────────────────────────────────

    # All-caps (minimum length to avoid "CV", "ID" false positives)
    if text.upper() == text and len(text) >= MIN_ALL_CAPS_LENGTH and text.replace(" ", "").isalpha():
        score += 0.4
        signals.append("all_caps")

    # Ends with colon
    if text.endswith(":"):
        score += 0.3
        signals.append("ends_with_colon")

    # Short line (1–4 words)
    word_count = len(words)
    if 1 <= word_count <= 4:
        score += 0.2
        signals.append(f"short_line:{word_count}_words")
    elif 5 <= word_count <= 6:
        score += 0.1
        signals.append(f"medium_line:{word_count}_words")

    # Title case (each word starts uppercase)
    title_words = [w for w in words if w.isalpha()]
    if title_words and all(w[0].isupper() for w in title_words):
        score += 0.15
        signals.append("title_case")
        # Multi-word title-case lines (3+ words) that are not dates are strong header candidates
        if len(title_words) >= 3:
            score += 0.10
            signals.append("multi_word_title_case")

    # Contextual: preceded by blank line
    if not prev_line.strip():
        score += 0.1
        signals.append("preceded_by_blank")

    # Contextual: followed by blank line or indented content
    if not next_line.strip():
        score += 0.05
        signals.append("followed_by_blank")
    elif next_line.startswith(("  ", "\t")):
        score += 0.05
        signals.append("followed_by_indent")

    # Contains separator (combined header signal)
    for sep in COMBINED_SEPARATORS:
        if sep.strip() in text:
            score += 0.05
            signals.append(f"contains_separator:{repr(sep.strip())}")
            break

    return min(score, 1.0), signals


# ── Stage 3: Exact alias matching ────────────────────────────────────────────

def _exact_alias_match(normalized_lower: str) -> Optional[Tuple[str, float]]:
    """
    Look up the normalized lowercase line in the alias registry.
    Returns (canonical_section, weight) or None.
    """
    norm = normalize_alias(normalized_lower)
    if norm in ALIAS_LOOKUP:
        return ALIAS_LOOKUP[norm], ALIAS_WEIGHTS[norm]
    return None


# ── Stage 4: Combined header resolution ──────────────────────────────────────

def _split_on_separators(text: str) -> List[str]:
    """Split a header on known combined-header separators."""
    # Build regex that splits on any separator
    sep_pattern = "|".join(
        re.escape(s) for s in sorted(COMBINED_SEPARATORS, key=len, reverse=True)
    )
    parts = re.split(sep_pattern, text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def _resolve_combined_header(normalized_lower: str) -> Optional[Tuple[str, List[str]]]:
    """
    Attempt to resolve a combined header like "Leadership & Activities".
    Returns (primary_canonical_section, [all_matched_sections]) or None.
    """
    parts = _split_on_separators(normalized_lower)
    if len(parts) < 2:
        return None

    matched_sections = []
    for part in parts:
        match = _exact_alias_match(part)
        if match:
            section, _ = match
            if section not in matched_sections:
                matched_sections.append(section)

    if not matched_sections:
        return None

    if len(matched_sections) == 1:
        # If less than 50% of the parts match an alias, it's just a content line
        if len(matched_sections) / len(parts) < 0.5:
            return None
        # Only one part matched — still valid, use it
        return matched_sections[0], matched_sections

    # Multiple sections matched — pick highest priority
    primary = max(
        matched_sections,
        key=lambda s: SECTION_PRIORITY.index(s) if s in SECTION_PRIORITY else -1,
    )
    return primary, matched_sections


# ── Stage 5: Fuzzy matching ───────────────────────────────────────────────────

_ALL_ALIASES = list(ALIAS_LOOKUP.keys())


def _fuzzy_match(normalized_lower: str, top_n: int = 5) -> List[FuzzyCandidate]:
    """
    Run fuzzy matching against all known aliases.
    Returns top_n candidates sorted by score descending.
    """
    # rapidfuzz process.extract returns (match, score, index)
    results = process.extract(
        normalized_lower,
        _ALL_ALIASES,
        scorer=fuzz.token_sort_ratio,
        limit=top_n,
    )

    candidates = []
    for alias, score, _ in results:
        candidates.append(FuzzyCandidate(
            alias=alias,
            canonical_section=ALIAS_LOOKUP[alias],
            score=score / 100.0,  # normalize to 0.0–1.0
            method="token_sort_ratio",
        ))

    return candidates


# ── Main detector ─────────────────────────────────────────────────────────────

def detect_header(
    raw_line: str,
    line_number: int = 0,
    prev_line: str = "",
    next_line: str = "",
) -> HeaderDetectionResult:
    """
    Determine whether a line is a section header, and if so, which section.

    Returns a fully populated HeaderDetectionResult.
    This function is pure: same inputs always produce same outputs.
    """
    # ── Stage 1: Normalize ───────────────────────────────────────────────────
    normalization = normalize_line(raw_line)
    normalized = normalization.normalized
    normalized_lower = normalized.lower().strip()

    # Empty lines are never headers
    if not normalized_lower:
        return HeaderDetectionResult(
            original_line=raw_line,
            line_number=line_number,
            normalization=normalization,
            is_header=False,
            confidence=0.0,
            canonical_section=None,
            match_method="none",
        )

    # ── Stage 2: Structural scoring ──────────────────────────────────────────
    struct_score, signals = _structural_score(
        normalized,
        prev_line=prev_line,
        next_line=next_line,
        line_number=line_number,
    )

    # If structural score is zero, this cannot be a header regardless of alias
    if struct_score == 0.0 and normalized_lower not in ALIAS_LOOKUP:
        return HeaderDetectionResult(
            original_line=raw_line,
            line_number=line_number,
            normalization=normalization,
            is_header=False,
            confidence=0.0,
            canonical_section=None,
            match_method="none",
            structural_score=0.0,
            signals_fired=signals,
        )

    # ── Stage 3: Exact alias match ───────────────────────────────────────────
    exact = _exact_alias_match(normalized_lower)
    if exact:
        canonical, alias_weight = exact
        # Blend structural and alias scores
        confidence = struct_score * 0.3 + alias_weight * 0.7
        # Exact alias always meets the accept threshold
        confidence = max(confidence, HEADER_CONFIDENCE_ACCEPT)
        return HeaderDetectionResult(
            original_line=raw_line,
            line_number=line_number,
            normalization=normalization,
            is_header=True,
            confidence=min(confidence, 1.0),
            canonical_section=canonical,
            match_method="exact",
            structural_score=struct_score,
            alias_score=alias_weight,
            signals_fired=signals,
        )

    # ── Stage 4: Combined header resolution ──────────────────────────────────
    combined = _resolve_combined_header(normalized_lower)
    if combined:
        primary, all_sections = combined
        confidence = struct_score * 0.3 + 0.9 * 0.7  # combined match weight = 0.9
        confidence = max(confidence, HEADER_CONFIDENCE_ACCEPT)
        return HeaderDetectionResult(
            original_line=raw_line,
            line_number=line_number,
            normalization=normalization,
            is_header=True,
            confidence=min(confidence, 1.0),
            canonical_section=primary,
            match_method="combined",
            combined_sections=all_sections,
            structural_score=struct_score,
            signals_fired=signals,
        )

    # ── Stage 5: Fuzzy matching (only if structural score is meaningful) ──────
    fuzzy_candidates: List[FuzzyCandidate] = []
    if struct_score >= 0.15:
        fuzzy_candidates = _fuzzy_match(normalized_lower)
        if fuzzy_candidates:
            best = fuzzy_candidates[0]
            if best.score >= FUZZY_ACCEPT_THRESHOLD:
                confidence = struct_score * 0.4 + best.score * 0.6
                if confidence >= HEADER_CONFIDENCE_AMBIGUOUS:
                    return HeaderDetectionResult(
                        original_line=raw_line,
                        line_number=line_number,
                        normalization=normalization,
                        is_header=True,
                        confidence=confidence,
                        canonical_section=best.canonical_section,
                        match_method="fuzzy",
                        structural_score=struct_score,
                        fuzzy_candidates=fuzzy_candidates,
                        signals_fired=signals,
                    )
            elif best.score >= FUZZY_AMBIGUOUS_THRESHOLD:
                # Ambiguous: header-like but unrecognized → other_section
                confidence = struct_score * 0.5 + best.score * 0.3
                if confidence >= HEADER_CONFIDENCE_AMBIGUOUS:
                    return HeaderDetectionResult(
                        original_line=raw_line,
                        line_number=line_number,
                        normalization=normalization,
                        is_header=True,
                        confidence=confidence,
                        canonical_section=None,   # → other_section
                        match_method="fuzzy",
                        structural_score=struct_score,
                        fuzzy_candidates=fuzzy_candidates,
                        signals_fired=signals,
                    )

    # ── Structural-only header (no alias match) ───────────────────────────────
    if struct_score >= HEADER_CONFIDENCE_ACCEPT:
        return HeaderDetectionResult(
            original_line=raw_line,
            line_number=line_number,
            normalization=normalization,
            is_header=True,
            confidence=struct_score,
            canonical_section=None,   # → other_section
            match_method="structural_only",
            structural_score=struct_score,
            fuzzy_candidates=fuzzy_candidates,
            signals_fired=signals,
        )

    if struct_score >= HEADER_CONFIDENCE_AMBIGUOUS:
        return HeaderDetectionResult(
            original_line=raw_line,
            line_number=line_number,
            normalization=normalization,
            is_header=True,
            confidence=struct_score,
            canonical_section=None,
            match_method="structural_only",
            structural_score=struct_score,
            fuzzy_candidates=fuzzy_candidates,
            signals_fired=signals,
        )

    # ── Not a header ──────────────────────────────────────────────────────────
    return HeaderDetectionResult(
        original_line=raw_line,
        line_number=line_number,
        normalization=normalization,
        is_header=False,
        confidence=struct_score,
        canonical_section=None,
        match_method="none",
        structural_score=struct_score,
        fuzzy_candidates=fuzzy_candidates,
        signals_fired=signals,
    )
