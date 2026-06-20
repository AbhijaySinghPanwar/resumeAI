"""
unit/test_ownership_engine.py — Structural invariant tests for the ownership engine.

These tests verify that the engine's structural guarantees hold
for ANY input, without knowing what the expected content is.

The key insight: these tests can run on ANY resume and should always pass.
They prove the architecture is sound, not that specific content was extracted.
"""

import pytest
from resumeai.core.ownership_engine import segment_document, OwnershipResult
from resumeai.core.constants import CANONICAL_SECTIONS
from resumeai.tests.fixtures.fixtures import ALL_FIXTURES, FIXTURE_STANDARD, FIXTURE_COMBINED_HEADER


# ── Helper ────────────────────────────────────────────────────────────────────

def parse_fixture(text: str) -> OwnershipResult:
    lines = text.splitlines()
    return segment_document(lines)


# ── Invariant tests ───────────────────────────────────────────────────────────

class TestStructuralInvariants:
    """
    These must pass for every fixture, every time.
    A failure here means the architecture is broken, not a content bug.
    """

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=[f["name"] for f in ALL_FIXTURES])
    def test_verify_invariants_passes(self, fixture):
        """verify_invariants() must return [] for every valid document."""
        result = parse_fixture(fixture["text"])
        violations = result.verify_invariants()
        assert violations == [], (
            f"Fixture '{fixture['name']}' has invariant violations:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=[f["name"] for f in ALL_FIXTURES])
    def test_every_line_in_exactly_one_block(self, fixture):
        """No line may belong to multiple blocks. No line may be orphaned."""
        result = parse_fixture(fixture["text"])
        seen = {}

        for block in result.blocks:
            for i, _ in enumerate(block.raw_lines):
                abs_line = block.start_line + i
                if abs_line in seen:
                    pytest.fail(
                        f"Fixture '{fixture['name']}': Line {abs_line} appears in "
                        f"both '{seen[abs_line]}' and '{block.section_name}'"
                    )
                seen[abs_line] = block.section_name

        # Every line in source must be accounted for
        total = result.total_lines
        for i in range(total):
            assert i in seen, (
                f"Fixture '{fixture['name']}': Line {i} not assigned to any block"
            )

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=[f["name"] for f in ALL_FIXTURES])
    def test_block_line_counts_sum_to_total(self, fixture):
        """Sum of all block line counts must equal total document lines."""
        result = parse_fixture(fixture["text"])
        total_in_blocks = sum(b.line_count for b in result.blocks)
        assert total_in_blocks == result.total_lines, (
            f"Fixture '{fixture['name']}': blocks contain {total_in_blocks} lines, "
            f"document has {result.total_lines}"
        )

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=[f["name"] for f in ALL_FIXTURES])
    def test_all_section_names_canonical(self, fixture):
        """Every block must have a valid canonical section name."""
        result = parse_fixture(fixture["text"])
        for block in result.blocks:
            assert block.section_name in CANONICAL_SECTIONS, (
                f"Fixture '{fixture['name']}': Block has invalid section_name: "
                f"{block.section_name!r}"
            )

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=[f["name"] for f in ALL_FIXTURES])
    def test_blocks_are_contiguous(self, fixture):
        """Block line ranges must be contiguous — no gaps within a block."""
        result = parse_fixture(fixture["text"])
        for block in result.blocks:
            expected_end = block.start_line + block.line_count - 1
            assert block.end_line == expected_end, (
                f"Fixture '{fixture['name']}': Block {block.section_name} "
                f"start={block.start_line} end={block.end_line} "
                f"but has {block.line_count} lines (expected end={expected_end})"
            )

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=[f["name"] for f in ALL_FIXTURES])
    def test_no_zero_line_blocks(self, fixture):
        """Every block must contain at least one line."""
        result = parse_fixture(fixture["text"])
        for block in result.blocks:
            assert block.line_count > 0, (
                f"Fixture '{fixture['name']}': Block {block.section_name} "
                f"at line {block.start_line} has zero lines"
            )

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=[f["name"] for f in ALL_FIXTURES])
    def test_debug_output_always_present(self, fixture):
        """Debug output is never None and always contains required keys."""
        result = parse_fixture(fixture["text"])
        debug_dict = result.debug.to_dict()

        required_keys = [
            "parser_version", "parse_timestamp", "total_lines",
            "detected_headers", "section_transitions", "unrecognized_headers",
            "ownership_log", "section_summary", "anomalies",
        ]
        for key in required_keys:
            assert key in debug_dict, (
                f"Fixture '{fixture['name']}': debug missing key: {key!r}"
            )

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=[f["name"] for f in ALL_FIXTURES])
    def test_ownership_log_length_equals_total_lines(self, fixture):
        """ownership_log must have exactly one entry per document line."""
        result = parse_fixture(fixture["text"])
        debug = result.debug.to_dict()
        assert len(debug["ownership_log"]) == result.total_lines, (
            f"Fixture '{fixture['name']}': ownership_log has {len(debug['ownership_log'])} "
            f"entries but document has {result.total_lines} lines"
        )


