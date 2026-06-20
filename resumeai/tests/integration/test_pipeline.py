"""
integration/test_pipeline.py — End-to-end pipeline integration tests.

These tests exercise the full pipeline: text → ownership → extraction → schema.
They verify both structural correctness and content accuracy against ground truth.

Why these tests matter:
  The previous test suite tested the parser against known-good inputs.
  These tests start from the ground truth and verify the parser reaches it.
"""

import pytest
from resumeai.pipeline import ResumeParser, parse_resume
from resumeai.core.schema import validate_result, EMPTY_SCHEMA
from resumeai.tests.fixtures.fixtures import (
    ALL_FIXTURES,
    FIXTURE_STANDARD, FIXTURE_STANDARD_GROUND_TRUTH,
    FIXTURE_COMBINED_HEADER, FIXTURE_COMBINED_HEADER_GROUND_TRUTH,
    FIXTURE_YEAR_PREFIX_EDUCATION, FIXTURE_YEAR_PREFIX_EDUCATION_GROUND_TRUTH,
    FIXTURE_CERT_THEN_LEADERSHIP, FIXTURE_CERT_THEN_LEADERSHIP_GROUND_TRUTH,
    FIXTURE_PDF_ARTIFACTS, FIXTURE_PDF_ARTIFACTS_GROUND_TRUTH,
    FIXTURE_NO_HEADERS, FIXTURE_NO_HEADERS_GROUND_TRUTH,
    FIXTURE_DENSE, FIXTURE_DENSE_GROUND_TRUTH,
)


@pytest.fixture
def parser():
    return ResumeParser(strict_schema=True, include_debug=True)


# ── Schema contract tests ─────────────────────────────────────────────────────

class TestSchemaContract:
    """
    Every parse result must satisfy the schema contract exactly.
    No missing keys. No wrong types. No missing arrays.
    """

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=[f["name"] for f in ALL_FIXTURES])
    def test_schema_valid_for_all_fixtures(self, parser, fixture):
        result = parser.parse_text(fixture["text"])
        violations = validate_result(result)
        assert violations == [], (
            f"Fixture '{fixture['name']}' failed schema validation:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=[f["name"] for f in ALL_FIXTURES])
    def test_all_array_fields_are_lists(self, parser, fixture):
        """Arrays must never be None."""
        result = parser.parse_text(fixture["text"])
        for key in ["education", "experience", "projects", "leadership", "certifications"]:
            assert isinstance(result[key], list), (
                f"Fixture '{fixture['name']}': {key!r} is {type(result[key]).__name__}, not list"
            )

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=[f["name"] for f in ALL_FIXTURES])
    def test_version_field_present_and_correct(self, parser, fixture):
        result = parser.parse_text(fixture["text"])
        assert result["version"] == "7.0.0"

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=[f["name"] for f in ALL_FIXTURES])
    def test_debug_block_always_present(self, parser, fixture):
        result = parser.parse_text(fixture["text"])
        assert isinstance(result["debug"], dict)
        assert "ownership_log" in result["debug"]
        assert "section_transitions" in result["debug"]
        assert "anomalies" in result["debug"]

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=[f["name"] for f in ALL_FIXTURES])
    def test_metadata_always_present(self, parser, fixture):
        result = parser.parse_text(fixture["text"])
        meta = result["metadata"]
        assert isinstance(meta, dict)
        assert "parse_duration_ms" in meta
        assert "total_lines_processed" in meta
        assert "sections_detected" in meta


# ── Ground truth verification tests ──────────────────────────────────────────

class TestGroundTruth:
    """
    Verify extracted content against manually-curated ground truth.
    These are the tests that would have caught the production failures.
    """

    def test_standard_resume_contact(self, parser):
        result = parser.parse_text(FIXTURE_STANDARD)
        truth = FIXTURE_STANDARD_GROUND_TRUTH
        assert result["contact"]["name"] == truth["contact"]["name"]
        assert result["contact"]["email"] == truth["contact"]["email"]

    def test_standard_resume_education_count(self, parser):
        result = parser.parse_text(FIXTURE_STANDARD)
        assert len(result["education"]) == FIXTURE_STANDARD_GROUND_TRUTH["education_count"]

    def test_standard_resume_experience_count(self, parser):
        result = parser.parse_text(FIXTURE_STANDARD)
        assert len(result["experience"]) == FIXTURE_STANDARD_GROUND_TRUTH["experience_count"]

    def test_standard_resume_certifications_count(self, parser):
        result = parser.parse_text(FIXTURE_STANDARD)
        truth_count = FIXTURE_STANDARD_GROUND_TRUTH["certifications_count"]
        assert len(result["certifications"]) == truth_count

    def test_standard_resume_leadership_count(self, parser):
        result = parser.parse_text(FIXTURE_STANDARD)
        assert len(result["leadership"]) == FIXTURE_STANDARD_GROUND_TRUTH["leadership_count"]

    def test_standard_resume_skills_not_empty(self, parser):
        result = parser.parse_text(FIXTURE_STANDARD)
        skills = result["skills"]
        has_skills = len(skills["flat_list"]) > 0 or len(skills["categories"]) > 0
        assert has_skills


