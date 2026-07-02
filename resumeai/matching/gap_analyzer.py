"""
matching/gap_analyzer.py — Skill Gap Analyzer (Phase 4.2 + hotfix + ontology wiring).

Fixes:
- Scans other_section.blocks (catches Strengths & Interests, etc.)
- MySQL/MariaDB → SQL inference (database implies query language)
- PostgreSQL → SQL inference
- Node.js → JavaScript inference
- All 12 resume sections covered
- raw_lines fallback for pre-patch stored parses

Ontology wiring (see resumeai/ontology/registry.py):
- The old local SKILL_ALIASES / SKILL_IMPLICATIONS dicts are gone. Alias
  normalization now goes through the shared registry (single source of
  truth, same one jd_parser.py and extractors/projects.py use).
- Skill-to-skill matching now has an explicit relationship-graph tier
  between exact/alias matching and fuzzy string matching: two canonical
  skills that are connected in the ontology's relationship graph (e.g.
  JWT -> Authentication, EC2 -> AWS) match at that tier, before falling
  through to fuzzy matching and then ONNX semantic similarity. This tier
  is O(1) (a precomputed closure lookup), so it's essentially free and
  actually *reduces* how often the (much more expensive) embedding path
  gets hit.
- Inferred project/experience capabilities (extractors/projects.py's
  `inferred_capabilities`, e.g. "Authentication" inferred from "implemented
  login using JWT") are now folded into the resume's skill evidence -- this
  data was already being computed but was previously never read by the
  matcher.
"""
from __future__ import annotations

from typing import Dict, Any, List, Set
from rapidfuzz import fuzz

from .schemas import SkillGapResult
from .jd_parser import extract_skills_from_text, normalize_skill
from resumeai.ontology.registry import get_registry

_registry = get_registry()

# Relationship-graph match tiers (see registry._build_closure). Chosen so:
#   - strong forward-hierarchical edges (child implies parent, e.g. JWT->
#     Authentication, weight ~0.9) and sibling edges (JWT<->OAuth, ~0.85)
#     count as a match;
#   - weak reverse-hierarchical edges (generic "Authentication" on its own
#     implying a *specific* mechanism like JWT, weight ~0.45) do NOT count
#     as a full match -- this is the precision guardrail from the
#     architecture review: a JD asking for one specific technology shouldn't
#     get full credit from a resume that only shows a related-but-different
#     one.
_RELATIONSHIP_MATCH_THRESHOLD = 0.55
# Family-level match (lowest-precision tier, e.g. React & Vue.js share the
# "Frontend" family) is intentionally NOT used as a boolean match source
# here -- it's too coarse to safely equate two different frameworks. It's
# reserved for future partial-credit/recommendation use, not hard matching.

# Embedding-similarity threshold for the last-resort semantic match tier
# (only reached for JD skills that fail exact/alias/relationship-graph/fuzzy
# matching -- see _is_match and generate_skill_gap below). Kept at the
# original 0.75 value: resumeai/matching/eval_threshold.py implements the
# precision/recall/F1 sweep methodology to measure a better value against
# real labeled data, but that script requires downloading the ONNX model
# (network access to huggingface.co), which was not available in the
# environment this change was implemented in. Run
# `python -m resumeai.matching.eval_threshold` in an environment with model
# access before adjusting this constant -- see that file's docstring for
# the full methodology and the labeled-dataset caveat.
SKILL_SEMANTIC_THRESHOLD = 0.75

GENERIC_WORDS = {
    "backend", "developer", "engineer", "intern", "requirements",
    "responsibilities", "candidate", "position", "role", "team",
    "work", "experience", "company", "software", "data",
}


def _norm(skill: str) -> str:
    """Lowercase + strip + ontology alias lookup (delegates to the shared registry)."""
    s = skill.lower().strip()
    canonical = _registry.normalize_skill(s)
    return canonical.lower() if canonical else s


def _scan_text(*parts) -> Set[str]:
    """Helper: join non-None text parts and extract canonical skills."""
    text = " ".join(p for p in parts if p)
    return set(extract_skills_from_text(text)) if text.strip() else set()


