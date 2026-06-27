"""
pipeline.py — Main orchestration pipeline for ResumeAI v7.0.0.

Phases:
  Phase 1: Section ownership engine + debug layer
  Phase 2: Field-level extraction per section
  Phase 3: Schema assembly + validation
  Phase 4: ATS metadata attachment
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from resumeai.core.constants import PARSER_VERSION
from resumeai.core.ownership_engine import OwnershipResult, segment_document
from resumeai.core.pdf_extractor import ExtractionResult, extract_text_from_pdf, extract_text_from_string
from resumeai.core.schema import assert_valid, empty_result, validate_result

from resumeai.extractors.contact import extract_contact
from resumeai.extractors.education import extract_education
from resumeai.extractors.experience import extract_experience
from resumeai.extractors.projects import extract_projects
from resumeai.extractors.leadership import extract_leadership
from resumeai.extractors.certifications import extract_certifications
from resumeai.extractors.skills import extract_skills
from resumeai.extractors.summary import extract_summary


class ParseError(Exception):
    """Raised when parsing cannot proceed at all (e.g. empty document)."""
    pass


class ResumeParser:
    """
    Deterministic resume parser.

    Usage:
        parser = ResumeParser()
        result = parser.parse_pdf("resume.pdf")
        result = parser.parse_text("raw resume text...")
        result = parser.parse_lines(["line1", "line2", ...])
    """

    def __init__(
        self,
        strict_schema: bool = True,
        include_debug: bool = True,
        include_raw_lines: bool = True,
    ):
        """
        Args:
            strict_schema: Raise SchemaViolation if output fails validation.
            include_debug: Include the debug block in output.
            include_raw_lines: Include raw_lines in each extracted entry.
        """
        self.strict_schema = strict_schema
        self.include_debug = include_debug
        self.include_raw_lines = include_raw_lines

    # ── Public API ────────────────────────────────────────────────────────────

    def parse_pdf(self, source: Union[str, Path, bytes]) -> Dict[str, Any]:
        """Parse a PDF file and return a v7.0.0 schema result."""
        extraction = extract_text_from_pdf(source)
        source_id = self._source_id(source)
        return self._run_pipeline(extraction, source_id)

    def parse_text(self, text: str, source_id: str = "") -> Dict[str, Any]:
        """Parse plain text (already extracted) and return a v7.0.0 schema result."""
        extraction = extract_text_from_string(text)
        return self._run_pipeline(extraction, source_id or "plaintext")

    def parse_lines(self, lines: List[str], source_id: str = "") -> Dict[str, Any]:
        """Parse a pre-split list of lines and return a v7.0.0 schema result."""
        extraction = ExtractionResult(
            raw_lines=lines,
            page_count=1,
            extractor_used="raw_lines",
        )
        return self._run_pipeline(extraction, source_id or "raw_lines")

    # ── Pipeline orchestration ────────────────────────────────────────────────

    def _run_pipeline(
        self, extraction: ExtractionResult, source_id: str
    ) -> Dict[str, Any]:

        start_time = time.monotonic()

        if not extraction.succeeded and extraction.error:
            raise ParseError(f"Text extraction failed: {extraction.error}")

        raw_lines = extraction.raw_lines

        # ── Phase 1: Section Ownership ────────────────────────────────────────
        ownership: OwnershipResult = segment_document(raw_lines, source_id=source_id)

        # Verify structural invariants — must pass before extraction
        invariant_violations = ownership.verify_invariants()
        if invariant_violations:
            # Log but don't abort — partial results are better than no results
            pass

        # ── Phase 2: Field Extraction ─────────────────────────────────────────
        result = empty_result()

        contact_lines = ownership.all_lines_for_section("contact")
        # Add global_links to contact lines
        contact_lines.extend(extraction.global_links)
        
        contact_data = self._safe_extract(
            "contact",
            extract_contact,
            contact_lines,
            default=result["contact"],
        )

        # Fallback to entire document if critical fields are missing
        if not contact_data.get("email") or not contact_data.get("phone"):
            fallback_lines = raw_lines + extraction.global_links
            fallback_data = self._safe_extract(
                "contact_fallback",
                extract_contact,
                fallback_lines,
                default={},
            )
            # Merge fallback data into contact_data
            for k, v in fallback_data.items():
                if v and not contact_data.get(k):
                    if isinstance(v, list) and isinstance(contact_data.get(k), list):
                        contact_data[k].extend(x for x in v if x not in contact_data[k])
                    else:
                        contact_data[k] = v
                        
        result["contact"] = contact_data

        result["summary"] = self._safe_extract(
            "summary",
            extract_summary,
            ownership.all_lines_for_section("summary"),
            default=None,
        )

        result["education"] = self._safe_extract(
            "education",
            extract_education,
            ownership.all_lines_for_section("education"),
            default=[],
        )

        result["experience"] = self._safe_extract(
            "experience",
            extract_experience,
            ownership.all_lines_for_section("experience"),
            default=[],
        )

        result["projects"] = self._safe_extract(
            "projects",
            extract_projects,
            ownership.all_lines_for_section("projects"),
            default=[],
        )

        result["leadership"] = self._safe_extract(
            "leadership",
            extract_leadership,
            ownership.all_lines_for_section("leadership"),
            default=[],
        )

        result["certifications"] = self._safe_extract(
            "certifications",
            extract_certifications,
            ownership.all_lines_for_section("certifications"),
            default=[],
        )
        
        result["open_source"] = self._safe_extract(
            "open_source",
            extract_projects,
            ownership.all_lines_for_section("open_source"),
            default=[],
        )
        
        result["achievements"] = self._safe_extract(
            "achievements",
            extract_leadership,
            ownership.all_lines_for_section("achievements"),
            default=[],
        )
        
        result["publications"] = self._safe_extract(
            "publications",
            extract_leadership,
            ownership.all_lines_for_section("publications"),
            default=[],
        )
        
        result["hackathons"] = self._safe_extract(
            "hackathons",
            extract_projects,
            ownership.all_lines_for_section("hackathons"),
            default=[],
        )
        
        result["research"] = self._safe_extract(
            "research",
            extract_projects,
            ownership.all_lines_for_section("research"),
            default=[],
        )
        
        result["tech_blogs"] = self._safe_extract(
            "tech_blogs",
            extract_projects,
            ownership.all_lines_for_section("tech_blogs"),
            default=[],
        )

        result["skills"] = self._safe_extract(
            "skills",
            extract_skills,
            ownership.all_lines_for_section("skills"),
            default=result["skills"],
        )

        # other_section: aggregate all other_section blocks
        other_blocks = []
        for block in ownership.blocks_by_section("other_section"):
            other_blocks.append({
                "header_line": block.header_line,
                "raw_lines": block.raw_lines,
            })
        result["other_section"]["blocks"] = other_blocks

        # ── Phase 3: Metadata + Debug ─────────────────────────────────────────
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        sections_detected = list({
            b.section_name for b in ownership.blocks
            if b.section_name != "other_section"
        })

        source_hash = hashlib.sha256(
            "\n".join(raw_lines).encode()
        ).hexdigest()[:16]

        result["metadata"] = {
            "parse_duration_ms": elapsed_ms,
            "source_file_hash": source_hash,
            "total_lines_processed": ownership.total_lines,
            "sections_detected": sorted(sections_detected),
            "parser_version": PARSER_VERSION,
            "extractor_used": extraction.extractor_used,
            "anomaly_count": len(ownership.debug.anomalies),
            "invariant_violations": invariant_violations,
            "extraction_warnings": extraction.warnings,
        }

        if self.include_debug:
            result["debug"] = ownership.debug.to_dict()
        else:
            result["debug"] = {}

        # ── Phase 3: Schema Validation ────────────────────────────────────────
        violations = validate_result(result)
        if violations:
            result["metadata"]["schema_violations"] = violations
            if self.strict_schema:
                assert_valid(result)

        # Strip raw_lines from entries if not requested (must happen after validation)
        if not self.include_raw_lines:
            result = self._strip_raw_lines(result)

        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _safe_extract(section: str, extractor, lines: List[str], default: Any) -> Any:
        """
        Call an extractor with error isolation.
        If the extractor raises, return the default value and log the error.
        Extractors must NEVER corrupt other sections — isolation is enforced here.
        """
        if not lines:
            return default
        try:
            return extractor(lines)
        except Exception as exc:
            # Never propagate extractor errors — return safe default
            # In production, this would be logged to an error tracking system
            return default

    @staticmethod
    def _source_id(source: Union[str, Path, bytes]) -> str:
        if isinstance(source, bytes):
            return hashlib.sha256(source).hexdigest()[:12]
        return str(source)

    @staticmethod
    def _strip_raw_lines(result: Dict[str, Any]) -> Dict[str, Any]:
        """Remove raw_lines from all entries for cleaner API output."""
        for section in ["education", "experience", "projects", "leadership", "certifications"]:
            if isinstance(result.get(section), list):
                for entry in result[section]:
                    entry.pop("raw_lines", None)
        if isinstance(result.get("skills"), dict):
            result["skills"].pop("raw_lines", None)
        return result


# ── Module-level convenience function ────────────────────────────────────────

_default_parser = None


def parse_resume(
    source: Union[str, Path, bytes, List[str]],
    source_type: str = "auto",
    include_debug: bool = True,
) -> Dict[str, Any]:
    """
    Convenience function for one-shot parsing.

    Args:
        source: PDF path/bytes, plain text string, or list of lines.
        source_type: "pdf" | "text" | "lines" | "auto" (auto-detects).
        include_debug: Include debug block in output.

    Returns:
        v7.0.0 schema dict.
    """
    parser = ResumeParser(include_debug=include_debug)

    if source_type == "auto":
        if isinstance(source, list):
            source_type = "lines"
        elif isinstance(source, bytes):
            source_type = "pdf"
        elif isinstance(source, (str, Path)) and str(source).endswith(".pdf"):
            source_type = "pdf"
        else:
            source_type = "text"

    if source_type == "pdf":
        return parser.parse_pdf(source)
    elif source_type == "lines":
        return parser.parse_lines(source)
    else:
        return parser.parse_text(str(source))
