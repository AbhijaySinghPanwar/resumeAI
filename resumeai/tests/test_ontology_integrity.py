"""
tests/test_ontology_integrity.py — Guardrails for the skill ontology.

Two jobs:
  1. Validate resumeai/ontology/skill_ontology.json against its schema
     (resumeai/ontology/schema.py) so a malformed edit fails CI instead of
     silently degrading match quality in production.
  2. Structurally prevent the "three disconnected skill dictionaries"
     problem from recurring: fail CI if any matching/extraction module
     defines its own top-level skill-alias dictionary instead of using the
     shared registry.

See architecture_review.md §6 (Maintainability) for the rationale.
"""
import ast
import json
import os

import pytest

from resumeai.ontology.schema import validate_ontology
from resumeai.ontology.registry import get_registry, SkillRegistry

ONTOLOGY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ontology", "skill_ontology.json"
)

# Modules that are allowed to import/use skill data -- but must do so via
# the registry, not by defining their own dictionary.
_GUARDED_MODULES = [
    os.path.join("matching", "jd_parser.py"),
    os.path.join("matching", "gap_analyzer.py"),
    os.path.join("extractors", "projects.py"),
]
_FORBIDDEN_NAME_PATTERNS = ("_SKILLS", "_ALIASES", "_NORMALIZE", "_IMPLICATIONS")
# TECH_NORMALIZE is intentionally still a module-level dict in projects.py,
# but it must be built FROM the registry (see the .setdefault(...) loop
# added there), not hand-authored as a standalone literal. We check for
# that pattern specifically rather than banning the name outright, since a
# thin backward-compatible cache of the registry's data is fine -- a
# second hand-maintained *source* of truth is not.
_ALLOWED_DERIVED_DICTS = {"TECH_NORMALIZE"}


def test_ontology_schema_is_valid():
    with open(ONTOLOGY_PATH, "r", encoding="utf-8") as f:
        ontology = json.load(f)
    problems = validate_ontology(ontology)
    assert not problems, "skill_ontology.json failed validation:\n" + "\n".join(problems)


def test_registry_loads_and_is_singleton():
    a = get_registry()
    b = SkillRegistry()
    assert a is b, "SkillRegistry must be a process-wide singleton"
    assert len(a.all_canonical_skills) > 50, "Ontology seems suspiciously small"


def test_registry_covers_audit_flagged_terms():
    """Regression guard for the specific terms the original audit found
    completely missing from the JD-side vocabulary (see
    semantic_matching_audit.md §2A)."""
    r = get_registry()
    must_resolve = [
        "authentication", "bearer token", "gemini api", "gemini",
        "crud", "cloud deployment", "real-time systems", "api integration",
        "resume parsing", "ec2", "s3", "aws lambda", "oauth", "oauth2",
    ]
    for term in must_resolve:
        assert r.normalize_skill(term) != term or term in r.all_canonical_skills, (
            f"'{term}' does not resolve to a canonical skill -- ontology regression"
        )


def test_no_duplicate_skill_dictionaries_reintroduced():
    """
    Structural guard: fail if a matching/extraction module defines a new
    top-level dict literal that looks like a hand-authored skill/alias
    table. This is what would have caught the original bug (three
    disconnected dictionaries) before it shipped.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    violations = []

    for rel_path in _GUARDED_MODULES:
        full_path = os.path.join(base_dir, rel_path)
        if not os.path.exists(full_path):
            continue
        with open(full_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=full_path)

        for node in ast.walk(tree):
            targets = None
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign) and node.target is not None:
                targets = [node.target]
            if not targets:
                continue

            for t in targets:
                name = getattr(t, "id", None)
                if not name:
                    continue
                if name in _ALLOWED_DERIVED_DICTS:
                    continue
                if any(pat in name for pat in _FORBIDDEN_NAME_PATTERNS):
                    # Only flag actual dict/list literals with real content,
                    # not e.g. an empty placeholder or a type alias.
                    if isinstance(node.value, (ast.Dict, ast.List)) and (
                        getattr(node.value, "keys", None) or getattr(node.value, "elts", None)
                    ):
                        violations.append(f"{rel_path}: {name}")

    assert not violations, (
        "Found what looks like a hand-authored skill dictionary outside the "
        "shared ontology registry -- add the terms to "
        "resumeai/ontology/skill_ontology.json instead:\n" + "\n".join(violations)
    )


def test_tech_normalize_is_derived_from_registry():
    """extractors/projects.py::TECH_NORMALIZE must be a superset of the
    registry's alias map (it's allowed to keep legacy canonical-name
    casing for pre-existing entries, but every registry alias must resolve
    to *some* canonical skill through it)."""
    from resumeai.extractors.projects import TECH_NORMALIZE

    registry_aliases = get_registry().alias_to_canonical_map()
    missing = [a for a in registry_aliases if a not in TECH_NORMALIZE]
    assert not missing, (
        f"{len(missing)} ontology aliases are not reachable via "
        f"extractors/projects.py::TECH_NORMALIZE: {missing[:10]}..."
    )
