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

import logging
from typing import Dict, Any, List, Optional, Union
from resumeai.core.skill_intelligence import SkillIntelligenceEngine

def _compute_skill_score(
    gap: Any,
    parsed_jd: Any,
    debug: Dict,
) -> Optional[float]:
    """Skill overlap score 0-100 utilizing domain weights and skill evidence confidence. Returns None if JD has no skills."""
    required = list(getattr(parsed_jd, "required_skills", []))
    preferred = list(getattr(parsed_jd, "preferred_skills", []))

    if not required and not preferred:
        debug["skill_match_note"] = "No skills extracted from JD — skill match is N/A."
        return None

    matched_count = len(gap.matched_skills)
    total_required = len(required)
    
    # Adaptive Scoring based on Domain Classification weights
    domain_class = getattr(parsed_jd, "domain_classification", {})
    weights = domain_class.get("weights", {}) if domain_class else {}
    
    engine = SkillIntelligenceEngine()
    
    # Calculate score using confidence logic
    score_acc = 0.0
    total_weight = 0.0
    
    evidence_map = {ev.skill: ev for ev in (gap.skill_evidence or [])}
    contributions = []
    
    # Required skills
    for req in required:
        norm = engine.normalize_skill(req)
        weight = weights.get(norm, 10.0) # Default weight 10
        total_weight += weight
        
        if req in evidence_map:
            conf = evidence_map[req].confidence / 100.0
            pts = weight * conf
            score_acc += pts
            contributions.append(f"+{round(pts, 1)} {req}")
        else:
            contributions.append(f"-{round(weight, 1)} {req} Missing")
            
    base = (score_acc / total_weight * 100) if total_weight > 0 else 50.0

    # Preferred bonus (up to +15)
    pref_bonus = 0.0
    if preferred:
        pref_acc = 0.0
        pref_weight_total = 0.0
        for pref in preferred:
            norm = engine.normalize_skill(pref)
            weight = weights.get(norm, 8.0)
            pref_weight_total += weight
            if pref in evidence_map:
                conf = evidence_map[pref].confidence / 100.0
                pref_acc += (weight * conf)
                
        if pref_weight_total > 0:
            pref_bonus = (pref_acc / pref_weight_total) * 15
            
        base = min(100.0, base + pref_bonus)

    debug["skill_match_score"] = round(base, 1)
    debug["required_matched"] = f"{matched_count}/{total_required}"
    debug["preferred_bonus"] = round(pref_bonus, 1)
    debug["score_contributions"] = contributions
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
    responsibilities = getattr(parsed_jd, "responsibilities", [])
    jd_keywords = getattr(parsed_jd, "keywords", [])

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
    exp_reqs = getattr(parsed_jd, "experience_requirements", [])

    exp_text = " ".join(exp_reqs).lower() if exp_reqs else ""
    
    # Try to find required years in JD
    jd_years = None
    matches = re.findall(r"(\d+)(?:\+|-|\s+to\s+\d+)?\s*(?:years?|yrs?)", exp_text)
    if matches:
        jd_years = max(int(m) for m in matches)

    is_entry = any(kw in exp_text for kw in [
        "entry", "junior", "fresher", "fresh graduate", "0-1", "0-2", "internship", "intern"
    ])
    if is_entry and not jd_years:
        jd_years = 0

    from resumeai.ats.exporters import _estimate_years_experience
    resume_years = _estimate_years_experience(experience)

    score = 30.0  # base

    # Base heuristic if no jd_years could be extracted
    if jd_years is None:
        if len(experience) >= 3:  score += 30
        elif len(experience) == 2: score += 22
        elif len(experience) == 1: score += 14

        if len(projects) >= 3:   score += 25
        elif len(projects) >= 2: score += 18
        elif len(projects) >= 1: score += 10

        if is_entry:
            score = min(100, score + 15)

        return round(min(100.0, score), 1)

    # Compare against jd_years
    if resume_years is None:
        # Give partial credit based on projects if fresher
        if len(projects) >= 2:
            resume_years = 1
        else:
            resume_years = 0

    if resume_years >= jd_years:
        score = 100.0
    else:
        # Scale proportionally but don't drop below 20 for having something
        ratio = resume_years / jd_years if jd_years > 0 else 1.0
        score = 20.0 + (ratio * 80.0)

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


