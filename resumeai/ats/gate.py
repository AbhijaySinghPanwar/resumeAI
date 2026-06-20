"""
ats/gate.py — Version enforcement and anomaly gating.

Every parse result must pass through the gate before ATS submission.
The gate enforces:
  1. Schema version is exactly PARSER_VERSION.
  2. No CRITICAL anomalies are present (unless overridden).
  3. Minimum data quality thresholds are met.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from resumeai.core.constants import PARSER_VERSION

# Anomaly types that block ATS submission by default
BLOCKING_ANOMALY_TYPES = {
    "zero_transitions",           # Parser found no section headers at all
    "certifications_absorbed_content",  # Certifications bled into other content
}

# Anomaly types that warn but don't block
WARNING_ANOMALY_TYPES = {
    "empty_section",
    "suspiciously_large_section",
    "no_leadership_detected",
    "education_missing",
}


@dataclass
class GateDecision:
    passed: bool
    schema_version: str
    blocking_anomalies: List[dict] = field(default_factory=list)
    warning_anomalies: List[dict] = field(default_factory=list)
    quality_flags: List[str] = field(default_factory=list)
    override_applied: bool = False

    @property
    def summary(self) -> str:
        if self.passed:
            status = "PASSED"
            if self.warning_anomalies:
                status += f" (with {len(self.warning_anomalies)} warning(s))"
        else:
            status = f"BLOCKED — {len(self.blocking_anomalies)} critical anomaly(ies)"
        return status

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "schema_version": self.schema_version,
            "blocking_anomalies": self.blocking_anomalies,
            "warning_anomalies": self.warning_anomalies,
            "quality_flags": self.quality_flags,
            "override_applied": self.override_applied,
            "summary": self.summary,
        }


class ATSGate:
    """
    Enforces version and quality requirements before ATS submission.

    Usage:
        gate = ATSGate()
        decision = gate.evaluate(parse_result)
        if decision.passed:
            ...submit...
    """

    def __init__(
        self,
        required_version: str = PARSER_VERSION,
        allow_override: bool = False,
        min_sections: int = 2,
    ):
        self.required_version = required_version
        self.allow_override = allow_override
        self.min_sections = min_sections

    def evaluate(
        self,
        result: Dict[str, Any],
        override_blocking: bool = False,
    ) -> GateDecision:
        """
        Evaluate a parse result and return a gate decision.

        Args:
            result: v7.0.0 parse result dict.
            override_blocking: If True and allow_override is True,
                               blocking anomalies are downgraded to warnings.
        """
        version = result.get("version", "unknown")
        blocking = []
        warnings_list = []
        quality_flags = []

        # ── Version check ─────────────────────────────────────────────────────
        if version != self.required_version:
            blocking.append({
                "type": "version_mismatch",
                "detail": f"Expected {self.required_version}, got {version}",
                "severity": "error",
            })

        # ── Anomaly classification ────────────────────────────────────────────
        debug = result.get("debug", {})
        anomalies = debug.get("anomalies", [])

        for anomaly in anomalies:
            atype = anomaly.get("type", "")
            if atype in BLOCKING_ANOMALY_TYPES:
                blocking.append(anomaly)
            elif atype in WARNING_ANOMALY_TYPES:
                warnings_list.append(anomaly)
            else:
                warnings_list.append(anomaly)

        # ── Quality thresholds ────────────────────────────────────────────────
        metadata = result.get("metadata", {})
        sections_detected = metadata.get("sections_detected", [])

        if len(sections_detected) < self.min_sections:
            quality_flags.append(
                f"Only {len(sections_detected)} section(s) detected "
                f"(minimum: {self.min_sections})"
            )

        contact = result.get("contact", {})
        if not contact.get("name"):
            quality_flags.append("Contact name not detected")
        if not contact.get("email"):
            quality_flags.append("Contact email not detected")

        if not result.get("experience") and not result.get("education"):
            quality_flags.append("Neither experience nor education extracted")
            blocking.append({
                "type": "insufficient_data",
                "detail": "Resume has no experience and no education content",
                "severity": "error",
            })

        # Schema violations logged in metadata
        schema_violations = metadata.get("schema_violations", [])
        if schema_violations:
            blocking.append({
                "type": "schema_violations",
                "detail": f"{len(schema_violations)} schema violation(s): {schema_violations[:3]}",
                "severity": "error",
            })

        # ── Override logic ────────────────────────────────────────────────────
        override_applied = False
        if blocking and override_blocking and self.allow_override:
            warnings_list.extend(blocking)
            blocking = []
            override_applied = True

        passed = len(blocking) == 0

        return GateDecision(
            passed=passed,
            schema_version=version,
            blocking_anomalies=blocking,
            warning_anomalies=warnings_list,
            quality_flags=quality_flags,
            override_applied=override_applied,
        )
