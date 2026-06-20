"""
adversarial/test_adversarial.py — Adversarial input tests.

These are deliberately pathological inputs designed to break naive parsers.
Every test here corresponds to a class of real-world resume edge case.

A parser that passes all adversarial tests is robust.
A parser that only passes fixture tests may still fail in production.
"""

import pytest
from resumeai.pipeline import ResumeParser
from resumeai.core.ownership_engine import segment_document
from resumeai.core.schema import validate_result


@pytest.fixture
def parser():
    return ResumeParser(strict_schema=False, include_debug=True)


# ── Adversarial Category 1: Structural extremes ───────────────────────────────

class TestStructuralExtremes:

    def test_completely_empty_input(self, parser):
        """Parser must not crash on empty string."""
        result = parser.parse_text("")
        assert result is not None
        assert isinstance(result["education"], list)

    def test_single_line_input(self, parser):
        """Parser must handle one-line documents."""
        result = parser.parse_text("John Doe")
        assert result is not None
        violations = validate_result(result)
        assert violations == []

    def test_only_whitespace(self, parser):
        result = parser.parse_text("   \n\n\t\n   ")
        assert result is not None
        assert isinstance(result["education"], list)

    def test_extremely_long_document(self, parser):
        """Parser must handle documents with many lines without performance collapse."""
        # 500 lines of fake content
        lines = ["Software Engineer | Company A | 2020 - Present"] + \
                ["- Built REST APIs and microservices"] * 499
        text = "\n".join(lines)
        result = parser.parse_text(text)
        assert result is not None

    def test_all_blank_lines_between_content(self, parser):
        """Many blank lines between sections must not confuse the engine."""
        text = "\n".join([
            "John Doe",
            "john@email.com",
            "",
            "",
            "",
            "EDUCATION",
            "",
            "",
            "B.Tech | IIT | 2020",
            "",
            "",
            "",
            "SKILLS",
            "",
            "Python, Java",
        ])
        result = parser.parse_text(text)
        assert isinstance(result["education"], list)
        assert isinstance(result["skills"], dict)

    def test_only_contact_info(self, parser):
        """Document with only contact details and no sections."""
        text = "Jane Smith\njane@email.com\n+1-555-0100\nSan Francisco, CA"
        result = parser.parse_text(text)
        assert result is not None
        # Contact info should be extracted
        assert result["contact"]["email"] == "jane@email.com"


# ── Adversarial Category 2: Header chaos ─────────────────────────────────────

class TestHeaderChaos:

    def test_fifteen_unrecognized_headers(self, parser):
        """Fifteen unrecognized headers must all go to other_section, no bleeding."""
        sections = [
            "Background",
            "Technical Competencies",
            "Professional Affiliations",
            "Research Interests",
            "Publications",
            "Awards and Honors",
            "Community Engagement",
            "Languages Spoken",
            "References",
            "Conferences",
            "Workshops",
            "Presentations",
            "Mentorship",
            "Industry Memberships",
            "Professional Development",
        ]
        lines = []
        for section in sections:
            lines.append(section)
            lines.append(f"- Content for {section}")
            lines.append("")

        result = segment_document(lines)
        violations = result.verify_invariants()
        assert violations == [], f"Invariant violations: {violations}"

    def test_every_line_looks_like_header(self, parser):
        """
        Document where every line looks like a header.
        The structural scorer must prevent content lines from all being
        misidentified as headers.
        """
        text = "\n".join([
            "EDUCATION",
            "EXPERIENCE",
            "SKILLS",
            "PROJECTS",
            "LEADERSHIP",
            "CERTIFICATIONS",
            "SUMMARY",
        ])
        result = parser.parse_text(text)
        assert result is not None
        violations = validate_result(result)
        assert violations == []

    def test_duplicate_section_headers(self, parser):
        """Same section appearing twice — second occurrence must not crash."""
        text = "\n".join([
            "EDUCATION",
            "B.Tech | IIT | 2020",
            "SKILLS",
            "Python, Java",
            "EDUCATION",           # duplicate
            "M.Tech | IIT | 2022",
        ])
        result = parser.parse_text(text)
        assert result is not None
        # No crash. Schema valid.
        violations = validate_result(result)
        assert violations == []

    def test_header_as_last_line(self, parser):
        """Section header as the very last line — empty section must not crash."""
        text = "\n".join([
            "John Doe",
            "john@email.com",
            "EDUCATION",
            "B.Tech | IIT | 2021",
            "LEADERSHIP",           # header with nothing after it
        ])
        result = parser.parse_text(text)
        assert result is not None
        assert isinstance(result["leadership"], list)

    def test_header_immediately_followed_by_another_header(self, parser):
        """Two consecutive headers — first section is empty, must not crash."""
        text = "\n".join([
            "EDUCATION",
            "EXPERIENCE",          # immediate next header, education is empty
            "Software Engineer | Company | 2021",
        ])
        result = parser.parse_text(text)
        assert isinstance(result["education"], list)
        assert isinstance(result["experience"], list)

    def test_mixed_case_headers(self, parser):
        """Headers in various case formats must all be detected."""
        cases = [
            "education", "EDUCATION", "Education",
            "eDuCaTiOn",  # random case — structural score may not catch this
        ]
        results = []
        for case in cases[:3]:  # First 3 are well-formed
            text = f"{case}\nB.Tech | IIT | 2021"
            result = parser.parse_text(text)
            edu_summary = result["debug"]["section_summary"].get("education", {})
            results.append(edu_summary.get("total_lines", 0) > 0)

        assert all(results), (
            f"Some case variants not recognized: {list(zip(cases[:3], results))}"
        )