def _expand_with_implications(found: Set[str]) -> Set[str]:
    """
    Expand a skill set with implied (strong forward-hierarchical) skills.
    e.g. MySQL → add SQL; Node.js → add JavaScript; JWT → add Authentication.
    Uses the same precomputed relationship closure as the match-time
    relationship-graph tier, so this list never drifts out of sync with it.
    """
    implied: Set[str] = set()
    for skill in list(found):
        canonical = _registry.normalize_skill(skill)
        for related_skill, (weight, rclass) in _registry.closure_for(canonical).items():
            if rclass == "hierarchical" and weight >= _RELATIONSHIP_MATCH_THRESHOLD:
                implied.add(related_skill)
            elif rclass == "sibling" and weight >= _RELATIONSHIP_MATCH_THRESHOLD:
                # Siblings (JWT/OAuth/Bearer Token) don't imply each other as
                # literal possessions, but they DO all imply their shared
                # parent (handled by the hierarchical edges above); nothing
                # additional to add here.
                continue
    return found | implied


def extract_all_resume_skills(parsed_resume: Dict[str, Any]) -> Set[str]:
    """
    Extract ALL canonical skills from a parsed resume dict.
    Covers every section including:
    - Skills (flat_list + categories)
    - Projects (technologies + bullets + raw_lines fallback)
    - Experience
    - Certifications
    - Leadership
    - Achievements
    - Hackathons
    - Research / Publications
    - Open Source
    - Technical Blogs
    - Education (field + coursework)
    - Summary
    - other_section.blocks (catches Strengths & Interests etc.)

    Also expands with implied skills (MySQL→SQL, Node.js→JavaScript).
    """
    found: Set[str] = set()

    # ── 1. Skills section ─────────────────────────────────────────────────
    skills_sec = parsed_resume.get("skills", {}) or {}
    flat_list = skills_sec.get("flat_list", []) or []
    for s in flat_list:
        if s:
            found.add(s)
            found.update(extract_skills_from_text(s))

    for cat in (skills_sec.get("categories", []) or []):
        # Support both "name" and "category" keys (extractor uses "category")
        for cat_skill in (cat.get("skills", []) or []):
            if cat_skill:
                found.add(cat_skill)
                found.update(extract_skills_from_text(cat_skill))
        # Scan category name too (e.g. "Frameworks & Tools")
        cat_name = cat.get("name", "") or cat.get("category", "") or ""
        if cat_name:
            found.update(extract_skills_from_text(cat_name))

    # Also scan skills raw_lines if present
    for raw in (skills_sec.get("raw_lines", []) or []):
        if raw:
            found.update(extract_skills_from_text(raw))

    # ── 2. Projects (with raw_lines fallback for tech recovery) ───────────
    for proj in (parsed_resume.get("projects", []) or []):
        for t in (proj.get("technologies", []) or []):
            if t:
                found.add(t)
                found.update(extract_skills_from_text(str(t)))

        proj_text = " ".join(filter(None, [
            proj.get("name", ""),
            proj.get("description", ""),
            " ".join(proj.get("bullets", []) or []),
            " ".join(str(x) for x in (proj.get("technologies", []) or [])),
        ]))
        found.update(extract_skills_from_text(proj_text))

        raw_lines = proj.get("raw_lines", []) or []
        if raw_lines:
            raw_text = " ".join(raw_lines)
            found.update(extract_skills_from_text(raw_text))

        # Rule-engine-inferred capabilities (e.g. "implemented login using
        # JWT" -> "Authentication") -- computed by extractors/projects.py
        # but previously discarded before reaching the matcher.
        for cap in (proj.get("inferred_capabilities", []) or []):
            if cap:
                found.add(cap)

    # ── 3. Experience ─────────────────────────────────────────────────────
    for exp in (parsed_resume.get("experience", []) or []):
        found.update(_scan_text(
            exp.get("title", ""),
            exp.get("company", ""),
            exp.get("description", ""),
            " ".join(exp.get("bullets", []) or []),
        ))

    # ── 4. Certifications ─────────────────────────────────────────────────
    for cert in (parsed_resume.get("certifications", []) or []):
        found.update(_scan_text(
            cert.get("name", ""),
            cert.get("issuer", ""),
            cert.get("description", ""),
        ))

    # ── 5. Leadership ─────────────────────────────────────────────────────
    for lead in (parsed_resume.get("leadership", []) or []):
        found.update(_scan_text(
            lead.get("role", ""),
            lead.get("organization", ""),
            " ".join(lead.get("bullets", []) or []),
            lead.get("description", ""),
        ))

    # ── 6. Achievements ───────────────────────────────────────────────────
    for ach in (parsed_resume.get("achievements", []) or []):
        if isinstance(ach, str):
            found.update(extract_skills_from_text(ach))
        elif isinstance(ach, dict):
            found.update(_scan_text(
                ach.get("title", ""),
                ach.get("description", ""),
            ))

    # ── 7. Hackathons ─────────────────────────────────────────────────────
    for hack in (parsed_resume.get("hackathons", []) or []):
        if isinstance(hack, dict):
            found.update(_scan_text(
                hack.get("name", ""),
                hack.get("description", ""),
                " ".join(hack.get("technologies", []) or []),
                " ".join(hack.get("bullets", []) or []),
            ))

    # ── 8. Research / Publications ────────────────────────────────────────
    for res in (parsed_resume.get("research", []) or []):
        if isinstance(res, dict):
            found.update(_scan_text(
                res.get("title", ""),
                res.get("description", ""),
                " ".join(res.get("technologies", []) or []),
            ))

    for pub in (parsed_resume.get("publications", []) or []):
        if isinstance(pub, dict):
            found.update(_scan_text(
                pub.get("title", ""),
                pub.get("abstract", ""),
                pub.get("description", ""),
            ))

    # ── 9. Open Source ────────────────────────────────────────────────────
    for oss in (parsed_resume.get("open_source", []) or []):
        if isinstance(oss, dict):
            found.update(_scan_text(
                oss.get("name", ""),
                oss.get("description", ""),
                " ".join(oss.get("technologies", []) or []),
                " ".join(oss.get("bullets", []) or []),
            ))

    # ── 10. Technical Blogs ───────────────────────────────────────────────
    for blog in (parsed_resume.get("blogs", []) or []):
        if isinstance(blog, dict):
            found.update(_scan_text(blog.get("title", ""), blog.get("description", "")))
        elif isinstance(blog, str):
            found.update(extract_skills_from_text(blog))

    # ── 11. Coursework / Education ────────────────────────────────────────
    for edu in (parsed_resume.get("education", []) or []):
        if isinstance(edu, dict):
            coursework = edu.get("coursework", "") or ""
            found.update(_scan_text(
                edu.get("field_of_study", ""),
                coursework if isinstance(coursework, str) else " ".join(coursework),
            ))

    # ── 12. Summary ───────────────────────────────────────────────────────
    summary = parsed_resume.get("summary", "") or ""
    if summary:
        found.update(extract_skills_from_text(summary))

    # ── 13. other_section.blocks ─────────────────────────────────────────
    # This catches "Strengths & Interests", "Achievements", and any other
    # unclassified sections from the parser.
    other_sec = parsed_resume.get("other_section", {}) or {}
    for block in (other_sec.get("blocks", []) or []):
        if isinstance(block, dict):
            # Scan block title + all content lines
            block_text = " ".join(filter(None, [
                block.get("title", ""),
                block.get("content", ""),
                " ".join(block.get("lines", []) or []),
                " ".join(block.get("bullets", []) or []),
            ]))
            if block_text.strip():
                found.update(extract_skills_from_text(block_text))
        elif isinstance(block, str):
            found.update(extract_skills_from_text(block))

    found.discard("")
    found.discard(None)

    # ── Expand with implied skills ────────────────────────────────────────
    found = _expand_with_implications(found)

    return found


