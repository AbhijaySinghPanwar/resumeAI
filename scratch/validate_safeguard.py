import json
from resumeai.matching.jd_parser import parse_job_description
from resumeai.matching.gap_analyzer import generate_skill_gap
from resumeai.matching.skill_matcher import SkillMatcher

JD_TEXT = "Experience developing backend web services"

RESUME = {
    'contact': {'name': 'Validation Candidate'},
    'summary': '',
    'skills': {
        'flat_list': ['Python', 'SQL'],
        'categories': []
    },
    'projects': [],
    'experience': [],
    'education': [],
    'certifications': [],
    'leadership': [],
}

parsed_jd = parse_job_description(JD_TEXT)
print("=== Raw JD Text ===")
print(JD_TEXT.strip())
print("\n=== Extracted JD Skills ===")
print(parsed_jd.required_skills)

print("\n=== Resume Skills ===")
print(RESUME['skills']['flat_list'])

gap = generate_skill_gap(RESUME, parsed_jd)
print("\n=== Matched Skills ===")
print(gap.matched_skills)
print("\n=== Missing Skills ===")
print(gap.missing_skills)
print("\n=== Skill Match Calculation (Gap) ===")
print(gap.match_percentage, "%")

matcher = SkillMatcher()
result = matcher.calculate_match_score(RESUME, parsed_jd)
print("\n=== Final Match Result ===")
print("Final Score:", result.match_score)
print(json.dumps(result.debug_info, indent=2))
