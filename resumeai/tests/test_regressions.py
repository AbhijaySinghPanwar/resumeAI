import pytest

from resumeai.extractors.education import _group_into_entries
from resumeai.ats.scorer import ResumeScorer
from resumeai.core.header_detector import _resolve_combined_header
from resumeai.extractors.experience import _parse_header as exp_parse_header
from resumeai.core.constants import ALIAS_LOOKUP, normalize_alias
from resumeai.extractors.skills import _split_skills


def test_education_substring_matching():
    # Should not match "ma" inside "Mathematics"
    group = _group_into_entries(["Mathematics"])
    from resumeai.extractors.education import DEGREE_KEYWORDS
    import re
    
    text = "Mathematics"
    matched = any(re.search(rf"\b{re.escape(kw)}\b", text.lower()) for kw in DEGREE_KEYWORDS)
    assert not matched, "Should not match 'ma' inside 'Mathematics'"

    text = "Systems"
    matched = any(re.search(rf"\b{re.escape(kw)}\b", text.lower()) for kw in DEGREE_KEYWORDS)
    assert not matched, "Should not match 'ms' inside 'Systems'"


def test_portfolio_header_ownership():
    # "LinkedIn - GitHub - Portfolio - LeetCode" should not resolve as a combined header
    text = "linkedin - github - portfolio - leetcode"
    result = _resolve_combined_header(text)
    assert result is None, "Should be rejected because match ratio is too low (1/4)"

    text = "leadership & activities"
    result = _resolve_combined_header(text)
    assert result is not None, "Should be accepted because match ratio is 100%"


def test_experience_date_range_parsing():
    # "Google – Software Engineer – Aug 2023 – Sep 2025"
    lines = ["Google \u2013 Software Engineer \u2013 Aug 2023 \u2013 Sep 2025"]
    company, title, start_date, end_date, is_current, location = exp_parse_header(lines)
    
    assert start_date == "2023-08"
    assert end_date == "2025-09"
    assert "Google" in (company or "") or "Google" in (title or "")


def test_awards_and_scholarships_alias():
    from resumeai.core.constants import ALIAS_LOOKUP, normalize_alias
    assert ALIAS_LOOKUP.get(normalize_alias("awards & scholarships")) == "leadership"
    assert ALIAS_LOOKUP.get(normalize_alias("awards")) == "leadership"


def test_skills_bullet_separator():
    text = "Java \u2022 Python \u2022 SQL"
    skills = _split_skills(text)
    assert len(skills) == 3
    assert skills[0] == "Java"
    assert skills[1] == "Python"
    assert skills[2] == "SQL"


def test_volunteer_experience_remaining_in_leadership():
    assert ALIAS_LOOKUP.get(normalize_alias("volunteer experience")) == "leadership"


def test_contact_urls():
    from resumeai.extractors.contact import extract_contact
    lines = [
        "github.com/user",
        "linkedin.com/user",
        "linkedin.com/in/user2",
        "leetcode.com/user",
        "portfolio.dev",
        "rajitagrawal2005@gmail.com",
    ]
    res = extract_contact(lines)
    assert res["github"] == "https://github.com/user"
    assert res["linkedin"] == "https://linkedin.com/user"
    assert res["portfolio"] == "leetcode.com/user"
    assert "portfolio.dev" in res["other_links"]
    assert not any("gmail.com" in link for link in res["other_links"])


def test_extra_curriculars_aliases():
    from resumeai.core.header_detector import detect_header
    for h in ["Extracurriculars", "Extra Curriculars", "Extra-Curriculars"]:
        res = detect_header(h)
        assert res.is_header is True
        assert res.canonical_section == "leadership"
        assert res.match_method == "exact"


def test_volunteer_header_strip():
    from resumeai.extractors.leadership import _get_content_lines
    lines1 = ["Volunteer Experience", "Red Cross"]
    lines2 = ["Volunteer at local shelter"]
    assert _get_content_lines(lines1) == ["Red Cross"]
    assert _get_content_lines(lines2) == []

def test_certification_classification():
    from resumeai.extractors.certifications import _classify_segment
    cases = [
        ("Google Cloud Professional Architect", "TITLE"),
        ("Google", "ISSUER"),
        ("AWS Cloud Practitioner", "TITLE"),
        ("Amazon Web Services", "ISSUER"),
        ("Oracle Cloud Infrastructure Generative AI Professional", "TITLE"),
        ("Oracle", "ISSUER"),
        ("Databricks Fundamentals", "TITLE"),
        ("Databricks", "ISSUER"),
        ("Postman API Fundamentals", "TITLE"),
        ("Postman", "ISSUER")
    ]
    for text, expected in cases:
        assert _classify_segment(text).name == expected

def test_title_with_year():
    from resumeai.extractors.certifications import _classify_segment
    assert _classify_segment("AWS Cloud Practitioner 2024").name == "TITLE"
    assert _classify_segment("2024").name == "DATE"
    assert _classify_segment("Issued May 2024").name == "DATE"

def test_multiline_cert_title():
    from resumeai.extractors.certifications import extract_certifications
    lines = [
        "Google Cloud",
        "Professional Architect",
        "Google"
    ]
    res = extract_certifications(lines)
    assert len(res) == 1
    # Multi-line titles currently combine on same line or get grouped under same cert
    # Since they are on separate lines, the state machine will merge them.
    assert "Google Cloud" in res[0]["name"]
    assert "Professional Architect" in res[0]["raw_lines"][1]
    assert res[0]["issuer"] == "Google"

def test_project_grouping_title_with_tech():
    from resumeai.extractors.projects import _group_into_entries
    lines = [
        "Personal Finance Tip Generator - HTML, CSS, JavaScript, Gemini API",
        "Engineered a web-based tool that delivers personalized budgeting suggestions.",
        "New Project Title - React, Node",
        "Built something cool."
    ]
    groups = _group_into_entries(lines)
    assert len(groups) == 2
    assert groups[0][0].startswith("Personal Finance")
    assert groups[1][0].startswith("New Project")

def test_certification_column_split():
    from resumeai.extractors.certifications import _stateful_grouping
    lines = ['\u2022 Postman API Fundamentals \u2013 Postman \u2022 Oracle Cloud Infrastructure Generative AI Professional']
    certs = _stateful_grouping(lines)
    assert len(certs) == 2
    assert certs[0]["name"] == "Postman API Fundamentals"
    assert certs[0]["issuer"] == "Postman"
    assert "Oracle Cloud" in certs[1]["name"]
    assert certs[1]["issuer"] == "Oracle"

def test_awards_maps_to_leadership():
    from resumeai.core.header_detector import detect_header
    res = detect_header("Awards & Scholarships")
    assert res.is_header
    assert res.canonical_section == "leadership"