def _is_match(jd_skill: str, resume_skills: Set[str], resume_skills_norm: Set[str]) -> bool:
    """
    Check if a JD skill matches any resume skill via, in ascending cost order:
    1. Exact string match (raw)
    2. Exact normalized/alias match
    3. Relationship-graph match (O(1) precomputed closure lookup -- e.g.
       JD wants "Authentication", resume has "JWT"; JD wants "EC2", resume
       has "AWS")
    4. Fuzzy string matching (>=82 token sort ratio)
    5. Semantic similarity match (moved to bulk operation in generate_skill_gap,
       only reached for skills that fail all of the above -- steps 1-4 resolve
       the large majority of real matches at near-zero cost, so the
       relatively expensive embedding path is only hit for genuine long tail)
    """
    raw_jd = jd_skill.strip()
    jd_norm = _norm(jd_skill)
    jd_canonical = _registry.normalize_skill(jd_skill)

    # 1. Raw exact match
    if raw_jd in resume_skills:
        return True

    # 2. Normalized exact alias match
    if jd_norm in resume_skills_norm:
        return True

    # 3. Relationship-graph match (see module docstring for the precision
    # rationale behind _RELATIONSHIP_MATCH_THRESHOLD).
    #
    # IMPORTANT: the lookup direction matters. We ask "starting from what the
    # candidate actually HAS (resume_skill), does its closure reach the JD's
    # requirement (jd_canonical), and at what confidence?" -- not the other
    # way around. This is what makes the asymmetric hierarchical weighting
    # work as intended: resume=JWT / JD=Authentication (generic) matches
    # strongly (child evidence -> parent requirement, ~0.9), while
    # resume=Python / JD=Django (specific) does NOT auto-match just because
    # Django's own closure happens to reach Python at full weight.
    for resume_skill in resume_skills:
        resume_canonical = _registry.normalize_skill(resume_skill)
        hit = _registry.closure_for(resume_canonical).get(jd_canonical)
        if hit and hit[0] >= _RELATIONSHIP_MATCH_THRESHOLD:
            return True

    # 4. Fuzzy match on normalized strings (lowered threshold: 82)
    for rs_norm in resume_skills_norm:
        score = fuzz.token_sort_ratio(jd_norm, rs_norm)
        if score >= 82:
            return True

    # 5. Semantic similarity match moved to bulk operation in generate_skill_gap

    return False


