"""
resumeai/ontology/registry.py — Skill Ontology Registry (v2)

This is the ONLY place skill vocabulary should be defined. It replaces the
three previously-disconnected dictionaries:
  - matching/jd_parser.py::CANONICAL_SKILLS      (JD-side extraction)
  - extractors/projects.py::TECH_NORMALIZE        (resume-side extraction)
  - core/skill_intelligence.py::SkillIntelligenceEngine (built, never wired in)

Design goals (see architecture_review.md for the full rationale):
  1. Single source of truth: resumeai/ontology/skill_ontology.json.
  2. Everything expensive (parsing the JSON, building alias tables, computing
     the bidirectional relationship closure) happens ONCE at process startup,
     never per-request. Every lookup at match time is an O(1) dict access.
  3. Relationship matching distinguishes "hierarchical" (child implies parent,
     e.g. FastAPI implies Python) from "sibling" (related-but-distinct, e.g.
     JWT/OAuth/Bearer Token under Authentication) so a JD asking for one
     specific mechanism doesn't get full, undifferentiated credit from a
     resume that only shows a related-but-different one.
  4. Multi-hop traversal is bounded to depth 2 to avoid implausible long
     inference chains, and is precomputed into a flat closure table.

Memory footprint: the ontology JSON is ~90KB on disk; the built lookup
tables (alias map, closure, family index) total a few hundred KB in memory
at most. This is loaded once per process, not per request.
"""
from __future__ import annotations

import json
import os
import re
import threading
from functools import lru_cache
from typing import Any, Dict, List, Optional, Set, Tuple

from .schema import assert_valid_ontology

_ONTOLOGY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skill_ontology.json")


