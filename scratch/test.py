import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from resumeai.core.skill_intelligence import SkillIntelligenceEngine
from resumeai.matching.jd_parser import parse_job_description
from resumeai.matching.gap_analyzer import generate_skill_gap
from resumeai.matching.skill_matcher import SkillMatcher
import json

jd_text = """
Backend Engineer
We are looking for a backend engineer.
Required:
- Python
- FastAPI
- Docker
- SQL
Preferred:
- AWS
"""

resume = {
    "summary": "Experienced software engineer.",
    "experience": [
        {
            "title": "Backend Dev",
            "description": "Built REST APIs using Python and Django. Containerized apps with Docker.",
            "bullets": ["Used PostgreSQL for database."]
        }
    ],
    "projects": [
        {
            "name": "Cloud App",
            "description": "Deployed on AWS EC2.",
            "technologies": ["AWS", "Python"]
        }
    ],
    "skills": {
        "flat_list": ["Python", "Django", "PostgreSQL", "Docker", "AWS"]
    },
    "education": [],
    "certifications": [],
    "leadership": []
}

parsed_jd = parse_job_description(jd_text)
print("Parsed JD Domain:")
print(json.dumps(parsed_jd.domain_classification, indent=2))

print("\nParsed JD Required:")
print(parsed_jd.required_skills)

print("\nParsed JD Preferred:")
print(parsed_jd.preferred_skills)

gap = generate_skill_gap(resume, parsed_jd)
print("\nMatched Skills:")
print(gap.matched_skills)
print("\nMissing Skills:")
print(gap.missing_skills)

print("\nSkill Evidence:")
for ev in (gap.skill_evidence or []):
    print(json.dumps(ev.to_dict(), indent=2))

print("\nMissing Analysis:")
for ms in (gap.missing_skills_analysis or []):
    print(json.dumps(ms.to_dict(), indent=2))

matcher = SkillMatcher()
result = matcher.calculate_match_score(resume, parsed_jd)

print("\nMatch Score:", result.match_score)
print(result.component_scores.skills)