def generate_skill_gap(
    parsed_resume: Dict[str, Any],
    parsed_jd: Any,
    cache: dict = None,
) -> SkillGapResult:
    """Compute skill gap between a parsed resume and a parsed JD."""
    if isinstance(parsed_jd, dict):
        required = parsed_jd.get("required_skills", [])
        preferred = parsed_jd.get("preferred_skills", [])
    else:
        required = list(getattr(parsed_jd, "required_skills", []))
        preferred = list(getattr(parsed_jd, "preferred_skills", []))

    required = [s for s in required if _norm(s) not in GENERIC_WORDS]
    preferred = [s for s in preferred if _norm(s) not in GENERIC_WORDS]

    resume_skills_raw = extract_all_resume_skills(parsed_resume)
    resume_skills_norm = {_norm(s) for s in resume_skills_raw}

    matched: List[str] = []
    missing: List[str] = []

    if not required and preferred:
        benchmark_skills = preferred
        is_preferred_only = True
    else:
        benchmark_skills = required
        is_preferred_only = False

    unmatched_benchmark = []
    for jd_skill in benchmark_skills:
        if _is_match(jd_skill, resume_skills_raw, resume_skills_norm):
            matched.append(jd_skill)
        else:
            unmatched_benchmark.append(jd_skill)

    # Batched Semantic Matching
    if unmatched_benchmark:
        try:
            from .embedding_engine import is_available, batch_encode_with_cache, cosine_similarity_matrix
            if is_available() and cache is not None:
                jd_vecs = batch_encode_with_cache(unmatched_benchmark, cache)
                rs_list = list(resume_skills_raw)
                if rs_list:
                    rs_vecs = batch_encode_with_cache(rs_list, cache)
                    sim_matrix = cosine_similarity_matrix(jd_vecs, rs_vecs)
                    
                    for i, jd_skill in enumerate(unmatched_benchmark):
                        if sim_matrix[i].max() >= SKILL_SEMANTIC_THRESHOLD:
                            matched.append(jd_skill)
                        else:
                            missing.append(jd_skill)
                            
                    import gc
                    del jd_vecs
                    del rs_vecs
                    del sim_matrix
                    gc.collect()
                else:
                    missing.extend(unmatched_benchmark)
            else:
                missing.extend(unmatched_benchmark)
        except Exception:
            missing.extend(unmatched_benchmark)

    recommended: List[str] = []
    if not is_preferred_only:
        unmatched_pref = []
        for pref_skill in preferred:
            if not _is_match(pref_skill, resume_skills_raw, resume_skills_norm):
                unmatched_pref.append(pref_skill)
                
        if unmatched_pref:
            try:
                from .embedding_engine import is_available, batch_encode_with_cache, cosine_similarity_matrix
                if is_available() and cache is not None:
                    pref_vecs = batch_encode_with_cache(unmatched_pref, cache)
                    rs_list = list(resume_skills_raw)
                    if rs_list:
                        rs_vecs = batch_encode_with_cache(rs_list, cache)
                        sim_matrix = cosine_similarity_matrix(pref_vecs, rs_vecs)
                        
                        for i, pref_skill in enumerate(unmatched_pref):
                            if sim_matrix[i].max() < SKILL_SEMANTIC_THRESHOLD:
                                recommended.append(pref_skill)
                        import gc
                        del pref_vecs
                        del rs_vecs
                        del sim_matrix
                        gc.collect()
                    else:
                        recommended.extend(unmatched_pref)
                else:
                    recommended.extend(unmatched_pref)
            except Exception:
                recommended.extend(unmatched_pref)

    total = len(benchmark_skills)
    match_pct = round((len(matched) / total * 100), 1) if total > 0 else 0.0

    return SkillGapResult(
        matched_skills=matched,
        missing_skills=missing,
        recommended_skills=recommended[:10],
        match_percentage=match_pct,
    )
