"""
matching/skill_matcher.py — Resume ↔ Job Matching Engine v2.

Computes a weighted match score from 4 components:
  - Skill Match (40%): canonical skill overlap with fuzzy fallback
  - Semantic Similarity (30%): MiniLM embedding similarity
  - Experience Alignment (15%): internship/project/years heuristics
  - Education Alignment (15%): degree and field relevance

Adds full debug_info to every result for traceability.
"""
from __future__ import annotations

import re
from typing import Dict, Any, List

from .schemas import MatchResult, ComponentScores
from .jd_parser import ParsedJD, extract_skills_from_text
from .gap_analyzer import (
    generate_skill_gap,
    extract_all_resume_skills,
    _norm,
)


# ── Grade boundaries ──────────────────────────────────────────────────────────
def _score_to_grade(score: int) -> str:
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B+"
    if score >= 60: return "B"
    if score >= 50: return "C"
    return "D"


# ── Component 1: Skill Match (40%) ────────────────────────────────────────────

def _compute_skill_score(
    parsed_resume: Dict[str, Any],
    parsed_jd: ParsedJD,
    debug: Dict,
) -> float:
    """Skill overlap score 0-100 with partial credit for preferred."""
    required = list(parsed_jd.required_skills)
    preferred = list(parsed_jd.preferred_skills)

    if not required and not preferred:
        debug["skill_match_note"] = "No skills specified in JD — neutral 60"
        return 60.0

    gap = generate_skill_gap(parsed_resume, parsed_jd)
    matched_count = len(gap.matched_skills)
    total_required = len(required)

    base = (matched_count / total_required * 100) if total_required > 0 else 50.0

    # Preferred bonus (up to +15)
    pref_bonus = 0.0
    if preferred:
        resume_norm = {_norm(s) for s in extract_all_resume_skills(parsed_resume)}
        from .gap_analyzer import _fuzzy_match_skill
        pref_matched = sum(1 for s in preferred if _fuzzy_match_skill(s, resume_norm))
        pref_bonus = (pref_matched / len(preferred)) * 15
        base = min(100.0, base + pref_bonus)

    debug["skill_match_score"] = round(base, 1)
    debug["required_matched"] = f"{matched_count}/{total_required}"
    debug["preferred_bonus"] = round(pref_bonus, 1)
    return round(base, 1)


# ── Component 2: Semantic Similarity (30%) ────────────────────────────────────

def _build_resume_corpus(parsed_resume: Dict[str, Any]) -> List[str]:
    """Build text snippets from resume for semantic comparison."""
    snippets: List[str] = []
    summary = parsed_resume.get("summary", "") or ""
    if summary.strip():
        snippets.append(summary.strip())

    for exp in parsed_resume.get("experience", []):
        bullets = exp.get("bullets", [])
        if bullets:
            snippets.append(" ".join(bullets[:5]))
        if exp.get("description"):
            snippets.append(exp["description"][:300])

    for proj in parsed_resume.get("projects", []):
        parts = [proj.get("name", "")]
        if proj.get("description"):
            parts.append(proj["description"])
        if proj.get("bullets"):
            parts.extend(proj["bullets"][:3])
        if proj.get("technologies"):
            parts.append("Technologies: " + ", ".join(proj["technologies"][:8]))
        text = " ".join(filter(None, parts))
        if text.strip():
            snippets.append(text)

    skills_flat = parsed_resume.get("skills", {}).get("flat_list", [])
    if skills_flat:
        snippets.append("Technical skills: " + ", ".join(skills_flat[:25]))

    return [s for s in snippets if len(s.strip()) > 15]