def _compute_education_score(parsed_resume: Dict[str, Any], parsed_jd: ParsedJD) -> Union[float, str]:
    edu_reqs = getattr(parsed_jd, "education_requirements", [])
    if not edu_reqs:
        return "Not Applicable"

    education = parsed_resume.get("education", [])
    if not education:
        return 35.0

    score = 40.0
    
    edu_text = " ".join(edu_reqs).lower() if edu_reqs else ""
    
    jd_requires_master = any(kw in edu_text for kw in ["master", "m.s.", "m.tech", "mtech", "ms"])
    jd_requires_phd = any(kw in edu_text for kw in ["phd", "ph.d", "doctorate"])

    has_bachelor = False
    has_master = False
    has_phd = False
    has_cs_field = False
    max_gpa_score = 0.0

    for edu in education:
        combined = f"{edu.get('degree','')}{edu.get('field_of_study','')}".lower()
        if any(kw in combined for kw in ["phd", "ph.d", "doctorate"]):
            has_phd = True
            has_master = True
            has_bachelor = True
        elif any(kw in combined for kw in ["m.tech", "mtech", "master", "m.s.", "m.e.", "m.sc"]):
            has_master = True
            has_bachelor = True
        elif any(kw in combined for kw in ["b.tech", "btech", "bachelor", "b.s.", "b.e.", "b.sc", "be ", " be"]):
            has_bachelor = True

        if any(kw in combined for kw in CS_FIELDS):
            has_cs_field = True
            
        gpa_str = edu.get("gpa", "") or ""
        if gpa_str:
            try:
                nums = re.findall(r"[\d.]+", gpa_str)
                if nums:
                    gpa_val = float(nums[0])
                    if gpa_val > 4.0:  # /10 scale
                        if gpa_val >= 9.0:   max_gpa_score = max(max_gpa_score, 15)
                        elif gpa_val >= 8.0: max_gpa_score = max(max_gpa_score, 10)
                        elif gpa_val >= 7.0: max_gpa_score = max(max_gpa_score, 5)
                    else:              # /4 scale
                        if gpa_val >= 3.7:   max_gpa_score = max(max_gpa_score, 15)
                        elif gpa_val >= 3.3: max_gpa_score = max(max_gpa_score, 10)
            except (ValueError, IndexError):
                pass

    if jd_requires_phd:
        if has_phd: score += 20
        elif has_master: score += 10
        elif has_bachelor: score += 5
    elif jd_requires_master:
        if has_master or has_phd: score += 20
        elif has_bachelor: score += 10
    else:
        # Default expects bachelor
        if has_bachelor or has_master or has_phd: score += 20

    if has_cs_field:
        score += 25

    score += max_gpa_score

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

        # ── Unwrap frontend payload if wrapped ────────────────────────────
        if "result" in parsed_resume and isinstance(parsed_resume["result"], dict) and "version" in parsed_resume["result"]:
            parsed_resume = parsed_resume["result"]

        # ── Skill gap (used by multiple components) ───────────────────────
        gap = generate_skill_gap(parsed_resume, parsed_jd)

        # ── Component scores ──────────────────────────────────────────────
        skill_score  = _compute_skill_score(gap, parsed_jd, debug)
        sem_score    = _compute_semantic_score(parsed_resume, parsed_jd, debug)
        exp_score    = _compute_experience_score(parsed_resume, parsed_jd)
        edu_score    = _compute_education_score(parsed_resume, parsed_jd)

        # ── Weighted overall ──────────────────────────────────────────────
        active_wt = sum(self.WEIGHTS.values())
        if skill_score is None:
            active_wt -= self.WEIGHTS["skills"]
            skill_score_val = 0.0
        else:
            skill_score_val = skill_score

        if edu_score == "Not Applicable":
            active_wt -= self.WEIGHTS["education"]
            edu_score_val = 0.0
            c_education = "Not Applicable"
        else:
            edu_score_val = edu_score
            c_education = round((edu_score * self.WEIGHTS["education"]) / active_wt, 1) if active_wt > 0 else 0

        overall = (
            skill_score_val  * self.WEIGHTS["skills"] * (0 if skill_score is None else 1)
            + sem_score      * self.WEIGHTS["semantic"]
            + exp_score      * self.WEIGHTS["experience"]
            + edu_score_val  * self.WEIGHTS["education"] * (0 if edu_score == "Not Applicable" else 1)
        ) / active_wt if active_wt > 0 else 0.0

        w_skills = f"{(self.WEIGHTS['skills']/active_wt)*100:.0f}%" if skill_score is not None and active_wt > 0 else "0%"
        w_semantic = f"{(self.WEIGHTS['semantic']/active_wt)*100:.0f}%" if active_wt > 0 else "0%"
        w_experience = f"{(self.WEIGHTS['experience']/active_wt)*100:.0f}%" if active_wt > 0 else "0%"
        w_education = f"{(self.WEIGHTS['education']/active_wt)*100:.0f}%" if edu_score != "Not Applicable" and active_wt > 0 else "0%"
        
        c_skills = round((skill_score * self.WEIGHTS["skills"]) / active_wt, 1) if skill_score is not None and active_wt > 0 else None
        c_semantic = round((sem_score * self.WEIGHTS["semantic"]) / active_wt, 1) if active_wt > 0 else 0
        c_experience = round((exp_score * self.WEIGHTS["experience"]) / active_wt, 1) if active_wt > 0 else 0

        overall = int(round(min(100.0, max(0.0, overall))))

        # ── Roadmap ───────────────────────────────────────────────────────
        from .roadmap_generator import generate_learning_roadmap
        roadmap = generate_learning_roadmap(gap.missing_skills)

        # ── Debug info (full traceability) ────────────────────────────────
        engine = SkillIntelligenceEngine()
        evidence_list = getattr(gap, "skill_evidence", [])
        evidence_map = {e.skill: e for e in evidence_list} if evidence_list else {}
        
        tech_depth = len(evidence_map) / 5.0
        proj_diversity = len(parsed_resume.get("projects", []))
        backend_strength = sum(1 for e in evidence_map.values() if e.confidence > 90 and engine._skill_to_families.get(e.skill) and "Backend" in engine._skill_to_families[e.skill])
        cloud_readiness = sum(1 for e in evidence_map.values() if e.confidence > 80 and engine._skill_to_families.get(e.skill) and "Cloud" in engine._skill_to_families[e.skill])
        
        resume_metrics = {
            "Technical Depth": min(10.0, tech_depth),
            "Project Diversity": min(10.0, proj_diversity * 2.5),
            "Backend Strength": min(10.0, backend_strength * 2.0),
            "Cloud Readiness": min(10.0, cloud_readiness * 3.3),
            "AI Readiness": min(10.0, sum(1 for e in evidence_map.values() if "AI" in engine._skill_to_families.get(e.skill, set())) * 3.3),
            "DevOps Readiness": min(10.0, sum(1 for e in evidence_map.values() if "DevOps" in engine._skill_to_families.get(e.skill, set())) * 3.3)
        }

        resume_skills_all = [e.skill for e in evidence_list] if evidence_list else []

        debug_info = {
            "jd_skills":          list(getattr(parsed_jd, "required_skills", [])),
            "resume_skills":      resume_skills_all,
            "resume_metrics":     resume_metrics,
            "matched_skills":     gap.matched_skills,
            "missing_skills":     gap.missing_skills,
            "skill_match_score":  skill_score if skill_score is not None else "N/A",
            "semantic_similarity": debug.get("semantic_similarity", sem_score),
            "experience_score":   exp_score,
            "education_score":    edu_score,
            "weights": {
                "skills":     w_skills,
                "semantic":   w_semantic,
                "experience": w_experience,
                "education":  w_education,
            },
            "weighted_contributions": {
                "skills":     c_skills if c_skills is not None else "N/A",
                "semantic":   c_semantic,
                "experience": c_experience,
                "education":  c_education,
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
            missing_skills_analysis=getattr(gap, 'missing_skills_analysis', None),
            skill_evidence=getattr(gap, 'skill_evidence', None),
            recommended_skills=gap.recommended_skills,
            recommended_learning=roadmap,
            debug_info=debug_info,
        )