class TestCombinedHeaderFixture:
    """
    The combined header fixture is the primary regression test for
    'leadership disappears into other_section'.
    """

    def test_leadership_not_empty(self, parser):
        result = parser.parse_text(FIXTURE_COMBINED_HEADER)
        assert len(result["leadership"]) >= FIXTURE_COMBINED_HEADER_GROUND_TRUTH["leadership_count_min"], (
            "Leadership is empty — 'Positions of Responsibility / Extracurriculars' "
            "was not recognized"
        )

    def test_certifications_do_not_contain_leadership_content(self, parser):
        result = parser.parse_text(FIXTURE_COMBINED_HEADER)
        cert_text = " ".join(
            str(c) for cert in result["certifications"]
            for c in cert.values() if c
        ).lower()
        assert "vice president" not in cert_text, (
            "Certifications absorbed 'Vice President' from leadership section"
        )
        assert "nss" not in cert_text, (
            "Certifications absorbed NSS from leadership section"
        )

    def test_leadership_keywords_present(self, parser):
        result = parser.parse_text(FIXTURE_COMBINED_HEADER)
        leadership_text = " ".join(
            " ".join(e.get("raw_lines", []))
            for e in result["leadership"]
        )
        # At least one leadership keyword should appear in leadership section
        keywords = FIXTURE_COMBINED_HEADER_GROUND_TRUTH["leadership_keywords"]
        found = any(kw.lower() in leadership_text.lower() for kw in keywords)
        assert found, (
            f"None of {keywords} found in leadership section content. "
            f"Leadership text: {leadership_text[:200]!r}"
        )


class TestYearPrefixEducation:
    """
    Tests for year-prefixed education lines.
    '2019 – 2023   B.Tech, Computer Science' must extract correctly.
    """

    def test_education_count(self, parser):
        result = parser.parse_text(FIXTURE_YEAR_PREFIX_EDUCATION)
        truth = FIXTURE_YEAR_PREFIX_EDUCATION_GROUND_TRUTH
        assert len(result["education"]) == truth["education_count"], (
            f"Expected {truth['education_count']} education entries, "
            f"got {len(result['education'])}"
        )

    def test_education_has_start_date(self, parser):
        result = parser.parse_text(FIXTURE_YEAR_PREFIX_EDUCATION)
        if result["education"]:
            first = result["education"][0]
            assert first.get("start_date") is not None, (
                "First education entry has no start_date — year prefix not parsed"
            )

    def test_education_start_year_correct(self, parser):
        result = parser.parse_text(FIXTURE_YEAR_PREFIX_EDUCATION)
        if result["education"]:
            first = result["education"][0]
            start = first.get("start_date", "")
            assert "2019" in str(start), (
                f"Expected start year 2019, got {start!r}"
            )


class TestCertThenLeadership:
    """
    THE critical regression test.
    Certifications followed immediately by leadership must not cause bleeding.
    """

    def test_certifications_count_correct(self, parser):
        result = parser.parse_text(FIXTURE_CERT_THEN_LEADERSHIP)
        truth = FIXTURE_CERT_THEN_LEADERSHIP_GROUND_TRUTH
        assert len(result["certifications"]) == truth["certifications_count"], (
            f"Expected {truth['certifications_count']} certs, got {len(result['certifications'])}"
        )

    def test_leadership_not_empty(self, parser):
        result = parser.parse_text(FIXTURE_CERT_THEN_LEADERSHIP)
        assert len(result["leadership"]) >= FIXTURE_CERT_THEN_LEADERSHIP_GROUND_TRUTH["leadership_count_min"], (
            "Leadership section is empty after certifications — bleeding detected"
        )

    def test_certifications_block_reasonable_size(self, parser):
        """Certifications block that is too large indicates bleeding."""
        result = parser.parse_text(FIXTURE_CERT_THEN_LEADERSHIP)
        debug = result["debug"]
        summary = debug.get("section_summary", {})
        cert_lines = summary.get("certifications", {}).get("total_lines", 0)
        max_lines = FIXTURE_CERT_THEN_LEADERSHIP_GROUND_TRUTH["certifications_line_count_max"]
        assert cert_lines <= max_lines, (
            f"Certifications has {cert_lines} lines (max: {max_lines}) — "
            f"leadership content may have bled into certifications"
        )

    def test_no_certifications_absorbed_content_anomaly(self, parser):
        result = parser.parse_text(FIXTURE_CERT_THEN_LEADERSHIP)
        anomalies = result["debug"].get("anomalies", [])
        cert_anomalies = [a for a in anomalies if a.get("type") == "certifications_absorbed_content"]
        assert cert_anomalies == [], (
            f"certifications_absorbed_content anomaly fired: {cert_anomalies}"
        )


