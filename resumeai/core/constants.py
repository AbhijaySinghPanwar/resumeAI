"""
constants.py — Canonical section registry and all fixed configuration.

This is the ONLY place where section names and aliases are defined.
Adding an alias here is the ONLY supported way to extend recognition.
No aliases live anywhere else in the codebase.
"""

from dataclasses import dataclass, field
from typing import Dict, List

PARSER_VERSION = "7.0.0"

# ── Canonical section identifiers ────────────────────────────────────────────
# These strings are the only valid section_name values in the system.
CANONICAL_SECTIONS = frozenset({
    "contact",
    "summary",
    "education",
    "experience",
    "projects",
    "leadership",
    "certifications",
    "skills",
    "open_source",
    "achievements",
    "publications",
    "hackathons",
    "research",
    "tech_blogs",
    "other_section",
})

# ── Section priority (higher index = higher priority for combined headers) ───
SECTION_PRIORITY = [
    "contact",
    "skills",
    "experience",
    "projects",
    "open_source",
    "research",
    "publications",
    "hackathons",
    "certifications",
    "achievements",
    "leadership",
    "tech_blogs",
    "education",
    "summary",
]

# ── Header confidence thresholds ─────────────────────────────────────────────
HEADER_CONFIDENCE_ACCEPT   = 0.75   # ≥ this → confirmed header, ownership transfers
HEADER_CONFIDENCE_AMBIGUOUS = 0.50  # 0.50–0.75 → ambiguous, goes to other_section
# below 0.50 → content line, stays in current section

FUZZY_ACCEPT_THRESHOLD  = 0.80
FUZZY_AMBIGUOUS_THRESHOLD = 0.60

# ── Combined header separators ────────────────────────────────────────────────
COMBINED_SEPARATORS = ["/", "|", "&", " and ", " & ", " + ", "–", "-"]

# ── Structural header signals ─────────────────────────────────────────────────
MAX_HEADER_LENGTH       = 60   # lines longer than this are almost never headers
MIN_ALL_CAPS_LENGTH     = 3    # "CV" shouldn't trigger all-caps boost

# ── Anomaly detection thresholds ─────────────────────────────────────────────
LARGE_SECTION_RATIO     = 0.60  # one section owning >60% of lines is suspicious
MAX_CERT_LINES_EXPECTED = 30    # certifications blocks larger than this are suspicious


@dataclass
class AliasEntry:
    """One entry in the section alias registry."""
    canonical_name: str
    aliases: List[str]
    weight: float = 1.0


# ── Section alias registry ────────────────────────────────────────────────────
# Rules:
#   1. All aliases are lowercase and pre-normalized (no leading/trailing spaces).
#   2. Aliases are matched AFTER artifact normalization is applied to the input.
#   3. Do NOT add combined-header aliases here (e.g. "leadership & activities").
#      The combined-header resolver handles those automatically.
#   4. Weight reflects how strongly an alias match implies this section (1.0 = certain).

SECTION_REGISTRY: List[AliasEntry] = [

    AliasEntry("contact", aliases=[
        "contact", "contact information", "contact info",
        "personal information", "personal details", "personal info",
        "profile", "basic information", "details",
    ]),

    AliasEntry("summary", aliases=[
        "summary", "professional summary", "career summary",
        "objective", "career objective", "professional objective",
        "about me", "about", "profile summary", "overview",
        "executive summary", "introduction",
    ]),

    AliasEntry("education", aliases=[
        "education", "educational background", "academic background",
        "academic history", "educational qualifications", "qualifications",
        "academics", "scholastics", "schooling", "degrees",
        "academic credentials", "educational experience",
    ]),

    AliasEntry("experience", aliases=[
        "experience", "work experience", "professional experience",
        "employment history", "employment", "work history",
        "career history", "professional background", "internships",
        "internship experience", "industry experience", "relevant experience",
        "job experience", "positions held", "professional work experience",
        "work", "jobs",
    ]),

    AliasEntry("projects", aliases=[
        "projects", "personal projects", "academic projects",
        "key projects", "notable projects", "project work",
        "project experience", "technical projects", "selected projects",
        "side projects", "portfolio",
    ]),

    AliasEntry("open_source", aliases=[
        "open source", "open source contributions", "open-source",
        "github contributions", "open source projects",
    ]),

    AliasEntry("leadership", aliases=[
        "leadership", "leadership experience", "leadership & activities",
        "positions of responsibility", "extracurricular activities",
        "extracurriculars", "activities", "campus involvement",
        "student activities", "co-curricular activities",
        "co-curriculars", "clubs and activities", "involvement",
        "volunteer experience", "volunteering", "community service",
        "community involvement", "social work", "nss", "ncc",
        "student leadership", "organizational roles",
        "responsibilities", "roles and responsibilities",
    ]),

    AliasEntry("achievements", aliases=[
        "achievements", "achievements and activities", "awards", "honors",
        "awards and honors", "awards & scholarships", "recognitions",
        "key achievements", "notable achievements",
    ]),

    AliasEntry("publications", aliases=[
        "publications", "research publications", "papers",
        "published papers", "articles", "journals", "conferences",
    ]),

    AliasEntry("hackathons", aliases=[
        "hackathons", "hackathon experience", "competitions",
        "coding competitions", "programming contests", "competitive programming",
    ]),

    AliasEntry("research", aliases=[
        "research", "research experience", "research projects",
        "academic research",
    ]),

    AliasEntry("tech_blogs", aliases=[
        "tech blogs", "technical blogs", "blogging", "articles and blogs",
        "writing", "technical writing",
    ]),

    AliasEntry("certifications", aliases=[
        "certifications", "certification", "certificates",
        "professional certifications", "licenses and certifications",
        "licenses", "credentials", "accreditations",
        "courses", "online courses", "moocs", "training",
        "professional development", "continuing education",
        "additional qualifications", "awards and certifications",
    ]),

    AliasEntry("skills", aliases=[
        "skills", "technical skills", "core skills",
        "key skills", "skill set", "competencies",
        "core competencies", "technologies", "tools",
        "tools and technologies", "programming languages",
        "languages", "technical expertise", "expertise",
        "areas of expertise", "specializations", "proficiencies",
        "technical proficiencies", "software", "frameworks",
    ]),
]

# Build fast lookup dict: normalized_alias → canonical_name
def normalize_alias(text: str) -> str:
    return text.lower().replace("-", "").replace(" ", "").rstrip(":")

ALIAS_LOOKUP: Dict[str, str] = {}
ALIAS_WEIGHTS: Dict[str, float] = {}

for entry in SECTION_REGISTRY:
    for alias in entry.aliases:
        norm = normalize_alias(alias)
        ALIAS_LOOKUP[norm] = entry.canonical_name
        ALIAS_WEIGHTS[norm] = entry.weight