# ── Bleeding prevention tests ─────────────────────────────────────────────────

class TestBleedingPrevention:
    """
    These tests verify the most critical architectural property:
    that an unrecognized header closes the previous section
    rather than allowing it to bleed.
    """

    def test_unrecognized_header_closes_previous_section(self):
        """
        If a header is unrecognized, the previous section must close.
        Content after the unrecognized header must NOT go to the previous section.

        We use context (blank line before) to boost structural score.
        """
        lines = [
            "CERTIFICATIONS",
            "AWS Certified",
            "Google Cloud",
            "",                                                # blank line before unrecognized
            "Unrecognized Section Header XYZ",                # unrecognized
            "Content that must NOT be in certifications",
            "More content that must NOT be in certifications",
        ]
        result = segment_document(lines)

        cert_lines = result.all_lines_for_section("certifications")
        cert_text = " ".join(cert_lines)

        assert "Content that must NOT be in certifications" not in cert_text, (
            "Certifications bled through an unrecognized header — "
            "the previous section was not closed"
        )

    def test_certifications_do_not_absorb_leadership(self):
        """
        The primary documented failure: certifications absorbing leadership content.
        This must be structurally impossible.
        """
        lines = [
            "Certifications",
            "AWS Certified Solutions Architect",
            "Google Cloud Professional",
            "Positions of Responsibility",
            "Vice President | Finance Club | 2022 - 2023",
            "- Led annual finance conclave",
            "Secretary | NSS | 2021 - 2022",
        ]
        result = segment_document(lines)

        cert_lines = result.all_lines_for_section("certifications")
        cert_text = " ".join(cert_lines).lower()

        leadership_lines = result.all_lines_for_section("leadership")
        leadership_text = " ".join(leadership_lines)

        # VP and Secretary should NOT be in certifications
        assert "vice president" not in cert_text, (
            "Certifications absorbed 'Vice President' — leadership is bleeding"
        )
        assert "secretary" not in cert_text, (
            "Certifications absorbed 'Secretary' — leadership is bleeding"
        )

        # Leadership section must have content
        assert len(leadership_lines) > 0, (
            "Leadership section is empty — content was lost"
        )

    def test_education_not_lost_to_preceding_section(self):
        """Education must survive even when preceded by a large section."""
        lines = [
            "Work Experience",
            "Software Engineer | Company A | 2021 - Present",
            "- Built APIs",
            "- Led team",
            "- Designed systems",
            "- Optimized performance",
            "Education",
            "B.Tech Computer Science | IIT | 2017-2021",
        ]
        result = segment_document(lines)

        edu_lines = result.all_lines_for_section("education")
        assert len(edu_lines) > 0, "Education section disappeared"

        edu_text = " ".join(edu_lines)
        assert "B.Tech" in edu_text or "education" in edu_text.lower()


# ── Determinism tests ─────────────────────────────────────────────────────────

class TestDeterminism:
    """
    Same input must always produce identical output.
    This catches non-deterministic regex ordering, float instability, etc.
    """

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=[f["name"] for f in ALL_FIXTURES])
    def test_identical_output_on_repeated_runs(self, fixture):
        """Parse the same fixture 5 times and assert identical block structure."""
        lines = fixture["text"].splitlines()
        first_result = segment_document(lines)
        first_sections = [(b.section_name, b.start_line, b.end_line) for b in first_result.blocks]

        for run in range(2, 6):
            result = segment_document(lines)
            sections = [(b.section_name, b.start_line, b.end_line) for b in result.blocks]
            assert sections == first_sections, (
                f"Fixture '{fixture['name']}': Run {run} produced different "
                f"section structure than run 1.\n"
                f"Run 1: {first_sections}\n"
                f"Run {run}: {sections}"
            )

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=[f["name"] for f in ALL_FIXTURES])
    def test_section_names_stable_across_runs(self, fixture):
        """The set of detected section names must be stable."""
        lines = fixture["text"].splitlines()
        results = [segment_document(lines) for _ in range(3)]
        section_sets = [
            frozenset(b.section_name for b in r.blocks)
            for r in results
        ]
        assert len(set(section_sets)) == 1, (
            f"Fixture '{fixture['name']}': Section names vary across runs: {section_sets}"
        )
