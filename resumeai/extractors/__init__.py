"""
extractors/ — Field-level extractors for each canonical section.

Each extractor:
  - Takes a List[str] of raw_lines (already segmented by Phase 1).
  - Returns a typed structure matching the schema.
  - Has NO knowledge of other sections.
  - Shares NO state with other extractors.
"""
