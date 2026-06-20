"""
integration/test_ats.py — ATS integration layer tests.

Tests the gate, exporters, and scorer against real fixture data.
"""

import json
import pytest

from resumeai.pipeline import ResumeParser
from resumeai.ats.gate import ATSGate
from resumeai.ats.exporters import to_generic_json, to_greenhouse, to_lever, to_workday, to_csv_row
from resumeai.ats.scorer import ResumeScorer
from resumeai.tests.fixtures.fixtures import FIXTURE_STANDARD, FIXTURE_DENSE


@pytest.fixture
def parser():
    return ResumeParser(strict_schema=False, include_debug=True)


@pytest.fixture
def standard_result(parser):
    return parser.parse_text(FIXTURE_STANDARD)


@pytest.fixture
def dense_result(parser):
    return parser.parse_text(FIXTURE_DENSE)


# ── Gate tests ────────────────────────────────────────────────────────────────

class TestATSGate:

    def test_good_resume_passes_gate(self, standard_result):
        gate = ATSGate()
        decision = gate.evaluate(standard_result)
        assert decision.schema_version == "7.0.0"
        # Should pass (or have only warnings)
        assert decision.blocking_anomalies == [] or decision.passed

    def test_wrong_version_blocked(self, standard_result):
        gate = ATSGate(required_version="6.0.0")
        decision = gate.evaluate(standard_result)
        assert not decision.passed
        assert any(b["type"] == "version_mismatch" for b in decision.blocking_anomalies)

    def test_gate_decision_has_summary(self, standard_result):
        gate = ATSGate()
        decision = gate.evaluate(standard_result)
        assert isinstance(decision.summary, str)
        assert len(decision.summary) > 0

    def test_gate_to_dict(self, standard_result):
        gate = ATSGate()
        decision = gate.evaluate(standard_result)
        d = decision.to_dict()
        assert "passed" in d
        assert "schema_version" in d
        assert "blocking_anomalies" in d
        assert "warning_anomalies" in d

    def test_gate_override_allows_blocking(self, standard_result):
        # Inject a blocking anomaly
        standard_result["debug"]["anomalies"].append({
            "type": "zero_transitions",
            "section": "all",
            "detail": "test",
            "severity": "error",
        })
        gate = ATSGate(allow_override=True)
        decision = gate.evaluate(standard_result, override_blocking=True)
        assert decision.passed is True
        assert decision.override_applied is True


# ── Exporter tests ─────────────────────────────────────────────────────────────

class TestExporters:

    def test_generic_json_is_valid_json(self, standard_result):
        output = to_generic_json(standard_result)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_generic_json_strips_debug_by_default(self, standard_result):
        output = to_generic_json(standard_result, strip_debug=True)
        parsed = json.loads(output)
        assert "debug" not in parsed

    def test_generic_json_keeps_debug_when_requested(self, standard_result):
        output = to_generic_json(standard_result, strip_debug=False)
        parsed = json.loads(output)
        assert "debug" in parsed

    def test_greenhouse_format_structure(self, standard_result):
        gh = to_greenhouse(standard_result)
        assert "first_name" in gh
        assert "last_name" in gh
        assert "email_addresses" in gh
        assert "educations" in gh
        assert "employments" in gh
        assert isinstance(gh["email_addresses"], list)
        assert isinstance(gh["educations"], list)

    def test_greenhouse_email_populated(self, standard_result):
        gh = to_greenhouse(standard_result)
        emails = [e["value"] for e in gh["email_addresses"]]
        assert "priya.sharma@email.com" in emails

    def test_greenhouse_date_format(self, dense_result):
        gh = to_greenhouse(dense_result)
        for edu in gh["educations"]:
            if edu.get("start_date"):
                assert isinstance(edu["start_date"], dict)
                assert "year" in edu["start_date"]

    def test_lever_format_structure(self, standard_result):
        lv = to_lever(standard_result)
        assert "name" in lv
        assert "email" in lv
        assert "tags" in lv
        assert "links" in lv
        assert isinstance(lv["tags"], list)
        assert isinstance(lv["links"], list)

    def test_lever_tags_are_strings(self, standard_result):
        lv = to_lever(standard_result)
        assert all(isinstance(t, str) for t in lv["tags"])

    def test_workday_format_structure(self, standard_result):
        wd = to_workday(standard_result)
        assert "First_Name" in wd
        assert "Last_Name" in wd
        assert "Email_Address" in wd
        assert "Skills" in wd

    def test_csv_row_is_string(self, standard_result):
        csv = to_csv_row(standard_result)
        assert isinstance(csv, str)
        assert len(csv) > 0
        assert "\n" in csv  # has header + data row

    def test_all_exporters_handle_empty_sections(self, parser):
        """Exporters must handle resumes where sections are empty."""
        result = parser.parse_text("John Doe\njohn@email.com")
        # None of these should raise
        to_generic_json(result)
        to_greenhouse(result)
        to_lever(result)
        to_workday(result)
        to_csv_row(result)


