"""
feedback_engine.py — Generates text feedback based on parsed resume and scores.
"""

from typing import Dict, List, Any, Tuple

def generate_feedback(parsed_resume: Dict[str, Any], breakdown: Dict[str, Any], project_quality: float, candidate_type: str, skill_diversity: float) -> Tuple[List[str], List[str], List[str]]:
    strengths = []
    risks = []
    improvements = []
    
    # Helper to get score safely
    def get_score(category):
        val = breakdown.get(category, {"score": 0})
        return val["score"] if isinstance(val, dict) else val

    # Strengths
    if project_quality >= 80:
        strengths.append("Exceptional project documentation and technical depth.")
    elif project_quality >= 60:
        strengths.append("Strong technical projects with clear technology usage.")
        
    if get_score("experience") >= 15:
        strengths.append("Robust professional experience with clear metrics.")
        
    if get_score("education") >= 12:
        strengths.append("Excellent academic background.")
        
    if skill_diversity >= 8:
        strengths.append("Broad and highly diverse technical skill set.")
        
    if get_score("certifications") >= 8:
        strengths.append("Strong continued learning through certifications.")
        
    contact = parsed_resume.get("contact", {})
    if contact.get("github") and contact.get("linkedin"):
        strengths.append("Complete professional online presence.")

    # Risks
    if get_score("contact") < 10:
        risks.append("Missing critical contact information (Email, Phone, or Name).")
        
    if not parsed_resume.get("education"):
        risks.append("No education history detected.")
        
    if project_quality < 30 and candidate_type in ["FRESHER", "EARLY CAREER"]:
        risks.append("Project section is too weak for an entry-level candidate.")
        
    if get_score("skills") < 5:
        risks.append("Insufficient technical keywords detected by ATS.")
        
    if candidate_type == "EXPERIENCED" and get_score("experience") < 10:
        risks.append("Experience descriptions lack depth and quantifiable metrics.")

    # Improvements
    if not contact.get("linkedin"):
        improvements.append("Add a LinkedIn profile URL.")
        
    if not contact.get("github") and candidate_type in ["FRESHER", "EARLY CAREER"]:
        improvements.append("Add a GitHub profile to showcase code.")
        
    if project_quality < 70:
        improvements.append("Enhance project descriptions with more technical details and bullet points.")
        
    if get_score("experience") < 20 and candidate_type == "EXPERIENCED":
        improvements.append("Use more action verbs and add metrics (e.g., 'Improved efficiency by 20%') to experience bullets.")
        
    if get_score("certifications") == 0:
        improvements.append("Consider adding relevant industry certifications.")
        
    if skill_diversity < 5:
        improvements.append("Expand skills section to include testing, cloud, and devops tools.")

    return strengths, risks, improvements
