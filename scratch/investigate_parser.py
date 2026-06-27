import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from resumeai.core.skill_intelligence import SkillIntelligenceEngine
from resumeai.matching.jd_parser import parse_job_description, _split_sections

jd_text = """Job Title: Backend Software Engineer

Location: Bengaluru

Responsibilities
- Design scalable backend services using Python.
- Build RESTful APIs using FastAPI or Django
- Design PostgreSQL databases
- Deploy applications using Docker
- Work with AWS

Required Skills
Python
Django
FastAPI
REST APIs
SQL
PostgreSQL
JWT
Docker
AWS
Git
CI/CD
Testable Code
Cloud
API Design
"""

print("-" * 55)
print("STEP 1\n")
engine = SkillIntelligenceEngine()
ontology_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resumeai", "matching", "skill_ontology.json")
print("Ontology loaded from:", ontology_path)
print("File exists:", os.path.exists(ontology_path))
print("Total categories loaded:", len(engine._ontology.get("categories", {})))
print("Total canonical skills loaded:", len(engine._canonical_list_sorted))

print("-" * 55)
print("STEP 4\n")
sections = _split_sections(jd_text)
print("Parsed Sections:")
for k, v in sections.items():
    print(f"{k.upper()}:\n{v.strip()[:50]}...\n")

print("-" * 55)
print("STEP 7\n")
parsed_jd = parse_job_description(jd_text)
print("Extracted required skills:")
for s in parsed_jd.required_skills:
    print(s)

print("\nExtracted preferred skills:")
for s in parsed_jd.preferred_skills:
    print(s)

print("\nExtracted keywords:")
for s in parsed_jd.keywords:
    print(s)
