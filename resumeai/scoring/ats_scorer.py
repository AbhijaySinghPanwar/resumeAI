"""
ats_scorer.py — Main orchestrator for ATS Scoring Engine v2.
"""

from typing import Dict, Any

from resumeai.scoring.scoring_rules import (
    score_contact,
    score_education,
    score_experience,
    score_projects,
    score_skills,
    score_keywords,
    score_certifications_leadership,
    score_formatting,
    score_awards
)
from resumeai.scoring.feedback_engine import generate_feedback

class ATSScorer:
    """
    Evaluates parsed resumes against deterministic ATS-friendly criteria.
    """
    
    def score(self, parsed_resume: Dict[str, Any]) -> Dict[str, Any]:
        
        # 1. Candidate Type Detection & Dynamic Weighting
        exp_count = len(parsed_resume.get("experience", []))
        if exp_count == 0:
            candidate_type = "FRESHER"
        elif exp_count <= 2:
            candidate_type = "EARLY CAREER"
        else:
            candidate_type = "EXPERIENCED"

        # 2. Dynamic Weighting Model (Phase 1)
        if candidate_type == "FRESHER":
            weights = {"contact": 10, "education": 15, "experience": 0, "projects": 30, "skills": 15, "keywords": 10, "certifications": 10, "formatting": 5, "awards": 5}
        elif candidate_type == "EARLY CAREER":
            weights = {"contact": 10, "education": 10, "experience": 15, "projects": 20, "skills": 15, "keywords": 10, "certifications": 10, "formatting": 5, "awards": 5}
        else:
            weights = {"contact": 10, "education": 10, "experience": 25, "projects": 15, "skills": 10, "keywords": 10, "certifications": 10, "formatting": 5, "awards": 5}
            
        contact_pct = score_contact(parsed_resume.get("contact", {}))
        edu_base, edu_bonus = score_education(
            parsed_resume.get("education", []),
            candidate_type,
        )
        exp_base, exp_bonus = score_experience(parsed_resume.get("experience", []))
        
        project_quality_breakdown = score_projects(parsed_resume.get("projects", []))
        project_quality_score = project_quality_breakdown["overall_score"]
        skills_pct, skill_diversity_score = score_skills(parsed_resume.get("skills", {}))
        
        keywords_pct = score_keywords(parsed_resume)
        certs_pct = score_certifications_leadership(
            parsed_resume.get("certifications", []),
            parsed_resume.get("leadership", [])
        )
        formatting_pct = score_formatting(parsed_resume)
        
        # Awards
        text_corpus = ""
        for sec in ["experience", "projects", "education", "leadership", "certifications", "awards", "summary"]:
            for item in parsed_resume.get(sec, []) if isinstance(parsed_resume.get(sec), list) else [parsed_resume.get(sec)]:
                text_corpus += str(item) + " "
                
        awards_pct = score_awards(parsed_resume.get("awards", []), text_corpus)
        
        # 3. Weighted Breakdown & Bonuses
        # Base scores
        c_score = round(contact_pct * weights["contact"] / 100)
        e_score = round(edu_base * weights["education"] / 100)
        exp_score = round(exp_base * weights["experience"] / 100)
        p_score = round(project_quality_score * weights["projects"] / 100)
        s_score = round(skills_pct * weights["skills"] / 100)
        k_score = round(keywords_pct * weights["keywords"] / 100)
        cert_score = round(certs_pct * weights["certifications"] / 100)
        f_score = round(formatting_pct * weights["formatting"] / 100)
        a_score = round(awards_pct * weights["awards"] / 100)

        breakdown = {
            "contact": {"score": c_score, "max": weights["contact"]},
            "education": {"score": e_score, "max": weights["education"]},
            "experience": {"score": exp_score, "max": weights["experience"]},
            "projects": {"score": p_score, "max": weights["projects"]},
            "skills": {"score": s_score, "max": weights["skills"]},
            "keywords": {"score": k_score, "max": weights["keywords"]},
            "certifications": {"score": cert_score, "max": weights["certifications"]},
            "formatting": {"score": f_score, "max": weights["formatting"]},
            "awards": {"score": a_score, "max": weights["awards"]}
        }

        # Separated bonuses
        edu_bonus_points = round(edu_bonus * weights["education"] / 100)
        exp_bonus_points = round(exp_bonus * weights["experience"] / 100)
        
        bonus_breakdown = {}
        if edu_bonus_points > 0:
            bonus_breakdown["education_excellence_bonus"] = edu_bonus_points
        if exp_bonus_points > 0:
            bonus_breakdown["internship_achievement_bonus"] = exp_bonus_points

        overall_score = sum(b["score"] for b in breakdown.values()) + sum(bonus_breakdown.values())
        
        # Scores now emerge from section weights and transparent academic
        # bonuses. Retain the field for API compatibility, but remove the old
        # checklist-style calibration uplift.
        calibration_bonus = 0
        overall_score = min(100, overall_score)
        
        # 4. Resume Tier & Grade (Backward Compatibility)
        if overall_score >= 90:
            resume_tier = "ELITE"
            grade = "A+"
        elif overall_score >= 80:
            resume_tier = "STRONG"
            grade = "A"
        elif overall_score >= 70:
            resume_tier = "COMPETITIVE"
            grade = "B"
        elif overall_score >= 60:
            resume_tier = "AVERAGE"
            grade = "C"
        else:
            resume_tier = "WEAK"
            grade = "D"
            
        # 5. Recruiter Readiness
        if candidate_type == "FRESHER":
            project_count = len(parsed_resume.get("projects", []))
            portfolio_pct = min(100.0, project_count / 3 * 100)
            credentials_pct = score_certifications_leadership(
                parsed_resume.get("certifications", []),
                parsed_resume.get("leadership", []),
            )
            github_pct = 100.0 if parsed_resume.get("contact", {}).get("github") else 0.0
            diversity_pct = skill_diversity_score * 10
            readiness_components = {
                "overall_ats": round(overall_score * 0.50, 2),
                "project_quality": round(project_quality_score * 0.25, 2),
                "education": round(edu_base * 0.10, 2),
                "skill_diversity": round(diversity_pct * 0.05, 2),
                "projects_portfolio": round(portfolio_pct * 0.03, 2),
                "certifications_leadership": round(credentials_pct * 0.04, 2),
                "github_presence": round(github_pct * 0.03, 2),
            }
            readiness_raw = sum(readiness_components.values())
        else:
            readiness_raw = (overall_score * 0.60) + (project_quality_score * 0.25) + (exp_base * 0.10) + (formatting_pct * 0.05)
            readiness_components = {
                "overall_ats": round(overall_score * 0.60, 2),
                "project_quality": round(project_quality_score * 0.25, 2),
                "experience": round(exp_base * 0.10, 2),
                "formatting": round(formatting_pct * 0.05, 2),
            }
            
        recruiter_readiness = min(100, round(readiness_raw))
        
        if recruiter_readiness >= 90:
            readiness_band = "READY FOR TOP INTERNSHIPS" if candidate_type == "FRESHER" else "ELITE"
        elif recruiter_readiness >= 80:
            readiness_band = "STRONG CANDIDATE"
        elif recruiter_readiness >= 70:
            readiness_band = "COMPETITIVE"
        elif recruiter_readiness >= 60:
            readiness_band = "NEEDS IMPROVEMENT"
        else:
            readiness_band = "HIGH RISK"
            
        # 6. Section Intelligence
        sections = []
        for k, v_dict in breakdown.items():
            v = v_dict["score"]
            max_s = v_dict["max"]
            if max_s > 0:
                pct = v / max_s
                sections.append({"name": k.capitalize(), "score": v, "max_score": max_s, "pct": pct})
                
        sections.sort(key=lambda x: x["pct"], reverse=True)
        strongest_section = sections[0] if sections else {"name": "None", "score": 0, "max_score": 0, "pct": 0.0}
        weakest_section = sections[-1] if sections else {"name": "None", "score": 0, "max_score": 0, "pct": 0.0}
        
        del strongest_section["pct"]
        del weakest_section["pct"]
        
        # 7. Resume Completeness 2.0
        # Check Contact, Education, Experience/Projects, Skills, Certifications, Leadership
        completeness_pts = 0
        if parsed_resume.get("contact", {}).get("name"): completeness_pts += 15
        if parsed_resume.get("contact", {}).get("email"): completeness_pts += 10
        if parsed_resume.get("education"): completeness_pts += 20
        if parsed_resume.get("experience") or parsed_resume.get("projects"): completeness_pts += 30
        if parsed_resume.get("skills", {}).get("flat_list"): completeness_pts += 15
        if parsed_resume.get("certifications"): completeness_pts += 5
        if parsed_resume.get("leadership"): completeness_pts += 5
        
        resume_completeness = min(100, completeness_pts)
        
        # 8. Feedback & Recruiter Summary
        strengths, risks, improvements = generate_feedback(parsed_resume, breakdown, project_quality_score, candidate_type, skill_diversity_score)

        return {
            "overall_score": overall_score,
            "candidate_type": candidate_type,
            "resume_tier": resume_tier,
            
            "recruiter_readiness": recruiter_readiness,
            "readiness_band": readiness_band,
            "recruiter_readiness_breakdown": readiness_components,
            
            "project_quality_score": project_quality_score,
            "project_quality_breakdown": project_quality_breakdown,
            "skill_diversity_score": skill_diversity_score,
            
            "strongest_section": strongest_section,
            "weakest_section": weakest_section,
            
            "calibration_bonus": calibration_bonus,
            
            "strengths": strengths,
            "risks": risks,
            "improvements": improvements,
            
            # Backward compatibility fields
            "breakdown": breakdown,
            "bonus_breakdown": bonus_breakdown,
            "weights": weights,
            "grade": grade,
            "resume_completeness": resume_completeness
        }
