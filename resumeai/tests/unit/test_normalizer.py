"""
unit/test_normalizer.py — Unit tests for the artifact normalization module.

Every test is isolated. No parser state. No document context.
Tests mirror real PDF extraction artifacts documented in production failures.
"""

import pytest
from resumeai.core.normalizer import (
    normalize_line,
    normalize_for_matching,
    is_likely_empty,
)


class TestStripWhitespace:
    def test_leading_whitespace_stripped(self):
        r = normalize_line("   Education")
        assert r.normalized == "Education"
        assert "stripped_whitespace" in r.transformations

    def test_trailing_whitespace_stripped(self):
        r = normalize_line("Education   ")
        assert r.normalized == "Education"

    def test_no_modification_when_clean(self):
        r = normalize_line("Education")
        assert r.normalized == "Education"
        assert not r.was_modified


class TestZeroWidthRemoval:
    def test_zero_width_space_removed(self):
        r = normalize_line("Education\u200b")
        assert "\u200b" not in r.normalized
        assert any("zero_width" in t for t in r.transformations)

    def test_bom_removed(self):
        r = normalize_line("\ufeffEducation")
        assert "\ufeff" not in r.normalized

    def test_multiple_zero_width_removed(self):
        r = normalize_line("Lead\u200ber\u200cship")
        assert r.normalized == "Leadership"


class TestUnicodeDashNormalization:
    def test_en_dash_normalized(self):
        r = normalize_line("2019\u20132023")
        assert "\u2013" not in r.normalized
        assert "-" in r.normalized
        assert "normalized_unicode_dashes" in r.transformations

    def test_em_dash_normalized(self):
        r = normalize_line("Software Engineer \u2014 Google")
        assert "\u2014" not in r.normalized
        assert "Software Engineer - Google" == r.normalized

    def test_figure_dash_normalized(self):
        r = normalize_line("Jan 2020\u2012Present")
        assert "\u2012" not in r.normalized


class TestSpacedCharacterCollapse:
    def test_spaced_word_collapsed(self):
        r = normalize_line("L e a d e r s h i p")
        assert r.normalized == "Leadership"
        assert "collapsed_spaced_characters" in r.transformations

    def test_spaced_education_collapsed(self):
        r = normalize_line("E d u c a t i o n")
        assert r.normalized == "Education"

    def test_spaced_skills_collapsed(self):
        r = normalize_line("S k i l l s")
        assert r.normalized == "Skills"

    def test_normal_sentence_not_collapsed(self):
        r = normalize_line("Developed REST APIs using Python and Django")
        assert r.normalized == "Developed REST APIs using Python and Django"
        assert "collapsed_spaced_characters" not in r.transformations


class TestInternalWhitespaceCollapse:
    def test_multiple_spaces_collapsed(self):
        r = normalize_line("Software   Engineer")
        assert r.normalized == "Software Engineer"
        assert "collapsed_internal_whitespace" in r.transformations

    def test_tab_collapsed_to_space(self):
        r = normalize_line("Skills:\tPython, Java")
        assert "\t" not in r.normalized


class TestSmartQuotes:
    def test_smart_single_quotes_normalized(self):
        r = normalize_line("\u2018Bachelor\u2019s Degree\u2019")
        assert "\u2018" not in r.normalized
        assert "\u2019" not in r.normalized

    def test_smart_double_quotes_normalized(self):
        r = normalize_line('\u201cSoftware Engineer\u201d')
        assert '\u201c' not in r.normalized
        assert '\u201d' not in r.normalized


class TestNormalizeForMatching:
    def test_returns_lowercase(self):
        result = normalize_for_matching("EDUCATION")
        assert result == "education"

    def test_strips_whitespace(self):
        result = normalize_for_matching("  Leadership  ")
        assert result == "leadership"

    def test_collapses_spaced_chars(self):
        result = normalize_for_matching("L e a d e r s h i p")
        assert result == "leadership"


class TestIsLikelyEmpty:
    def test_empty_string(self):
        assert is_likely_empty("") is True

    def test_whitespace_only(self):
        assert is_likely_empty("   ") is True

    def test_dash_only(self):
        assert is_likely_empty("---") is True

    def test_real_content(self):
        assert is_likely_empty("Education") is False

    def test_single_char(self):
        assert is_likely_empty("A") is False
