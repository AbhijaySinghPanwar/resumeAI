"""
conftest.py — Shared pytest configuration.

Provides session-scoped parsed results for expensive fixtures,
so each fixture text is only parsed once per test session.
"""

import pytest
from resumeai.pipeline import ResumeParser
from resumeai.tests.fixtures.fixtures import (
    FIXTURE_STANDARD,
    FIXTURE_COMBINED_HEADER,
    FIXTURE_YEAR_PREFIX_EDUCATION,
    FIXTURE_CERT_THEN_LEADERSHIP,
    FIXTURE_PDF_ARTIFACTS,
    FIXTURE_NO_HEADERS,
    FIXTURE_DENSE,
)


@pytest.fixture(scope="session")
def session_parser():
    """One parser instance for the whole test session."""
    return ResumeParser(strict_schema=False, include_debug=True)


@pytest.fixture(scope="session")
def parsed_standard(session_parser):
    return session_parser.parse_text(FIXTURE_STANDARD)


@pytest.fixture(scope="session")
def parsed_combined_header(session_parser):
    return session_parser.parse_text(FIXTURE_COMBINED_HEADER)


@pytest.fixture(scope="session")
def parsed_year_prefix(session_parser):
    return session_parser.parse_text(FIXTURE_YEAR_PREFIX_EDUCATION)


@pytest.fixture(scope="session")
def parsed_cert_leadership(session_parser):
    return session_parser.parse_text(FIXTURE_CERT_THEN_LEADERSHIP)


@pytest.fixture(scope="session")
def parsed_pdf_artifacts(session_parser):
    return session_parser.parse_text(FIXTURE_PDF_ARTIFACTS)


@pytest.fixture(scope="session")
def parsed_no_headers(session_parser):
    return session_parser.parse_text(FIXTURE_NO_HEADERS)


@pytest.fixture(scope="session")
def parsed_dense(session_parser):
    return session_parser.parse_text(FIXTURE_DENSE)
