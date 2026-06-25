import json
from resumeai.matching.jd_parser import parse_job_description
from resumeai.matching.gap_analyzer import generate_skill_gap, _norm
from resumeai.matching.skill_matcher import SkillMatcher

JD_TEXT = """Software Engineer Intern

Requirements:
- Python
- FastAPI
- SQL
- Git
- REST APIs
- Problem Solving
- Data Structures
"""

# We'll simulate a parsed resume with exactly the skills requested.
RESUME = {
    'contact': {'name': 'Validation Candidate'},
    'summary': '',
    'skills': {
        'flat_list': ['Python', 'MySQL', 'GitHub', 'DSA', 'Problem Solving'],
        'categories': []
    },
    'projects': [],
    'experience': [],
    'education': [],
    'certifications': [],
    'leadership': [],
}

parsed_jd = parse_job_description(JD_TEXT)
print("=== Parsed JD Skills ===")
print("Required:", parsed_jd.required_skills)
print("Normalized:", [_norm(s) for s in parsed_jd.required_skills])
print()

gap = generate_skill_gap(RESUME, parsed_jd)
print("=== Normalized Skill Sets ===")
resume_skills_raw = RESUME['skills']['flat_list']
print("Resume Raw:", resume_skills_raw)
print("Resume Normalized:", [_norm(s) for s in resume_skills_raw])
print()

print("=== Skill Gap ===")
print("Matched:", gap.matched_skills)
print("Missing:", gap.missing_skills)
print("Skill Match Score:", gap.match_percentage)
print()

matcher = SkillMatcher()
result = matcher.calculate_match_score(RESUME, parsed_jd)
print("=== Final Match Result ===")
print("Final Score:", result.match_score)
print("Final Grade:", result.match_grade)
print(json.dumps(result.debug_info, indent=2))
