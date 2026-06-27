import json
import os
import sys

# Ensure we can import from resumeai
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from resumeai.core.skill_intelligence import SkillIntelligenceEngine
from resumeai.matching.jd_parser import parse_job_description
from resumeai.matching.gap_analyzer import generate_skill_gap, extract_all_resume_skills
from resumeai.matching.skill_matcher import SkillMatcher

def main():
    # Load the latest parse payload (representing the parsed resume)
    payload_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "resumeai_app", "latest_parse_payload.json"))
    with open(payload_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
        
    # Simulate the wrapper unwrap logic we added to skill_matcher
    if "result" in payload and isinstance(payload["result"], dict) and "version" in payload["result"]:
        parsed_resume = payload["result"]
    else:
        parsed_resume = payload

    jd_text = """Job Title: Backend Software Engineer
Requirements:
- Python
- Django or FastAPI
- REST APIs
- SQL (PostgreSQL or MySQL)
- Docker
- Git
"""

    print("==================================================")
    print("      SEMANTIC PIPELINE INTEGRATION TRACE         ")
    print("==================================================\n")

    # STEP 1
    print("STEP 1: Parsed JD Skills")
    parsed_jd = parse_job_description(jd_text)
    print(f"Required Skills ({len(parsed_jd.required_skills)}): {parsed_jd.required_skills}")
    print(f"Preferred Skills ({len(parsed_jd.preferred_skills)}): {parsed_jd.preferred_skills}\n")

    # STEP 2
    print("STEP 2: Resume Explicit Skills")
    resume_skills_raw = set(extract_all_resume_skills(parsed_resume))
    print(f"Explicit Skills ({len(resume_skills_raw)}): {sorted(list(resume_skills_raw))}\n")

    # STEP 3
    print("STEP 3: Project Inferred Skills")
    engine = SkillIntelligenceEngine()
    projects = parsed_resume.get("projects", [])
    inferred_skills = engine.infer_project_skills(projects)
    
    # Let's filter inferred to show only explicit project ones vs purely semantic inferred
    project_explicit = {k: v for k, v in inferred_skills.items() if v.match_type == "Explicit"}
    print(f"Project Explicit Skills ({len(project_explicit)}):")
    for k, v in project_explicit.items():
        print(f"  - {k} (Confidence: {v.confidence}, Source: {v.sources[0]})")
    print("")

    # STEP 4
    print("STEP 4: Expanded Semantic Skills")
    semantic_inferred = {k: v for k, v in inferred_skills.items() if v.match_type != "Explicit"}
    print(f"Semantic/Inferred Skills ({len(semantic_inferred)}):")
    for k, v in semantic_inferred.items():
        print(f"  - {k} (Type: {v.match_type}, Confidence: {v.confidence}, Reason: {v.reason})")
    print("")

    # STEP 5
    print("STEP 5: Unified Skill Graph")
    unified_skills = set(resume_skills_raw) | set(inferred_skills.keys())
    print(f"Total Unique Skills in Graph ({len(unified_skills)}): {sorted(list(unified_skills))}\n")

    # STEP 6
    print("STEP 6: Required JD Skills (Benchmark)")
    benchmark_skills = sorted(set(parsed_jd.required_skills) | set(parsed_jd.preferred_skills))
    print(f"Benchmark Skills ({len(benchmark_skills)}): {benchmark_skills}\n")

    # STEP 7 & 8
    print("STEP 7 & 8: Matched and Missing Skills (Gap Analysis)")
    gap = generate_skill_gap(parsed_resume, parsed_jd)
    print(f"Matched Skills ({len(gap.matched_skills)}): {gap.matched_skills}")
    if hasattr(gap, 'skill_evidence') and gap.skill_evidence:
        print("Evidence:")
        for ev in gap.skill_evidence:
            print(f"  - {ev.skill} -> {ev.match_type} (Confidence {ev.confidence}): {ev.reason}")
    print(f"Missing Skills ({len(gap.missing_skills)}): {gap.missing_skills}\n")

    # STEP 9
    print("STEP 9: Weighted Skill Score")
    matcher = SkillMatcher()
    match_result = matcher.calculate_match_score(payload, parsed_jd) # pass the raw payload to test the unwrap
    print(f"Skill Score: {match_result.component_scores.skills}")
    print(f"Semantic Relevance: {match_result.component_scores.semantic}")
    print(f"Final Match Score: {match_result.match_score}%\n")

    # STEP 10
    print("STEP 10: Final API JSON")
    print(json.dumps(match_result.to_dict(), indent=2))

if __name__ == "__main__":
    main()