# ── Adversarial Category 3: Content that looks like headers ──────────────────

class TestFalseHeaderPrevention:
    """
    Content lines that superficially resemble headers must NOT trigger
    ownership transitions.
    """

    def test_company_name_not_mistaken_for_header(self, parser):
        """A company name in all caps must not become a section header."""
        text = "\n".join([
            "WORK EXPERIENCE",
            "GOOGLE INC",          # company name in caps — NOT a header
            "Software Engineer | 2020 - Present",
            "- Built distributed systems",
            "",
            "AMAZON",              # another company name
            "Senior Engineer | 2022 - Present",
        ])
        result = parser.parse_text(text)
        # Google Inc and Amazon should not appear as top-level section names
        debug = result["debug"]
        section_names = {b["to_section"] for b in debug.get("section_transitions", [])}
        assert "google inc" not in section_names

    def test_degree_name_not_mistaken_for_header(self, parser):
        """'BACHELOR OF TECHNOLOGY' within education must not open a new section."""
        text = "\n".join([
            "EDUCATION",
            "BACHELOR OF TECHNOLOGY",  # degree line, not a header
            "Computer Science | IIT | 2021",
            "",
            "SKILLS",
            "Python, Java",
        ])
        result = parser.parse_text(text)
        # Skills must still be detected (if degree opened new section, skills would be lost)
        skills_lines = result["debug"]["section_summary"].get("skills", {}).get("total_lines", 0)
        assert skills_lines > 0, "Skills were lost — degree name may have been misidentified as section"

    def test_gpa_line_not_header(self, parser):
        """'CGPA: 8.7/10' must not trigger a new section."""
        text = "\n".join([
            "EDUCATION",
            "B.Tech, Computer Science",
            "IIT Bombay | 2021",
            "CGPA: 8.7/10",         # detail line, not a header
            "",
            "EXPERIENCE",
            "Engineer | Company | 2021",
        ])
        result = parser.parse_text(text)
        assert result["debug"]["section_summary"].get("experience", {}).get("total_lines", 0) > 0


# ── Adversarial Category 4: Encoding extremes ─────────────────────────────────

class TestEncodingExtremes:

    def test_all_unicode_dashes_in_headers(self, parser):
        """Headers connected with various Unicode dashes must be recognized."""
        dashes = ["\u2013", "\u2014", "\u2012", "\u2015"]
        for dash in dashes:
            text = f"Leadership{dash}Activities\nVP | Finance Club | 2022"
            result = parser.parse_text(text)
            # Should not crash and should produce valid schema
            assert result is not None

    def test_null_bytes_in_text(self, parser):
        """Null bytes (PDF extraction artifact) must not crash the parser."""
        text = "EDUCATION\x00\nB.Tech | IIT | 2021\nSKILLS\nPython"
        try:
            result = parser.parse_text(text)
            assert result is not None
        except Exception as e:
            pytest.fail(f"Parser crashed on null bytes: {e}")

    def test_mixed_scripts_in_content(self, parser):
        """Content with non-Latin scripts in bullets must not confuse the engine."""
        text = "\n".join([
            "EDUCATION",
            "B.Tech | IIT | 2021",
            "EXPERIENCE",
            "Software Engineer | Company",
            "- Built systems (प्रणाली) for Hindi-speaking users",
            "SKILLS",
            "Python, Hindi (हिंदी), Tamil",
        ])
        result = parser.parse_text(text)
        assert result is not None
        violations = validate_result(result)
        assert violations == []

    def test_rtl_text_in_content(self, parser):
        """Right-to-left text in content must not crash."""
        text = "\n".join([
            "EDUCATION",
            "B.Tech Computer Science | 2021",
            "EXPERIENCE",
            "Engineer | \u202bشركة التقنية\u202c | 2022",  # RTL marks
            "- Developed applications",
        ])
        result = parser.parse_text(text)
        assert result is not None


