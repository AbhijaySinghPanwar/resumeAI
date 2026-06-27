"""
schema.py — Schema v7.0.0 definition, builder, and validator.

Rules:
  - All arrays always exist (never None).
  - All objects always exist (never None).
  - No fields are conditionally present.
  - Schema shape is identical for every document.
  - debug block is always present.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Optional

from resumeai.core.constants import PARSER_VERSION

# ── Empty-state template ──────────────────────────────────────────────────────
# This is the canonical shape of a v7.0.0 parse result.
# No field may be added or removed at runtime.

EMPTY_SCHEMA: Dict[str, Any] = {
    "version": PARSER_VERSION,
    "contact": {
        "name": None,
        "email": None,
        "phone": None,
        "location": None,
        "linkedin": None,
        "github": None,
        "portfolio": None,
        "other_links": [],
    },
    "summary": None,
    "education": [],
    "experience": [],
    "projects": [],
    "leadership": [],
    "certifications": [],
    "open_source": [],
    "achievements": [],
    "publications": [],
    "hackathons": [],
    "research": [],
    "tech_blogs": [],
    "skills": {
        "categories": [],
        "flat_list": [],
        "raw_lines": [],
    },
    "other_section": {
        "blocks": [],
    },
    "metadata": {
        "parse_duration_ms": None,
        "source_file_hash": None,
        "total_lines_processed": None,
        "sections_detected": [],
        "parser_version": PARSER_VERSION,
        "extractor_used": None,
        "anomaly_count": 0,
    },
    "debug": {},
}


def empty_result() -> Dict[str, Any]:
    """Return a fresh, deep-copied empty schema instance."""
    return copy.deepcopy(EMPTY_SCHEMA)


# ── Schema validation ─────────────────────────────────────────────────────────

class SchemaViolation(Exception):
    """Raised when a result violates the schema contract."""
    pass


def validate_result(result: Dict[str, Any]) -> List[str]:
    """
    Validate a parse result against the v7.0.0 schema contract.
    Returns a list of violation messages (empty = valid).
    Does NOT raise — callers decide whether to raise.
    """
    violations: List[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            violations.append(message)

    # Top-level keys
    for key in EMPTY_SCHEMA:
        check(key in result, f"Missing top-level key: {key!r}")

    if "version" in result:
        check(result["version"] == PARSER_VERSION,
              f"Version mismatch: expected {PARSER_VERSION!r}, got {result['version']!r}")

    # Arrays must be lists (never None)
    for array_key in ["education", "experience", "projects", "leadership", "certifications", 
                      "open_source", "achievements", "publications", "hackathons", "research", "tech_blogs"]:
        if array_key in result:
            check(isinstance(result[array_key], list),
                  f"{array_key!r} must be a list, got {type(result[array_key]).__name__}")

    # Contact must be a dict
    if "contact" in result:
        check(isinstance(result["contact"], dict),
              f"contact must be a dict")
        for contact_key in ["name", "email", "phone", "location", "linkedin", "github",
                            "portfolio", "other_links"]:
            check(contact_key in result["contact"],
                  f"contact missing key: {contact_key!r}")
        if "other_links" in result["contact"]:
            check(isinstance(result["contact"]["other_links"], list),
                  "contact.other_links must be a list")

    # Skills must be a dict with required keys
    if "skills" in result:
        check(isinstance(result["skills"], dict), "skills must be a dict")
        for sk in ["categories", "flat_list", "raw_lines"]:
            if isinstance(result.get("skills"), dict):
                check(sk in result["skills"], f"skills missing key: {sk!r}")
                check(isinstance(result["skills"].get(sk), list),
                      f"skills.{sk} must be a list")

    # other_section must have blocks list
    if "other_section" in result:
        check(isinstance(result["other_section"], dict), "other_section must be a dict")
        if isinstance(result["other_section"], dict):
            check("blocks" in result["other_section"], "other_section missing 'blocks'")

    # metadata must be a dict
    if "metadata" in result:
        check(isinstance(result["metadata"], dict), "metadata must be a dict")

    # debug must be a dict (never None)
    if "debug" in result:
        check(isinstance(result["debug"], dict), "debug must be a dict, not None")

    # Validate array item shapes
    if isinstance(result.get("education"), list):
        for i, item in enumerate(result["education"]):
            for field in ["institution", "degree", "field_of_study", "start_date",
                          "end_date", "gpa", "honors", "raw_lines"]:
                check(field in item, f"education[{i}] missing field: {field!r}")

    if isinstance(result.get("experience"), list):
        for i, item in enumerate(result["experience"]):
            for field in ["company", "title", "location", "start_date", "end_date",
                          "is_current", "bullets", "raw_lines"]:
                check(field in item, f"experience[{i}] missing field: {field!r}")

    if isinstance(result.get("certifications"), list):
        for i, item in enumerate(result["certifications"]):
            for field in ["name", "issuer", "date", "expiry", "credential_id", "raw_lines"]:
                check(field in item, f"certifications[{i}] missing field: {field!r}")

    if isinstance(result.get("leadership"), list):
        for i, item in enumerate(result["leadership"]):
            for field in ["organization", "role", "start_date", "end_date",
                          "bullets", "raw_lines"]:
                check(field in item, f"leadership[{i}] missing field: {field!r}")

    return violations


def assert_valid(result: Dict[str, Any]) -> None:
    """Validate and raise SchemaViolation if any violations found."""
    violations = validate_result(result)
    if violations:
        raise SchemaViolation(
            f"Schema contract violated ({len(violations)} violations):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


def to_json(result: Dict[str, Any], indent: int = 2, strip_debug: bool = False) -> str:
    """Serialize a result to JSON. Optionally strip the debug block."""
    output = result if not strip_debug else {k: v for k, v in result.items() if k != "debug"}
    return json.dumps(output, indent=indent, ensure_ascii=False, default=str)
