"""
resumeai/extractors/project_rules.py — Contextual capability inference rules.

This upgrades the previous ad-hoc keyword checks in projects.py::_infer_capabilities
(single generic words like "api" or "test" anywhere in the text triggering a
capability) into precise, auditable pattern rules.

Design principles (see architecture_review.md §2.4):
  - Each rule emits a CANONICAL skill name (from the shared ontology). Rules
    do NOT encode synonym/relationship knowledge themselves -- that's the
    ontology registry's job (resumeai/ontology/registry.py). This keeps rule
    authoring simple and prevents a second synonym table from growing here.
  - Rules require technology/action co-occurrence where a single generic
    word would be too noisy (e.g. "implemented" + "login"/"jwt"/"oauth" for
    Authentication, not "auth" appearing anywhere in any form).
  - Pure regex over already-in-memory text -- no embeddings, no models, no
    additional per-request cost. Compiled once at import time.
  - Every match is auditable: rules are (name, pattern, canonical_skill)
    tuples, so a future maintainer can see exactly why a capability was
    inferred (useful for the "reason"/evidence trail elsewhere in the app).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Set


@dataclass(frozen=True)
class CapabilityRule:
    name: str  # human-readable id, useful for debugging/audit trails
    pattern: re.Pattern
    canonical_skill: str


def _rule(name: str, regex: str, canonical_skill: str) -> CapabilityRule:
    return CapabilityRule(name=name, pattern=re.compile(regex, re.IGNORECASE), canonical_skill=canonical_skill)


# Ordered list of (pattern -> canonical skill) rules. Patterns require
# action-verb + domain-token co-occurrence wherever a bare keyword would be
# too broad (e.g. "api" alone is too common to safely imply "API Integration").
CAPABILITY_RULES: List[CapabilityRule] = [
    # ── Authentication ──────────────────────────────────────────────────────
    _rule(
        "auth_implementation",
        r"\b(implement|implemented|build|built|add|added|integrat\w*)\b[^.]{0,40}"
        r"\b(login|sign[\s-]?in|sign[\s-]?up|auth\w*)\b[^.]{0,40}"
        r"\b(jwt|oauth\w*|bearer|session|token)\b",
        "Authentication",
    ),
    _rule(
        "auth_direct_mechanism",
        r"\b(jwt|oauth2?|bearer\s*token)\b",
        "Authentication",
    ),
    # ── CRUD ─────────────────────────────────────────────────────────────────
    _rule(
        "crud_verbs",
        r"\b(create|created|read|update|updated|delete|deleted|fetch\w*)\b[^.]{0,40}"
        r"\b(record|records|resource|resources|entries|entry|item|items|user|users|document|documents)\b",
        "CRUD",
    ),
    _rule(
        "crud_explicit",
        r"\bcrud\b",
        "CRUD",
    ),
    # ── Real-time systems ────────────────────────────────────────────────────
    _rule(
        "realtime_tech",
        r"\b(websocket|socket\.?io|server[\s-]?sent\s*events|sse|mqtt|real[\s-]?time)\b",
        "Real-time Systems",
    ),
    # ── Cloud deployment ─────────────────────────────────────────────────────
    _rule(
        "cloud_deploy_action",
        r"\b(deploy\w*|host\w*|shipped)\b[^.]{0,40}"
        r"\b(aws|gcp|azure|heroku|vercel|netlify|render|railway|ec2|s3|lambda|docker|kubernetes|cloud)\b",
        "Cloud Deployment",
    ),
    # ── IoT / embedded ────────────────────────────────────────────────────────
    _rule(
        "iot_hardware",
        r"\b(esp32|esp8266|arduino|raspberry\s*pi|sensor\w*|microcontroller|embedded\s*system)\b",
        "IoT",
    ),
    # ── API integration (third-party API usage, not just "the word api") ────
    _rule(
        "api_integration_action",
        r"\b(integrat\w*|connect\w*|call\w*)\b[^.]{0,40}"
        r"\b(api|sdk|endpoint\w*)\b",
        "API Integration",
    ),
    # ── Prompt engineering / LLM usage ───────────────────────────────────────
    _rule(
        "prompt_engineering",
        r"\b(prompt\w*\s*(engineer\w*|design\w*|template\w*)|"
        r"designed\s*prompts|crafted\s*prompts)\b",
        "Prompt Engineering",
    ),
    _rule(
        "llm_usage_implies_prompting",
        r"\b(gemini|openai|gpt-?\d|chatgpt|claude\s*api|llm)\b[^.]{0,60}"
        r"\b(prompt\w*|generat\w*\s*(response|text|content))\b",
        "Prompt Engineering",
    ),
    # ── Resume parsing (domain-specific to this product, but a legitimate
    # general pattern: extracting structured data from resume/CV text) ───────
    _rule(
        "resume_parsing",
        r"\b(pars\w*|extract\w*)\b[^.]{0,40}\b(resume|resumes|cv|cvs)\b",
        "Resume Parsing",
    ),
    # ── Testing ───────────────────────────────────────────────────────────────
    _rule(
        "testing_explicit",
        r"\b(unit\s*test\w*|integration\s*test\w*|test[\s-]?driven|pytest|jest|junit|selenium|cypress)\b",
        "Testing",
    ),
    # ── Data visualization ────────────────────────────────────────────────────
    _rule(
        "data_viz",
        r"\b(dashboard\w*|data\s*visuali[sz]\w*|charts?\b|graphs?\s*(rendered|displayed))\b",
        "Data Visualization",
    ),
]


def infer_capabilities_from_text(text: str) -> Set[str]:
    """Run all capability rules against a block of project/experience text
    (description + bullets). Returns the set of canonical skill names any
    rule matched. Cheap: compiled regex scan, no external calls."""
    if not text:
        return set()
    found: Set[str] = set()
    for rule in CAPABILITY_RULES:
        if rule.pattern.search(text):
            found.add(rule.canonical_skill)
    return found