def _compute_semantic_score(
    parsed_resume: Dict[str, Any],
    parsed_jd: ParsedJD,
    debug: Dict,
) -> float:
    """Semantic similarity score 0-100 using MiniLM embeddings with keyword fallback."""
    responsibilities = parsed_jd.responsibilities
    jd_keywords = parsed_jd.keywords

    if not responsibilities and not jd_keywords:
        # No JD text to compare — fall back to skill-based estimate
        skill_match = debug.get("skill_match_score", 50)
        fallback = min(90.0, skill_match * 0.9 + 10)
        debug["semantic_note"] = "No JD responsibilities — skill-based estimate"
        debug["semantic_similarity"] = round(fallback, 1)
        return round(fallback, 1)

    resume_snippets = _build_resume_corpus(parsed_resume)
    if not resume_snippets:
        debug["semantic_note"] = "Empty resume corpus"
        debug["semantic_similarity"] = 20.0
        return 20.0

    query_texts: List[str] = []
    if responsibilities:
        query_texts.extend(responsibilities[:10])
    if jd_keywords:
        query_texts.append("Skills required: " + ", ".join(jd_keywords[:25]))

    try:
        from .embedding_engine import max_similarity_scores
        scores = max_similarity_scores(query_texts, resume_snippets)
        if not scores:
            raise ValueError("empty scores")
        avg_sim = sum(scores) / len(scores)
        # Scale [0,1] → [0,100] with a 1.15x boost for partial semantic matches
        result = round(min(100.0, avg_sim * 100 * 1.15), 1)
        debug["semantic_note"] = "MiniLM embedding"
        debug["semantic_similarity"] = result
        return result
    except Exception as e:
        fallback = _semantic_fallback(resume_snippets, query_texts)
        debug["semantic_note"] = f"Keyword fallback (embedding error: {e})"
        debug["semantic_similarity"] = fallback
        return fallback


def _semantic_fallback(resume_snippets: List[str], jd_texts: List[str]) -> float:
    """Keyword overlap fallback when embeddings are unavailable."""
    resume_text = " ".join(resume_snippets).lower()
    jd_text = " ".join(jd_texts).lower()
    jd_words = set(re.findall(r"\b\w{4,}\b", jd_text))
    if not jd_words:
        return 45.0
    matches = sum(1 for w in jd_words if w in resume_text)
    return round(min(95.0, (matches / len(jd_words)) * 100 * 1.6), 1)


# ── Component 3: Experience Alignment (15%) ───────────────────────────────────

def _compute_experience_score(parsed_resume: Dict[str, Any], parsed_jd: ParsedJD) -> float:
    experience = parsed_resume.get("experience", [])
    projects = parsed_resume.get("projects", [])
    exp_reqs = parsed_jd.experience_requirements

    score = 30.0  # base

    # Formal experience
    if len(experience) >= 3:  score += 30
    elif len(experience) == 2: score += 22
    elif len(experience) == 1: score += 14

    # Projects count toward experience (freshers especially)
    if len(projects) >= 3:   score += 25
    elif len(projects) >= 2: score += 18
    elif len(projects) >= 1: score += 10

    if exp_reqs:
        exp_text = " ".join(exp_reqs).lower()
        is_entry = any(kw in exp_text for kw in [
            "entry", "junior", "fresher", "fresh graduate", "0-1", "0-2", "internship", "intern"
        ])
        if is_entry:
            score = min(100, score + 15)

    return round(min(100.0, score), 1)


# ── Component 4: Education Alignment (15%) ────────────────────────────────────

DEGREE_KEYWORDS = {
    "b.tech", "btech", "bachelor", "b.s.", "b.e.", "b.sc",
    "m.tech", "mtech", "master", "m.s.", "m.e.", "m.sc",
    "phd", "ph.d", "mba", "be ", " be",
}
CS_FIELDS = {
    "computer science", "cs", "software engineering", "information technology",
    "it", "electronics", "electrical", "ece", "cse", "information systems",
    "artificial intelligence", "data science", "mathematics", "statistics",
}


def _compute_education_score(parsed_resume: Dict[str, Any], parsed_jd: ParsedJD) -> float:
    education = parsed_resume.get("education", [])
    if not education:
        return 35.0

    score = 40.0

    for edu in education:
        combined = f"{edu.get('degree','')}{edu.get('field_of_study','')}".lower()
        if any(kw in combined for kw in DEGREE_KEYWORDS):
            score += 20
            break

    for edu in education:
        combined = f"{edu.get('degree','')}{edu.get('field_of_study','')}".lower()
        if any(kw in combined for kw in CS_FIELDS):
            score += 25
            break

    for edu in education:
        gpa_str = edu.get("gpa", "") or ""
        if gpa_str:
            try:
                nums = re.findall(r"[\d.]+", gpa_str)
                if nums:
                    gpa_val = float(nums[0])
                    if gpa_val > 4.0:  # /10 scale
                        if gpa_val >= 9.0:   score += 15
                        elif gpa_val >= 8.0: score += 10
                        elif gpa_val >= 7.0: score += 5
                    else:              # /4 scale
                        if gpa_val >= 3.7:   score += 15
                        elif gpa_val >= 3.3: score += 10
            except (ValueError, IndexError):
                pass
        break

    return round(min(100.0, score), 1)