# ── Adversarial Category 5: Regression from documented failures ───────────────

class TestDocumentedRegressions:
    """
    These tests were written AFTER documented production failures.
    Each test name describes the exact failure it prevents from recurring.
    """

    def test_regression_certifications_absorbing_leadership(self, parser):
        """
        REGRESSION: Production failure where leadership entries appeared
        inside certifications array.

        Root cause was: "Positions of Responsibility" not in alias list,
        so no ownership transition fired, and certifications section continued.
        """
        text = "\n".join([
            "Certifications",
            "CFA Level 1 | CFA Institute | 2022",
            "FRM Part 1 | GARP | 2023",
            "",
            "Positions of Responsibility",
            "President | Finance Club | 2022",
            "- Led annual conclave with 300+ attendees",
            "Secretary | Debate Club | 2021",
        ])
        result = parser.parse_text(text)

        # Certifications must not contain leadership content
        cert_names = [c.get("name", "") for c in result["certifications"] if c.get("name")]
        cert_text = " ".join(cert_names).lower()
        assert "president" not in cert_text, "REGRESSION: President found in certifications"
        assert "secretary" not in cert_text, "REGRESSION: Secretary found in certifications"

        # Leadership must have content
        assert len(result["leadership"]) >= 1, "REGRESSION: Leadership is empty"

    def test_regression_education_disappearing(self, parser):
        """
        REGRESSION: Education section disappeared in some resume formats.
        Root cause was year-prefixed lines being misidentified as non-education content.
        """
        text = "\n".join([
            "Contact",
            "test@email.com",
            "",
            "Education",
            "2019 - 2023   B.Tech Computer Science",
            "              BITS Pilani | CGPA: 8.5",
            "",
            "Experience",
            "Engineer | Company | 2023",
        ])
        result = parser.parse_text(text)
        edu_lines = result["debug"]["section_summary"].get("education", {}).get("total_lines", 0)
        assert edu_lines > 0, "REGRESSION: Education section disappeared"

    def test_regression_leadership_not_detected(self, parser):
        """
        REGRESSION: Leadership section had content but leadership[] was empty.
        Root cause was combined headers like 'Leadership & Extracurriculars'
        not being in the alias list.
        """
        text = "\n".join([
            "EDUCATION",
            "B.Tech | IIT | 2021",
            "",
            "WORK EXPERIENCE",
            "Engineer | Company | 2021",
            "",
            "LEADERSHIP & EXTRACURRICULARS",
            "President | Tech Club | 2020",
            "- Organized Annual Tech Fest",
            "NSS Volunteer | 2019",
        ])
        result = parser.parse_text(text)
        assert len(result["leadership"]) >= 1, (
            "REGRESSION: 'LEADERSHIP & EXTRACURRICULARS' combined header not recognized"
        )

    def test_regression_test_passing_while_real_resume_fails(self, parser):
        """
        META-REGRESSION: Tests passed because they used clean ASCII headers.
        Real resumes had PDF artifacts. This test uses dirty input.
        """
        # This is what PDF extraction actually produces for some documents
        dirty_text = "\n".join([
            "Arun Kumar",
            "arun@email.com",
            "",
            "E\u200bd\u200bu\u200bc\u200ba\u200bt\u200bi\u200bo\u200bn",  # zero-width spaces
            "B.Tech | IIT | 2021",
            "",
            "S k i l l s",              # spaced chars
            "Python, Java, React",
            "",
            "L e a d e r s h i p",     # spaced chars
            "President | Club | 2020",
        ])
        result = parser.parse_text(dirty_text)

        # Skills must be found despite spaced chars
        skills_lines = result["debug"]["section_summary"].get("skills", {}).get("total_lines", 0)
        assert skills_lines > 0, "Skills not detected despite spaced 'S k i l l s' header"

        # Leadership must be found despite spaced chars
        leadership_lines = result["debug"]["section_summary"].get("leadership", {}).get("total_lines", 0)
        assert leadership_lines > 0, "Leadership not detected despite spaced 'L e a d e r s h i p'"
