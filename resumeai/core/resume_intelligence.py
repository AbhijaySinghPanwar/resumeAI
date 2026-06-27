"""
core/resume_intelligence.py — Multi-stage Resume Intelligence Engine
"""

from typing import Dict, Any, List
from resumeai.matching.schemas import SkillEvidence
from resumeai.core.skill_intelligence import SkillIntelligenceEngine

class ResumeIntelligenceEngine:
    def __init__(self):
        self.skill_engine = SkillIntelligenceEngine()

    def _create_evidence(self, skill: str, source_type: str, source_name: str, confidence: int, evidence_text: str) -> SkillEvidence:
        return SkillEvidence(
            skill=skill,
            match_type="Explicit",
            confidence=confidence,
            reason=f"Found in {source_type}",
            sources=[source_name],
            # Adding extra contextual fields that gap_analyzer can use
        )

    def extract_resume_evidence(self, parsed_resume: Dict[str, Any]) -> Dict[str, List[SkillEvidence]]:
        """
        Extracts evidence from all sections of the resume and ranks them by source type.
        Returns a mapping from Skill -> List[SkillEvidence].
        """
        evidence_map: Dict[str, List[SkillEvidence]] = {}

        def add_evidence(skill: str, source_type: str, source_name: str, confidence: int, text: str):
            skill = self.skill_engine.normalize_skill(skill)
            if skill not in evidence_map:
                evidence_map[skill] = []
            
            # Avoid duplicate evidence from the exact same source
            if not any(e.sources[0] == source_name for e in evidence_map[skill]):
                evidence_map[skill].append(self._create_evidence(skill, source_type, source_name, confidence, text))

        # 1. Professional Experience & Internships (Base Confidence: 100)
        for exp in parsed_resume.get("experience", []):
            title = exp.get("title") or ""
            company = exp.get("company") or ""
            desc = exp.get("description") or ""
            bullets = " ".join(exp.get("bullets", []))
            full_text = f"{title} {company} {desc} {bullets}"
            
            is_internship = "intern" in title.lower()
            source_type = "Internship Experience" if is_internship else "Professional Experience"
            source_name = f"{source_type}: {title} at {company}"
            
            for skill in self.skill_engine.extract_skills_from_text(full_text):
                add_evidence(skill, source_type, source_name, 100, full_text)

        # 2. Open Source Contributions (Base Confidence: 95)
        for os_proj in parsed_resume.get("open_source", []):
            name = os_proj.get("name") or ""
            desc = os_proj.get("description") or ""
            bullets = " ".join(os_proj.get("bullets", []))
            full_text = f"{name} {desc} {bullets}"
            source_name = f"Open Source: {name}"
            
            for skill in self.skill_engine.extract_skills_from_text(full_text):
                add_evidence(skill, "Open Source Contributions", source_name, 95, full_text)
                
            for tech in os_proj.get("technologies", []):
                add_evidence(tech, "Open Source Contributions", source_name, 95, tech)

        # 3. Major Projects (Base Confidence: 90)
        for proj in parsed_resume.get("projects", []):
            name = proj.get("name") or ""
            desc = proj.get("description") or ""
            bullets = " ".join(proj.get("bullets", []))
            full_text = f"{name} {desc} {bullets}"
            source_name = f"Project: {name}"
            
            for skill in self.skill_engine.extract_skills_from_text(full_text):
                add_evidence(skill, "Major Projects", source_name, 90, full_text)
                
            for tech in proj.get("technologies", []):
                add_evidence(tech, "Major Projects", source_name, 90, tech)

        # 4. Research Projects (Base Confidence: 88)
        for res in parsed_resume.get("research", []):
            name = res.get("name") or ""
            desc = res.get("description") or ""
            bullets = " ".join(res.get("bullets", []))
            full_text = f"{name} {desc} {bullets}"
            source_name = f"Research: {name}"
            
            for skill in self.skill_engine.extract_skills_from_text(full_text):
                add_evidence(skill, "Research Projects", source_name, 88, full_text)

        # 5. Certifications (Base Confidence: 85)
        for cert in parsed_resume.get("certifications", []):
            name = cert.get("name") or ""
            issuer = cert.get("issuer") or ""
            full_text = f"{name} {issuer}"
            source_name = f"Certification: {name}"
            
            for skill in self.skill_engine.extract_skills_from_text(full_text):
                add_evidence(skill, "Certifications", source_name, 85, full_text)

        # 6. Education / Coursework (Base Confidence: 80)
        for edu in parsed_resume.get("education", []):
            degree = edu.get("degree") or ""
            field = edu.get("field_of_study") or ""
            full_text = f"{degree} in {field}"
            source_name = f"Education: {degree}"
            
            for skill in self.skill_engine.extract_skills_from_text(full_text):
                add_evidence(skill, "Coursework", source_name, 80, full_text)

        # 7. Skills Section (Base Confidence: 80)
        skills_sec = parsed_resume.get("skills", {})
        for s in skills_sec.get("flat_list", []):
            for skill in self.skill_engine.extract_skills_from_text(s):
                add_evidence(skill, "Skills Section", "Skills List", 80, s)
            add_evidence(s, "Skills Section", "Skills List", 80, s)
            
        for cat in skills_sec.get("categories", []):
            for s in cat.get("skills", []):
                for skill in self.skill_engine.extract_skills_from_text(s):
                    add_evidence(skill, "Skills Section", f"Skills Category: {cat.get('name', 'General')}", 80, s)
                add_evidence(s, "Skills Section", f"Skills Category: {cat.get('name', 'General')}", 80, s)

        # 8. Hackathons & Achievements & Publications & Tech Blogs (Base Confidence: 85)
        for hack in parsed_resume.get("hackathons", []):
            text = f"{hack.get('name', '')} {hack.get('description', '')} {' '.join(hack.get('bullets', []))}"
            for skill in self.skill_engine.extract_skills_from_text(text):
                add_evidence(skill, "Hackathons", f"Hackathon: {hack.get('name', '')}", 85, text)

        for pub in parsed_resume.get("publications", []):
            text = f"{pub.get('organization', '')} {pub.get('role', '')} {' '.join(pub.get('bullets', []))}"
            for skill in self.skill_engine.extract_skills_from_text(text):
                add_evidence(skill, "Publications", f"Publication: {pub.get('role', '')}", 85, text)
                
        for blog in parsed_resume.get("tech_blogs", []):
            text = f"{blog.get('name', '')} {blog.get('description', '')} {' '.join(blog.get('bullets', []))}"
            for skill in self.skill_engine.extract_skills_from_text(text):
                add_evidence(skill, "Tech Blogs", f"Tech Blog: {blog.get('name', '')}", 85, text)
                
        # 9. Summary
        summary = parsed_resume.get("summary", "")
        if summary:
            for skill in self.skill_engine.extract_skills_from_text(summary):
                add_evidence(skill, "Professional Summary", "Summary", 80, summary)

        return evidence_map

    def calculate_project_complexity(self, project: Dict[str, Any]) -> float:
        """
        Estimates project complexity on a scale of 0-10.
        Dimensions: Backend, Database, Auth, Cloud, AI, Testing, CI/CD, Microservices
        """
        text = str(project).lower()
        score = 5.0 # Base score
        
        dimensions = {
            "Cloud Deployment": ["aws", "gcp", "azure", "ec2", "s3", "lambda"],
            "Backend Architecture": ["api", "rest", "graphql", "backend", "server"],
            "Database Design": ["sql", "nosql", "postgres", "mysql", "mongodb", "database"],
            "Authentication": ["jwt", "oauth", "auth", "login"],
            "AI Integration": ["ai", "ml", "llm", "gemini", "openai", "model", "predict"],
            "Testing": ["test", "pytest", "jest", "mock"],
            "CI/CD": ["ci/cd", "github actions", "jenkins", "pipeline", "deploy"],
            "Microservices": ["microservice", "docker", "kubernetes", "container"],
            "Scalability": ["scale", "cache", "redis", "kafka", "optimize", "performance"]
        }
        
        hits = 0
        for dim, keywords in dimensions.items():
            if any(kw in text for kw in keywords):
                score += 0.5
                hits += 1
                
        if len(project.get("technologies", [])) > 4:
            score += 0.5
            
        if len(project.get("bullets", [])) > 2:
            score += 0.5
            
        return min(10.0, round(score, 1))

    def evaluate_technology_usage_strength(self, evidence_text: str) -> int:
        """
        Differentiates between Mentioned (80), Used (85), Implemented (90), Designed (95), Architected (100).
        Returns a confidence multiplier or absolute boost.
        """
        text = evidence_text.lower()
        if "architect" in text or "spearhead" in text:
            return 100
        if "design" in text or "develop" in text or "build" in text or "built" in text:
            return 95
        if "implement" in text or "integrate" in text or "create" in text:
            return 90
        if "use" in text or "utilize" in text or "leverage" in text:
            return 85
        return 80