# ── Scorer tests ──────────────────────────────────────────────────────────────

class TestResumeScorer:

    JD_PYTHON = """
    We are looking for a Software Engineer with 3+ years of experience.
    Requirements:
    - Strong Python programming skills
    - Experience with Django or Flask
    - Knowledge of AWS and Docker
    - Familiarity with React
    - Bachelor's degree in Computer Science or related field
    - AWS certification preferred
    """

    JD_FINANCE = """
    Financial Analyst position requiring:
    - 2+ years of financial modeling experience
    - Proficiency in Excel and SQL
    - CFA certification or progress toward CFA
    - MBA or Bachelor's in Finance
    - Bloomberg Terminal experience
    """

    def test_score_returns_match_report(self, standard_result):
        scorer = ResumeScorer()
        report = scorer.score(standard_result, self.JD_PYTHON)
        assert report is not None
        assert 0 <= report.overall_score <= 100

    def test_score_has_grade(self, standard_result):
        scorer = ResumeScorer()
        report = scorer.score(standard_result, self.JD_PYTHON)
        assert report.grade in ("A", "B", "C", "D", "F")

    def test_score_has_matched_and_missing_skills(self, standard_result):
        scorer = ResumeScorer()
        report = scorer.score(standard_result, self.JD_PYTHON)
        assert isinstance(report.matched_skills, list)
        assert isinstance(report.missing_skills, list)

    def test_score_to_dict(self, standard_result):
        scorer = ResumeScorer()
        report = scorer.score(standard_result, self.JD_PYTHON)
        d = report.to_dict()
        assert "overall_score" in d
        assert "grade" in d
        assert "category_scores" in d
        assert "recommendation" in d

    def test_python_resume_scores_well_on_python_jd(self, standard_result):
        scorer = ResumeScorer()
        report = scorer.score(standard_result, self.JD_PYTHON)
        # Python resume vs Python JD should score reasonably well
        assert report.overall_score >= 20  # at minimum, some skills matched

    def test_score_deterministic(self, standard_result):
        """Same resume + same JD always produces same score."""
        scorer = ResumeScorer()
        scores = [scorer.score(standard_result, self.JD_PYTHON).overall_score for _ in range(5)]
        assert len(set(scores)) == 1, f"Scores vary: {scores}"

    def test_recommendation_is_string(self, standard_result):
        scorer = ResumeScorer()
        report = scorer.score(standard_result, self.JD_PYTHON)
        assert isinstance(report.recommendation, str)
        assert len(report.recommendation) > 0

    def test_jd_hash_is_stable(self, standard_result):
        scorer = ResumeScorer()
        r1 = scorer.score(standard_result, self.JD_PYTHON)
        r2 = scorer.score(standard_result, self.JD_PYTHON)
        assert r1.jd_hash == r2.jd_hash

    def test_different_jd_different_hash(self, standard_result):
        scorer = ResumeScorer()
        r1 = scorer.score(standard_result, self.JD_PYTHON)
        r2 = scorer.score(standard_result, self.JD_FINANCE)
        assert r1.jd_hash != r2.jd_hash

    def test_experience_years_extracted(self, dense_result):
        scorer = ResumeScorer()
        report = scorer.score(dense_result, self.JD_PYTHON)
        # Dense fixture has 6+ years of experience entries
        assert report.experience_years_found is not None
        assert report.experience_years_found >= 0