# ── Main Matcher ──────────────────────────────────────────────────────────────

class SkillMatcher:
    """
    Resume ↔ Job Matching Engine v2.

    Returns debug_info for full score traceability:
      jd_skills, resume_skills, matched_skills, missing_skills,
      skill_match_score, semantic_similarity, final_match_score
    """
    WEIGHTS = {
        "skills":     0.40,
        "semantic":   0.30,
        "experience": 0.15,
        "education":  0.15,
    }

    def calculate_match_score(
        self,
        parsed_resume: Dict[str, Any],
        parsed_jd: ParsedJD,
    ) -> MatchResult:
        debug: Dict = {}

        # ── Skill gap (used by multiple components) ───────────────────────
        gap = generate_skill_gap(parsed_resume, parsed_jd)
        resume_skills_all = sorted(extract_all_resume_skills(parsed_resume))

        # ── Component scores ──────────────────────────────────────────────
        skill_score  = _compute_skill_score(parsed_resume, parsed_jd, debug)
        sem_score    = _compute_semantic_score(parsed_resume, parsed_jd, debug)
        exp_score    = _compute_experience_score(parsed_resume, parsed_jd)
        edu_score    = _compute_education_score(parsed_resume, parsed_jd)

        # ── Weighted overall ──────────────────────────────────────────────
        overall = (
            skill_score  * self.WEIGHTS["skills"]
            + sem_score  * self.WEIGHTS["semantic"]
            + exp_score  * self.WEIGHTS["experience"]
            + edu_score  * self.WEIGHTS["education"]
        )
        overall = int(round(min(100.0, max(0.0, overall))))

        # ── Roadmap ───────────────────────────────────────────────────────
        from .roadmap_generator import generate_learning_roadmap
        roadmap = generate_learning_roadmap(gap.missing_skills)

        # ── Debug info (full traceability) ────────────────────────────────
        debug_info = {
            "jd_skills":          list(parsed_jd.required_skills),
            "resume_skills":      resume_skills_all,
            "matched_skills":     gap.matched_skills,
            "missing_skills":     gap.missing_skills,
            "skill_match_score":  debug.get("skill_match_score", skill_score),
            "semantic_similarity": debug.get("semantic_similarity", sem_score),
            "experience_score":   exp_score,
            "education_score":    edu_score,
            "weights": {
                "skills":     f"{self.WEIGHTS['skills']*100:.0f}%",
                "semantic":   f"{self.WEIGHTS['semantic']*100:.0f}%",
                "experience": f"{self.WEIGHTS['experience']*100:.0f}%",
                "education":  f"{self.WEIGHTS['education']*100:.0f}%",
            },
            "weighted_contributions": {
                "skills":     round(skill_score * self.WEIGHTS["skills"], 1),
                "semantic":   round(sem_score   * self.WEIGHTS["semantic"], 1),
                "experience": round(exp_score   * self.WEIGHTS["experience"], 1),
                "education":  round(edu_score   * self.WEIGHTS["education"], 1),
            },
            "final_match_score":  overall,
            "semantic_note":      debug.get("semantic_note", ""),
        }

        return MatchResult(
            match_score=overall,
            match_grade=_score_to_grade(overall),
            component_scores=ComponentScores(
                skills=skill_score,
                semantic=sem_score,
                experience=exp_score,
                education=edu_score,
            ),
            matched_skills=gap.matched_skills,
            missing_skills=gap.missing_skills,
            recommended_skills=gap.recommended_skills,
            recommended_learning=roadmap,
            debug_info=debug_info,
        )
