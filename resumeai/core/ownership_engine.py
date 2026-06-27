"""
ownership_engine.py — Deterministic Section Ownership Engine.

Core guarantees:
  - Every line belongs to exactly one SectionBlock.
  - No line may belong to multiple SectionBlocks.
  - Unknown lines go to other_section.
  - Ownership transitions are logged.
  - The sum of all block line counts equals total document lines.

This module does NOT extract fields. It segments. That is all.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from resumeai.core.constants import (
    HEADER_CONFIDENCE_ACCEPT,
    HEADER_CONFIDENCE_AMBIGUOUS,
    LARGE_SECTION_RATIO,
    MAX_CERT_LINES_EXPECTED,
    PARSER_VERSION,
)
from resumeai.core.header_detector import HeaderDetectionResult, detect_header
from resumeai.core.normalizer import is_likely_empty


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class SectionBlock:
    """
    A contiguous run of lines belonging to one canonical section.
    This is the fundamental unit produced by the ownership engine.
    """
    section_name: str          # always a member of CANONICAL_SECTIONS
    start_line: int            # inclusive, 0-indexed from raw extraction
    end_line: int              # inclusive (updated as lines are added)
    raw_lines: List[str]       # unmodified lines from extraction
    header_line: str           # exact line that triggered this block
    header_confidence: float   # 0.0–1.0 from header detector
    transition_reason: str     # why ownership transferred here
    header_result: Optional[HeaderDetectionResult] = None  # full detection result

    @property
    def line_count(self) -> int:
        return len(self.raw_lines)

    def append_line(self, line: str) -> None:
        self.raw_lines.append(line)
        self.end_line = self.start_line + len(self.raw_lines) - 1

    def to_dict(self) -> dict:
        return {
            "section_name": self.section_name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "line_count": self.line_count,
            "header_line": self.header_line,
            "header_confidence": round(self.header_confidence, 4),
            "transition_reason": self.transition_reason,
        }


@dataclass
class OwnershipTransition:
    """Record of a section boundary crossing."""
    from_section: str
    to_section: str
    at_line: int
    trigger_line: str
    confidence: float
    previous_block_line_count: int
    reason: str


@dataclass
class OwnershipLogEntry:
    """Per-line ownership record."""
    line_number: int
    raw_line: str
    assigned_section: str
    assignment_reason: str   # "content"|"header_transition"|"preamble"|"ambiguous_header"


@dataclass
class AnomalyRecord:
    type: str
    section: str
    detail: str
    severity: str   # "warning" | "error"


@dataclass
class DebugOutput:
    """Complete debug output from the ownership engine."""
    parser_version: str
    parse_timestamp: str
    source_hash: str
    total_lines: int
    detected_headers: List[dict]
    section_transitions: List[dict]
    unrecognized_headers: List[dict]
    ownership_log: List[dict]
    artifact_warnings: List[dict]
    section_summary: Dict[str, dict]
    anomalies: List[dict]

    def to_dict(self) -> dict:
        return {
            "parser_version": self.parser_version,
            "parse_timestamp": self.parse_timestamp,
            "source_hash": self.source_hash,
            "total_lines": self.total_lines,
            "detected_headers": self.detected_headers,
            "section_transitions": self.section_transitions,
            "unrecognized_headers": self.unrecognized_headers,
            "ownership_log": self.ownership_log,
            "artifact_warnings": self.artifact_warnings,
            "section_summary": self.section_summary,
            "anomalies": self.anomalies,
        }


@dataclass
class OwnershipResult:
    """Complete output of the ownership engine."""
    blocks: List[SectionBlock]
    debug: DebugOutput
    total_lines: int

    def blocks_by_section(self, section_name: str) -> List[SectionBlock]:
        return [b for b in self.blocks if b.section_name == section_name]

    def all_lines_for_section(self, section_name: str) -> List[str]:
        lines = []
        for block in self.blocks_by_section(section_name):
            lines.extend(block.raw_lines)
        return lines

    def verify_invariants(self) -> List[str]:
        """
        Verify structural invariants. Returns list of violations (empty = all OK).
        This should return [] for every valid parse result.
        """
        violations = []
        seen_lines = set()

        for block in self.blocks:
            if block.section_name not in {
                "contact", "summary", "education", "experience",
                "projects", "leadership", "certifications", "skills", 
                "open_source", "achievements", "publications", 
                "hackathons", "research", "tech_blogs", "other_section"
            }:
                violations.append(
                    f"Block has invalid section_name: {block.section_name!r}"
                )

            if block.line_count == 0:
                violations.append(
                    f"Block {block.section_name} at line {block.start_line} has zero lines"
                )

            for i, line in enumerate(block.raw_lines):
                abs_line = block.start_line + i
                if abs_line in seen_lines:
                    violations.append(
                        f"Line {abs_line} appears in multiple blocks (duplicate ownership)"
                    )
                seen_lines.add(abs_line)

        # Check for gaps
        if seen_lines:
            expected = set(range(0, self.total_lines))
            missing = expected - seen_lines
            extra = seen_lines - expected
            if missing:
                violations.append(f"Lines not assigned to any block: {sorted(missing)[:10]}")
            if extra:
                violations.append(f"Block references out-of-range lines: {sorted(extra)[:10]}")

        return violations


# ── Ownership State Machine ───────────────────────────────────────────────────

class OwnershipEngine:
    """
    Linear, single-pass document segmentation engine.

    States: PREAMBLE → IN_SECTION
    Transitions occur only when header detection fires above threshold.
    The previous block is CLOSED the instant a new one begins.
    """

    def __init__(self, confidence_accept: float = HEADER_CONFIDENCE_ACCEPT,
                 confidence_ambiguous: float = HEADER_CONFIDENCE_AMBIGUOUS):
        self._confidence_accept = confidence_accept
        self._confidence_ambiguous = confidence_ambiguous

    def segment(self, raw_lines: List[str], source_id: str = "") -> OwnershipResult:
        """
        Segment a document into SectionBlocks.

        Args:
            raw_lines: Lines from PDF/text extraction, unmodified.
            source_id: Identifier for this document (used in debug output).

        Returns:
            OwnershipResult with blocks, debug output, and invariant-ready data.
        """
        import datetime

        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
        source_hash = hashlib.sha256("\n".join(raw_lines).encode()).hexdigest()[:16]

        blocks: List[SectionBlock] = []
        transitions: List[OwnershipTransition] = []
        ownership_log: List[OwnershipLogEntry] = []
        detected_headers: List[HeaderDetectionResult] = []
        unrecognized_headers: List[HeaderDetectionResult] = []
        artifact_warnings: List[dict] = []

        # ── Initial state: PREAMBLE ───────────────────────────────────────────
        # Lines before any recognized header go to the contact block
        current_block = SectionBlock(
            section_name="contact",
            start_line=0,
            end_line=0,
            raw_lines=[],
            header_line="[PREAMBLE]",
            header_confidence=1.0,
            transition_reason="preamble_default",
        )

        total_lines = len(raw_lines)

        for i, raw_line in enumerate(raw_lines):
            prev_line = raw_lines[i - 1] if i > 0 else ""
            next_line = raw_lines[i + 1] if i < total_lines - 1 else ""

            # Detect header for this line
            result = detect_header(
                raw_line=raw_line,
                line_number=i,
                prev_line=prev_line,
                next_line=next_line,
            )

            # Log any normalization artifacts
            if result.normalization.transformations:
                artifact_warnings.append({
                    "line_number": i,
                    "artifact_types": result.normalization.transformations,
                    "original": raw_line,
                    "normalized": result.normalization.normalized,
                })

            # ── Ownership decision ────────────────────────────────────────────
            if result.is_header and result.confidence >= self._confidence_accept:
                # CONFIRMED HEADER → close current block, open new block
                target_section = result.canonical_section or "other_section"

                if current_block.line_count > 0:
                    blocks.append(current_block)

                transitions.append(OwnershipTransition(
                    from_section=current_block.section_name,
                    to_section=target_section,
                    at_line=i,
                    trigger_line=raw_line.strip(),
                    confidence=result.confidence,
                    previous_block_line_count=current_block.line_count,
                    reason=f"header_detected:{result.match_method}",
                ))

                current_block = SectionBlock(
                    section_name=target_section,
                    start_line=i,
                    end_line=i,
                    raw_lines=[raw_line],
                    header_line=raw_line,
                    header_confidence=result.confidence,
                    transition_reason=f"header:{result.match_method}",
                    header_result=result,
                )

                detected_headers.append(result)
                if result.canonical_section is None:
                    unrecognized_headers.append(result)

                ownership_log.append(OwnershipLogEntry(
                    line_number=i,
                    raw_line=raw_line,
                    assigned_section=target_section,
                    assignment_reason="header_transition",
                ))

            elif result.is_header and result.confidence >= self._confidence_ambiguous:
                # AMBIGUOUS HEADER → close current block, open other_section block
                # Critical: the previous section is CLOSED. No bleeding.
                if current_block.line_count > 0:
                    blocks.append(current_block)

                transitions.append(OwnershipTransition(
                    from_section=current_block.section_name,
                    to_section="other_section",
                    at_line=i,
                    trigger_line=raw_line.strip(),
                    confidence=result.confidence,
                    previous_block_line_count=current_block.line_count,
                    reason="ambiguous_header",
                ))

                current_block = SectionBlock(
                    section_name="other_section",
                    start_line=i,
                    end_line=i,
                    raw_lines=[raw_line],
                    header_line=raw_line,
                    header_confidence=result.confidence,
                    transition_reason="ambiguous_header",
                    header_result=result,
                )

                detected_headers.append(result)
                unrecognized_headers.append(result)

                ownership_log.append(OwnershipLogEntry(
                    line_number=i,
                    raw_line=raw_line,
                    assigned_section="other_section",
                    assignment_reason="ambiguous_header",
                ))

            else:
                # CONTENT LINE → append to current block
                current_block.append_line(raw_line)

                ownership_log.append(OwnershipLogEntry(
                    line_number=i,
                    raw_line=raw_line,
                    assigned_section=current_block.section_name,
                    assignment_reason="content",
                ))

        # Close final block
        if current_block.line_count > 0:
            blocks.append(current_block)

        # ── Build section summary ─────────────────────────────────────────────
        section_summary = self._build_section_summary(blocks)

        # ── Anomaly detection ─────────────────────────────────────────────────
        anomalies = self._detect_anomalies(blocks, total_lines, ownership_log)

        # ── Build debug output ────────────────────────────────────────────────
        debug = DebugOutput(
            parser_version=PARSER_VERSION,
            parse_timestamp=timestamp,
            source_hash=source_hash,
            total_lines=total_lines,
            detected_headers=[self._header_result_to_dict(h) for h in detected_headers],
            section_transitions=[self._transition_to_dict(t) for t in transitions],
            unrecognized_headers=[self._header_result_to_dict(h) for h in unrecognized_headers],
            ownership_log=[self._log_entry_to_dict(e) for e in ownership_log],
            artifact_warnings=artifact_warnings,
            section_summary=section_summary,
            anomalies=[a.__dict__ for a in anomalies],
        )

        return OwnershipResult(
            blocks=blocks,
            debug=debug,
            total_lines=total_lines,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_section_summary(self, blocks: List[SectionBlock]) -> Dict[str, dict]:
        summary: Dict[str, dict] = {}
        for block in blocks:
            name = block.section_name
            if name not in summary:
                summary[name] = {"block_count": 0, "total_lines": 0}
            summary[name]["block_count"] += 1
            summary[name]["total_lines"] += block.line_count
        return summary

    def _detect_anomalies(
        self,
        blocks: List[SectionBlock],
        total_lines: int,
        ownership_log: List[OwnershipLogEntry],
    ) -> List[AnomalyRecord]:
        anomalies: List[AnomalyRecord] = []

        if total_lines == 0:
            return anomalies

        section_line_counts: Dict[str, int] = {}
        for block in blocks:
            section_line_counts[block.section_name] = (
                section_line_counts.get(block.section_name, 0) + block.line_count
            )

        # empty section (expected sections that are completely missing)
        for expected in ["education", "experience", "skills"]:
            if section_line_counts.get(expected, 0) == 0:
                anomalies.append(AnomalyRecord(
                    type="empty_section",
                    section=expected,
                    detail=f"No lines assigned to {expected}",
                    severity="warning",
                ))

        # suspiciously large section
        for section, count in section_line_counts.items():
            ratio = count / total_lines
            if ratio > LARGE_SECTION_RATIO:
                anomalies.append(AnomalyRecord(
                    type="suspiciously_large_section",
                    section=section,
                    detail=f"{section} owns {ratio:.0%} of document lines",
                    severity="warning",
                ))

        # certifications absorbed too much content
        cert_lines = section_line_counts.get("certifications", 0)
        if cert_lines > MAX_CERT_LINES_EXPECTED:
            anomalies.append(AnomalyRecord(
                type="certifications_absorbed_content",
                section="certifications",
                detail=f"certifications has {cert_lines} lines (expected ≤{MAX_CERT_LINES_EXPECTED})",
                severity="error",
            ))

        # zero transitions (only one section detected = no headers recognized)
        if len(blocks) <= 1:
            anomalies.append(AnomalyRecord(
                type="zero_transitions",
                section="all",
                detail="Only one section block detected — no headers were recognized",
                severity="error",
            ))

        # leadership missing but keywords present in other sections
        if section_line_counts.get("leadership", 0) == 0:
            leadership_keywords = {
                "president", "secretary", "treasurer", "vice president",
                "vp", "head", "coordinator", "organizer", "lead", "chair",
                "volunteer", "nss", "ncc", "mentor", "representative",
            }
            other_content = " ".join(
                e.raw_line.lower() for e in ownership_log
                if e.assigned_section != "leadership"
            )
            import re
            found_keywords = [
                kw for kw in leadership_keywords 
                if re.search(rf"\b{re.escape(kw)}\b", other_content)
            ]
            if found_keywords:
                anomalies.append(AnomalyRecord(
                    type="no_leadership_detected",
                    section="leadership",
                    detail=f"Leadership keywords found in other sections: {found_keywords[:5]}",
                    severity="warning",
                ))

        return anomalies

    @staticmethod
    def _header_result_to_dict(r: HeaderDetectionResult) -> dict:
        return {
            "line_number": r.line_number,
            "original_text": r.original_line,
            "normalized_text": r.normalized_line,
            "canonical_section": r.canonical_section,
            "confidence": round(r.confidence, 4),
            "match_method": r.match_method,
            "combined_sections": r.combined_sections,
            "structural_score": round(r.structural_score, 4),
            "signals_fired": r.signals_fired,
            "normalization_applied": r.normalization.transformations,
            "fuzzy_candidates": [
                {"alias": c.alias, "section": c.canonical_section, "score": round(c.score, 3)}
                for c in r.fuzzy_candidates[:3]
            ],
        }

    @staticmethod
    def _transition_to_dict(t: OwnershipTransition) -> dict:
        return {
            "from_section": t.from_section,
            "to_section": t.to_section,
            "at_line": t.at_line,
            "trigger_line": t.trigger_line,
            "confidence": round(t.confidence, 4),
            "previous_block_line_count": t.previous_block_line_count,
            "reason": t.reason,
        }

    @staticmethod
    def _log_entry_to_dict(e: OwnershipLogEntry) -> dict:
        return {
            "line_number": e.line_number,
            "raw_line": e.raw_line[:120],  # truncate long lines in log
            "assigned_section": e.assigned_section,
            "assignment_reason": e.assignment_reason,
        }


# ── Convenience function ──────────────────────────────────────────────────────

def segment_document(raw_lines: List[str], source_id: str = "") -> OwnershipResult:
    """Segment a document. Convenience wrapper around OwnershipEngine."""
    engine = OwnershipEngine()
    return engine.segment(raw_lines, source_id=source_id)