class TestPDFArtifacts:
    """
    Tests for PDF extraction artifacts (spaced chars, Unicode dashes).
    The normalizer must handle these before section detection.
    """

    def test_education_not_empty_despite_spaced_header(self, parser):
        result = parser.parse_text(FIXTURE_PDF_ARTIFACTS)
        assert len(result["education"]) > 0 or result["debug"]["section_summary"].get("education", {}).get("total_lines", 0) > 0, (
            "Education is empty — 'E d u c a t i o n' header not recognized"
        )

    def test_experience_not_empty_despite_spaced_header(self, parser):
        result = parser.parse_text(FIXTURE_PDF_ARTIFACTS)
        exp_lines = result["debug"]["section_summary"].get("experience", {}).get("total_lines", 0)
        assert exp_lines > 0 or len(result["experience"]) > 0, (
            "Experience is empty — spaced header not normalized"
        )

    def test_leadership_not_empty_despite_spaced_header(self, parser):
        result = parser.parse_text(FIXTURE_PDF_ARTIFACTS)
        debug_summary = result["debug"]["section_summary"]
        leadership_lines = debug_summary.get("leadership", {}).get("total_lines", 0)
        assert leadership_lines > 0 or len(result["leadership"]) > 0, (
            "Leadership is empty — spaced 'L e a d e r s h i p' header not normalized"
        )


class TestNoHeaders:
    """
    Graceful handling when a resume has no recognizable section headers.
    Must not crash. Must still extract contact info.
    """

    def test_no_crash_on_headerless_resume(self, parser):
        result = parser.parse_text(FIXTURE_NO_HEADERS)
        assert result is not None

    def test_schema_still_valid_for_headerless_resume(self, parser):
        result = parser.parse_text(FIXTURE_NO_HEADERS)
        violations = validate_result(result)
        assert violations == []

    def test_all_arrays_present_even_when_empty(self, parser):
        result = parser.parse_text(FIXTURE_NO_HEADERS)
        for key in ["education", "experience", "projects", "leadership", "certifications"]:
            assert isinstance(result[key], list), f"{key} must be a list, not {type(result[key])}"


class TestDenseResume:
    """Tests for a fully-populated resume with all sections."""

    def test_dense_contact_name(self, parser):
        result = parser.parse_text(FIXTURE_DENSE)
        assert result["contact"]["name"] == FIXTURE_DENSE_GROUND_TRUTH["contact_name"]

    def test_dense_contact_email(self, parser):
        result = parser.parse_text(FIXTURE_DENSE)
        assert result["contact"]["email"] == FIXTURE_DENSE_GROUND_TRUTH["contact_email"]

    def test_dense_education_count(self, parser):
        result = parser.parse_text(FIXTURE_DENSE)
        assert len(result["education"]) == FIXTURE_DENSE_GROUND_TRUTH["education_count"]

    def test_dense_experience_count(self, parser):
        result = parser.parse_text(FIXTURE_DENSE)
        assert len(result["experience"]) == FIXTURE_DENSE_GROUND_TRUTH["experience_count"]

    def test_dense_certifications_count(self, parser):
        result = parser.parse_text(FIXTURE_DENSE)
        assert len(result["certifications"]) == FIXTURE_DENSE_GROUND_TRUTH["certifications_count"]

    def test_dense_leadership_present(self, parser):
        result = parser.parse_text(FIXTURE_DENSE)
        assert len(result["leadership"]) >= FIXTURE_DENSE_GROUND_TRUTH["leadership_count_min"]

    def test_dense_projects_present(self, parser):
        result = parser.parse_text(FIXTURE_DENSE)
        assert len(result["projects"]) >= FIXTURE_DENSE_GROUND_TRUTH["projects_count_min"]


# ── Determinism tests ─────────────────────────────────────────────────────────

class TestFullPipelineDeterminism:
    """
    Full pipeline determinism: same text → byte-identical JSON output.
    Excludes: parse_timestamp, parse_duration_ms (intentionally variable).
    """

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=[f["name"] for f in ALL_FIXTURES])
    def test_deterministic_schema_output(self, parser, fixture):
        import json

        def normalize_for_comparison(result: dict) -> dict:
            """Remove intentionally-variable fields before comparison."""
            import copy
            r = copy.deepcopy(result)
            r.get("metadata", {}).pop("parse_duration_ms", None)
            r.get("debug", {}).pop("parse_timestamp", None)
            return r

        results = [parser.parse_text(fixture["text"]) for _ in range(3)]
        normalized = [normalize_for_comparison(r) for r in results]

        first_json = json.dumps(normalized[0], sort_keys=True, default=str)
        for i, n in enumerate(normalized[1:], 2):
            run_json = json.dumps(n, sort_keys=True, default=str)
            assert run_json == first_json, (
                f"Fixture '{fixture['name']}': Run {i} produced different output than run 1"
            )
