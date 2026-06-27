"""
matching/gap_analyzer.py — Skill Gap Analyzer v3.0

Uses Central Skill Intelligence Engine for Semantic Inference and 4-Level Matching.
"""
from __future__ import annotations

from typing import Dict, Any, List

from .schemas import SkillGapResult, MissingSkill
from resumeai.core.skill_intelligence import SkillIntelligenceEngine
from resumeai.core.resume_intelligence import ResumeIntelligenceEngine

# ── Generic Words Filter ───────────────────────────────────────────────────────
GENERIC_WORDS = {
    "backend", "developer", "engineer", "intern", "requirements",
    "responsibilities", "candidate", "position", "role", "team",
    "work", "experience", "company", "software", "data"
}

def _norm(skill: str) -> str:
    s = skill.lower().strip()
    return s

def generate_skill_gap(
    parsed_resume: Dict[str, Any],
    parsed_jd: Any,  # ParsedJD or dict
) -> SkillGapResult:
    """
    Compute semantic skill gap between a parsed resume and a parsed JD.
    """
    skill_engine = SkillIntelligenceEngine()
    resume_engine = ResumeIntelligenceEngine()
    
    if isinstance(parsed_jd, dict):
        required = parsed_jd.get("required_skills", [])
        preferred = parsed_jd.get("preferred_skills", [])
    else:
        required = list(getattr(parsed_jd, "required_skills", []))
        preferred = list(getattr(parsed_jd, "preferred_skills", []))

    required = [s for s in required if _norm(s) not in GENERIC_WORDS]
    preferred = [s for s in preferred if _norm(s) not in GENERIC_WORDS]

    # Extract all evidence from the resume (Dictionary of Skill -> List[SkillEvidence])
    evidence_map = resume_engine.extract_resume_evidence(parsed_resume)
    
    matched: List[str] = []
    missing: List[str] = []
    skill_evidence = []
    missing_analysis = []

    if not required and preferred:
        benchmark_skills = preferred
        is_preferred_only = True
    else:
        benchmark_skills = required
        is_preferred_only = False
        
    domain_weights = {}
    if not isinstance(parsed_jd, dict):
        domain_class = getattr(parsed_jd, "domain_classification", {})
        if domain_class:
            domain_weights = domain_class.get("weights", {})

    for jd_skill in benchmark_skills:
        # Match using the new intelligence engine!
        evidence = skill_engine.match_skill(jd_skill, evidence_map)
        if evidence:
            matched.append(jd_skill)
            skill_evidence.append(evidence.to_dict())
        else:
            missing.append(jd_skill)
            
            # Intelligent Missing Analysis
            weight = domain_weights.get(skill_engine.normalize_skill(jd_skill), 0)
            importance = "Critical" if weight >= 14 else "High" if weight >= 10 else "Medium"
            
            missing_analysis.append(MissingSkill(
                skill=jd_skill,
                importance=importance,
                reason=f"Appears in Required Skills. Also supported by JD Domain weighting ({weight} pts)." if weight > 0 else "Required by JD.",
                learning_time="~2-4 weeks (est)" if importance != "Critical" else "~1-2 months (est)",
                suggested_project=f"Build a small project using {jd_skill} to boost resume visibility."
            ))

    recommended: List[str] = []
    if not is_preferred_only:
        for pref_skill in preferred:
            evidence = skill_engine.match_skill(pref_skill, evidence_map)
            if not evidence:
                recommended.append(pref_skill)
            else:
                skill_evidence.append(evidence.to_dict())

    total = len(benchmark_skills)
    match_pct = round((len(matched) / total * 100), 1) if total > 0 else 0.0

    return SkillGapResult(
        matched_skills=matched,
        missing_skills=missing,
        recommended_skills=recommended[:10],
        match_percentage=match_pct,
        skill_evidence=skill_evidence,
        missing_skills_analysis=missing_analysis
    )
