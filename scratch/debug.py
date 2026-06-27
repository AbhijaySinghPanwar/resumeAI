import sys
import os
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from resumeai.core.skill_intelligence import SkillIntelligenceEngine
from resumeai.matching.jd_parser import parse_job_description
from resumeai.matching.gap_analyzer import generate_skill_gap
from resumeai.matching.skill_matcher import SkillMatcher
from resumeai.pipeline import ResumeParser

# Backend JD
jd_text = """
Job Title: Backend Engineer
Requirements:
- 3+ years experience
- Python
- Django or FastAPI
- REST APIs
- SQL (PostgreSQL or MySQL)
- Docker
- Git
"""

# Simple backend resume
resume_text = """
Abhijay
Backend Developer

Experience:
Backend Developer at Tech
- Developed REST APIs with Python and FastAPI
- Database design with PostgreSQL
- Dockerized applications
"""

parser = ResumeParser(strict_schema=False, include_debug=True)
parsed_resume = parser.parse_text(resume_text)

parsed_jd = parse_job_description(jd_text)
print("--- JD Parsed ---")
print("Required:", parsed_jd.required_skills)
print("Domain:", parsed_jd.domain_classification)

gap = generate_skill_gap(parsed_resume, parsed_jd)
print("\n--- Gap Analyzer ---")
print("Matched:", gap.matched_skills)
print("Missing:", gap.missing_skills)
print("Match Pct:", gap.match_percentage)

matcher = SkillMatcher()
result = matcher.calculate_match_score(parsed_resume, parsed_jd)
print("\n--- Matcher ---")
print("Skill Score:", result.component_scores.skills)
print("Matched Count:", len(result.matched_skills))
print("Missing Count:", len(result.missing_skills))
