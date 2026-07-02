"""
resumeai/ontology/schema.py — Structural validation for skill_ontology.json.

This is the enforcement mechanism behind the "single source of truth" design:
if the ontology file is malformed, this fails loudly and early (at load time,
and in CI via test_ontology_integrity.py) instead of silently degrading match
quality at runtime.

No external dependencies beyond the standard library — keeps ontology loading
cheap and dependency-free, which matters on a 512MB free-tier deployment.
"""
from __future__ import annotations

from typing import Any, Dict, List, Set

ALLOWED_RELATION_CLASSES = {"hierarchical", "sibling"}
ALLOWED_RELATION_TYPES = {
    "implements", "used_for", "framework_of", "belongs_to",
    "orchestrates", "library_for", "sibling_of",
}


class OntologyValidationError(ValueError):
    """Raised when skill_ontology.json fails structural validation."""


def _collect_canonical_skills(ontology: Dict[str, Any]) -> Set[str]:
    canonicals: Set[str] = set()
    for _cat_name, skills in ontology.get("categories", {}).items():
        canonicals.update(skills.keys())
    return canonicals


def validate_ontology(ontology: Dict[str, Any]) -> List[str]:
    """
    Validate the ontology structure. Returns a list of human-readable
    problem descriptions (empty list == valid). Does not raise -- callers
    decide whether to treat problems as fatal (production load) or just
    report them (CI test).
    """
    problems: List[str] = []

    if "categories" not in ontology or not isinstance(ontology["categories"], dict):
        problems.append("Missing or invalid top-level 'categories' object.")
        return problems  # nothing else is checkable without this

    canonical_skills = _collect_canonical_skills(ontology)

    # ── 1. No alias maps to two different canonicals ──────────────────────
    alias_owner: Dict[str, str] = {}
    for cat_name, skills in ontology["categories"].items():
        for canonical, data in skills.items():
            if not isinstance(data, dict) or "aliases" not in data:
                problems.append(f"Skill '{canonical}' in category '{cat_name}' missing 'aliases' list.")
                continue
            aliases = data["aliases"]
            if not isinstance(aliases, list):
                problems.append(f"Skill '{canonical}' aliases must be a list.")
                continue
            for alias in [canonical] + aliases:
                key = alias.lower().strip()
                if key in alias_owner and alias_owner[key] != canonical:
                    problems.append(
                        f"Alias '{alias}' maps to both '{alias_owner[key]}' and '{canonical}' "
                        f"(ambiguous canonicalization)."
                    )
                else:
                    alias_owner[key] = canonical

    # ── 2. Every relationship source/target resolves to a real canonical ──
    for i, rel in enumerate(ontology.get("relationships", [])):
        for field in ("source", "target"):
            val = rel.get(field)
            if val not in canonical_skills:
                problems.append(
                    f"Relationship #{i} field '{field}'='{val}' does not resolve to a "
                    f"canonical skill defined in 'categories'."
                )
        rtype = rel.get("type")
        if rtype not in ALLOWED_RELATION_TYPES:
            problems.append(f"Relationship #{i} has unknown type '{rtype}'.")
        rclass = rel.get("relation_class")
        if rclass not in ALLOWED_RELATION_CLASSES:
            problems.append(f"Relationship #{i} has unknown relation_class '{rclass}'.")
        weight = rel.get("weight")
        if not isinstance(weight, (int, float)) or not (0.0 < weight <= 1.0):
            problems.append(f"Relationship #{i} has invalid weight '{weight}' (expected 0 < w <= 1).")

    # ── 3. No relationship cycle of length 1 (self-loop) ───────────────────
    for i, rel in enumerate(ontology.get("relationships", [])):
        if rel.get("source") == rel.get("target"):
            problems.append(f"Relationship #{i} is a self-loop ({rel.get('source')} -> itself).")

    # ── 4. families reference real canonical skills ────────────────────────
    for fam_name, skills in ontology.get("families", {}).items():
        for s in skills:
            if s not in canonical_skills:
                problems.append(f"Family '{fam_name}' references unknown skill '{s}'.")

    return problems


def assert_valid_ontology(ontology: Dict[str, Any]) -> None:
    problems = validate_ontology(ontology)
    if problems:
        raise OntologyValidationError(
            f"skill_ontology.json failed validation with {len(problems)} problem(s):\n"
            + "\n".join(f"  - {p}" for p in problems)
        )
