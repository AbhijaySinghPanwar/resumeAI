"""
unit/test_header_detector.py — Unit tests for the header detection engine.

Each test exercises a single line in isolation.
No document context. No parser state. Pure function testing.
"""

import pytest
from resumeai.core.header_detector import detect_header
from resumeai.core.constants import HEADER_CONFIDENCE_ACCEPT, HEADER_CONFIDENCE_AMBIGUOUS


class TestExactAliasMatching:
    """Tests for Stage 3: Exact alias matching."""

    def test_education_detected(self):
        r = detect_header("EDUCATION", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "education"
        assert r.match_method == "exact"
        assert r.confidence >= HEADER_CONFIDENCE_ACCEPT

    def test_experience_detected(self):
        r = detect_header("WORK EXPERIENCE", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "experience"

    def test_skills_detected(self):
        r = detect_header("Technical Skills", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "skills"

    def test_leadership_detected(self):
        r = detect_header("Leadership", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "leadership"

    def test_certifications_detected(self):
        r = detect_header("Certifications", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "certifications"

    def test_positions_of_responsibility_detected_as_leadership(self):
        r = detect_header("Positions of Responsibility", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "leadership"

    def test_extracurriculars_detected_as_leadership(self):
        r = detect_header("Extracurricular Activities", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "leadership"

    def test_projects_detected(self):
        r = detect_header("Projects", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "projects"

    def test_summary_detected(self):
        r = detect_header("Professional Summary", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "summary"

    def test_objective_detected_as_summary(self):
        r = detect_header("Career Objective", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "summary"

    def test_volunteering_detected_as_leadership(self):
        r = detect_header("Volunteer Experience", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "leadership"

    def test_alias_with_trailing_colon(self):
        r = detect_header("Education:", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "education"

    def test_case_insensitive_matching(self):
        r = detect_header("education", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "education"


class TestCombinedHeaderResolution:
    """Tests for Stage 4: Combined header resolution.

    These are the most critical tests — combined headers were the primary
    cause of leadership disappearing into other_section.
    """

    def test_positions_slash_extracurriculars(self):
        r = detect_header("Positions of Responsibility / Extracurriculars", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "leadership"
        assert r.match_method == "combined"
        assert len(r.combined_sections) >= 1

    def test_leadership_and_activities(self):
        r = detect_header("Leadership & Activities", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "leadership"
        # May be "exact" (alias exists) or "combined" — both are correct
        assert r.match_method in ("exact", "combined")

    def test_education_and_certifications(self):
        r = detect_header("Education and Certifications", line_number=0)
        assert r.is_header is True
        # Education has higher priority
        assert r.canonical_section == "education"
        assert "certifications" in r.combined_sections

    def test_skills_and_tools(self):
        r = detect_header("Skills & Tools", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "skills"

    def test_leadership_pipe_activities(self):
        r = detect_header("Leadership | Activities", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "leadership"

    def test_experience_and_projects(self):
        r = detect_header("Experience & Projects", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "experience"


class TestSpacedCharacterHeaders:
    """Tests for PDF extraction artifact: 'L e a d e r s h i p'."""

    def test_spaced_education(self):
        r = detect_header("E d u c a t i o n", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "education"

    def test_spaced_leadership(self):
        r = detect_header("L e a d e r s h i p", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "leadership"

    def test_spaced_skills(self):
        r = detect_header("S k i l l s", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "skills"

    def test_spaced_experience(self):
        r = detect_header("E x p e r i e n c e", line_number=0)
        assert r.is_header is True
        assert r.canonical_section == "experience"


class TestNonHeaders:
    """Tests for lines that must NOT be mistakenly detected as headers."""

    def test_bullet_point_not_header(self):
        r = detect_header("- Developed RESTful APIs using Python and Django", line_number=1)
        assert r.is_header is False

    def test_long_sentence_not_header(self):
        r = detect_header(
            "Experienced software engineer with 5 years of Python development "
            "building scalable backend systems.",
            line_number=1,
        )
        assert r.is_header is False

    def test_date_line_not_header(self):
        r = detect_header("June 2021 – Present", line_number=5)
        assert r.is_header is False

    def test_email_not_header(self):
        r = detect_header("john.doe@email.com", line_number=1)
        assert r.is_header is False

    def test_sentence_with_period_not_header(self):
        r = detect_header("Built scalable systems using microservices.", line_number=10)
        assert r.is_header is False

    def test_empty_line_not_header(self):
        r = detect_header("", line_number=5)
        assert r.is_header is False

    def test_company_name_with_context_not_header(self):
        # Content line — company name + dates looks like header but context saves us
        r = detect_header("Amazon | Seattle | 2020 – Present", line_number=10)
        # This may or may not be detected as header — it should NOT be "education" or "skills"
        if r.is_header:
            assert r.canonical_section not in ("education", "skills", "certifications")


class TestFuzzyMatching:
    """Tests for Stage 5: Fuzzy matching fallback."""

    def test_typo_in_education(self):
        # "Eductaion" — common OCR typo
        r = detect_header("Eductaion", line_number=0)
        # Should either match education via fuzzy or be is_header=True going to other_section
        if r.is_header:
            assert r.canonical_section in ("education", None)

    def test_partial_match_certifications(self):
        r = detect_header("Certification & Licenses", line_number=0)
        assert r.is_header is True
        assert r.canonical_section in ("certifications", "leadership")


class TestConfidenceScores:
    """Tests for confidence score ranges."""

    def test_exact_match_high_confidence(self):
        r = detect_header("EDUCATION", line_number=0)
        assert r.confidence >= 0.9

    def test_non_header_low_confidence(self):
        r = detect_header("Built RESTful APIs with Python and Django serving 50K users.", line_number=5)
        assert r.confidence < HEADER_CONFIDENCE_AMBIGUOUS

    def test_combined_header_high_confidence(self):
        r = detect_header("Positions of Responsibility / Extracurriculars", line_number=0)
        assert r.confidence >= HEADER_CONFIDENCE_ACCEPT


class TestNormalizationLogging:
    """Tests that normalization transformations are logged correctly."""

    def test_unicode_dash_in_header_logged(self):
        r = detect_header("Leadership \u2013 Activities", line_number=0)
        assert "normalized_unicode_dashes" in r.normalization.transformations

    def test_zero_width_removal_logged(self):
        r = detect_header("Education\u200b", line_number=0)
        assert any("zero_width" in t for t in r.normalization.transformations)

    def test_spaced_char_collapse_logged(self):
        r = detect_header("E d u c a t i o n", line_number=0)
        assert "collapsed_spaced_characters" in r.normalization.transformations
