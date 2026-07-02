# resumeai/ontology — Skill Ontology (single source of truth)

This package is the **only** place skill vocabulary should be defined for the
ResumeAI matching engine. `resumeai/matching/jd_parser.py`,
`resumeai/matching/gap_analyzer.py`, and `resumeai/extractors/projects.py`
all pull their skill vocabulary from here — none of them should define their
own alias dictionary. A CI test
(`resumeai/tests/test_ontology_integrity.py::test_no_duplicate_skill_dictionaries_reintroduced`)
fails the build if one reappears.

## Files

| File | Purpose |
|---|---|
| `skill_ontology.json` | The data. Canonical skills, aliases, categories, relationships, families, domain weights. |
| `schema.py` | Structural validation for the JSON (no duplicate aliases, every relationship resolves, etc.). |
| `registry.py` | The loader/matcher. Singleton, loads once at process startup, precomputes the relationship closure. |

## How to add a new skill

1. Open `skill_ontology.json`.
2. Find (or create) the right category under `"categories"`, and add:
   ```json
   "My New Skill": {
     "aliases": ["alias one", "alias two", "acronym"]
   }
   ```
   All aliases should be lowercase. The canonical key itself doesn't need to
   be repeated in the alias list.
3. (Optional) If the skill relates to another one, add an entry to
   `"relationships"`:
   ```json
   {
     "source": "My New Skill",
     "target": "Some Parent Skill",
     "type": "used_for",
     "relation_class": "hierarchical",
     "weight": 0.85
   }
   ```
   - `relation_class: "hierarchical"` — child implies parent (e.g. FastAPI
     implements Python). The registry gives full credit in the child→parent
     direction and reduced credit in reverse, so a generic parent skill on a
     resume doesn't fully satisfy a JD asking for one specific child.
   - `relation_class: "sibling"` — related-but-distinct alternatives under
     the same parent (e.g. JWT / OAuth / Bearer Token under Authentication).
     Siblings match each other at the given weight, but never at full (1.0)
     confidence, since they aren't actually the same thing.
   - `weight` is a float in `(0, 1]`. See `registry.py`'s `TYPE_WEIGHT`
     defaults for typical starting points per relation type.
4. Run the integrity tests locally:
   ```
   pytest resumeai/tests/test_ontology_integrity.py -v
   ```
5. **No code change is required.** `jd_parser.py`, `gap_analyzer.py`, and
   `extractors/projects.py` all pick up the new skill automatically on next
   process start (the registry is a singleton loaded once at startup).

## Why this exists

Before this package existed, skill vocabulary was defined independently in
three different places (`jd_parser.py::CANONICAL_SKILLS`,
`extractors/projects.py::TECH_NORMALIZE`, and an unused
`core/skill_intelligence.py`), which meant a skill recognized on the resume
side could be completely invisible to the JD-parsing side (or vice versa) —
see `semantic_matching_audit.md` for the concrete bugs this caused. This
package is the fix: one file of data, one loader, everything else reads from
it.

## Ownership

Changes to `skill_ontology.json` are content changes, not engineering
changes — they should be reviewable by anyone who understands the skill
domain, not just engineers. Recommended: add a `CODEOWNERS` entry for this
directory naming whoever owns match-quality for the product.

## Performance notes

- The JSON (~90KB) is parsed once per process, at startup (via
  `preload_registry()` in `resumeai_app/backend/main.py`'s startup hook),
  not per request.
- The relationship closure (bidirectional, depth ≤ 2) is also precomputed
  once at startup. Every match-time lookup (`registry.related()`,
  `registry.closure_for()`) is an O(1) dict access.
- Total memory footprint: well under 1MB. See `architecture_review.md` §7
  for the full per-change performance breakdown.