class SkillRegistry:
    """
    Process-wide singleton. Call get_registry() to obtain the instance;
    do not instantiate directly.
    """

    _instance: Optional["SkillRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "SkillRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:  # double-checked locking
                    inst = super().__new__(cls)
                    inst._load()
                    cls._instance = inst
        return cls._instance

    # ── Loading ──────────────────────────────────────────────────────────
    def _load(self) -> None:
        with open(_ONTOLOGY_PATH, "r", encoding="utf-8") as f:
            self._ontology: Dict[str, Any] = json.load(f)

        assert_valid_ontology(self._ontology)

        self._alias_to_canonical: Dict[str, str] = {}
        self._skill_to_category: Dict[str, str] = {}
        self._skill_to_families: Dict[str, Set[str]] = {}

        for cat_name, skills in self._ontology.get("categories", {}).items():
            for canonical, data in skills.items():
                self._alias_to_canonical[canonical.lower()] = canonical
                self._skill_to_category[canonical] = cat_name
                for alias in data.get("aliases", []):
                    self._alias_to_canonical[alias.lower()] = canonical

        # Longest-alias-first for greedy, non-overlapping span matching.
        self._sorted_aliases: List[Tuple[str, str]] = sorted(
            self._alias_to_canonical.items(), key=lambda kv: len(kv[0]), reverse=True
        )
        # Pre-compiled regex per alias (built once, reused every extraction call).
        self._alias_patterns: List[Tuple[re.Pattern, str]] = [
            (re.compile(r"(?<![a-zA-Z0-9/\-])" + re.escape(alias) + r"(?![a-zA-Z0-9/\-])"), canonical)
            for alias, canonical in self._sorted_aliases
        ]

        for family_name, skills in self._ontology.get("families", {}).items():
            for skill in skills:
                self._skill_to_families.setdefault(skill, set()).add(family_name)

        self._relationships: List[Dict[str, Any]] = self._ontology.get("relationships", [])
        self._closure = self._build_closure(max_depth=2)

    def _build_closure(self, max_depth: int) -> Dict[str, Dict[str, Tuple[float, str]]]:
        """
        Precompute a bounded-depth, bidirectional relationship closure ONCE.
        closure[a][b] = (weight, relation_class) meaning "a" and "b" are related.

        Hierarchical edges (child -> parent) are traversed forward at full
        weight; the reverse direction (parent -> child) is stored too but at
        a discounted weight, since "knows the general thing" is weaker
        evidence of "knows the specific thing" than the other way around.
        Sibling edges are stored symmetrically at their own weight.
        """
        # adjacency[node] = list of (neighbor, weight, relation_class, direction)
        adjacency: Dict[str, List[Tuple[str, float, str]]] = {}

        def add_edge(a: str, b: str, weight: float, relation_class: str) -> None:
            adjacency.setdefault(a, []).append((b, weight, relation_class))

        REVERSE_HIERARCHICAL_DISCOUNT = 0.5

        for rel in self._relationships:
            src, tgt = rel["source"], rel["target"]
            weight = float(rel.get("weight", 0.8))
            rclass = rel.get("relation_class", "hierarchical")
            if rclass == "sibling":
                add_edge(src, tgt, weight, "sibling")
                add_edge(tgt, src, weight, "sibling")
            else:
                add_edge(src, tgt, weight, "hierarchical")  # child -> parent, full weight
                add_edge(tgt, src, weight * REVERSE_HIERARCHICAL_DISCOUNT, "hierarchical")

        closure: Dict[str, Dict[str, Tuple[float, str]]] = {}
        for start in adjacency:
            visited: Dict[str, Tuple[float, str, int]] = {}  # node -> (weight, class, hops)
            frontier = [(start, 1.0, "hierarchical", 0)]
            while frontier:
                node, path_weight, _cls, depth = frontier.pop()
                if depth >= max_depth:
                    continue
                for neighbor, edge_weight, rclass in adjacency.get(node, []):
                    if neighbor == start:
                        continue
                    combined = path_weight * edge_weight
                    prev = visited.get(neighbor)
                    if prev is None or combined > prev[0]:
                        visited[neighbor] = (combined, rclass, depth + 1)
                        frontier.append((neighbor, combined, rclass, depth + 1))
            closure[start] = {n: (w, c) for n, (w, c, _hops) in visited.items()}
        return closure

    # ── Public API ───────────────────────────────────────────────────────
    @lru_cache(maxsize=2048)
    def normalize_skill(self, raw: str) -> str:
        if not raw:
            return raw
        return self._alias_to_canonical.get(raw.strip().lower(), raw.strip())

    def extract_skills_from_text(self, text: str) -> List[str]:
        """Greedy, longest-alias-first, non-overlapping extraction of canonical
        skill names from free text. Same algorithm/semantics as the previous
        per-module implementations, now backed by the single ontology."""
        if not text:
            return []
        text_lower = text.lower()
        found: Set[str] = set()
        consumed_spans: List[Tuple[int, int]] = []

        for pattern, canonical in self._alias_patterns:
            for m in pattern.finditer(text_lower):
                start, end = m.start(), m.end()
                if any(s < end and start < e for s, e in consumed_spans):
                    continue
                found.add(canonical)
                consumed_spans.append((start, end))

        return sorted(found)

    def closure_for(self, skill: str) -> Dict[str, Tuple[float, str]]:
        """All (skill -> (weight, relation_class)) pairs reachable within the
        precomputed depth-bounded closure for a canonical skill. O(1)."""
        return self._closure.get(skill, {})

    def related(self, skill_a: str, skill_b: str) -> Optional[Tuple[float, str]]:
        """
        O(1) check: are these two canonical skills related in the
        precomputed closure? Returns (confidence_weight, relation_class) or
        None. Callers should normalize_skill() both inputs first.
        """
        if skill_a == skill_b:
            return (1.0, "exact")
        return self._closure.get(skill_a, {}).get(skill_b)

    def family_match(self, skill_a: str, skill_b: str) -> Optional[str]:
        """Lowest-precision fallback: do these two canonical skills share a
        family? Returns the shared family name, or None. Callers should
        treat this as partial credit only, never a full boolean match."""
        fams_a = self._skill_to_families.get(skill_a, set())
        fams_b = self._skill_to_families.get(skill_b, set())
        shared = fams_a & fams_b
        return next(iter(shared), None) if shared else None

    def classify_industry_domain(self, text: str) -> List[str]:
        text_lower = text.lower()
        matched = []
        for domain, keywords in self._ontology.get("industry_domains", {}).items():
            if any(re.search(r"\b" + re.escape(kw) + r"\b", text_lower) for kw in keywords):
                matched.append(domain)
        return matched

    def alias_to_canonical_map(self) -> Dict[str, str]:
        """Flat alias(lowercase)->canonical map, for legacy call sites that
        need a plain dict rather than the extraction/normalize methods."""
        return dict(self._alias_to_canonical)

    @property
    def all_canonical_skills(self) -> Set[str]:
        return set(self._skill_to_category.keys())


# ── Module-level convenience API (mirrors the old jd_parser.py surface) ────
def get_registry() -> SkillRegistry:
    return SkillRegistry()


def preload_registry() -> None:
    """Call once at application startup (alongside the ONNX model preload)
    so the ontology JSON parse + closure precompute happens during boot,
    not on the first incoming request."""
    get_registry()


def extract_skills_from_text(text: str) -> List[str]:
    return get_registry().extract_skills_from_text(text)


def normalize_skill(raw: str) -> str:
    return get_registry().normalize_skill(raw)
