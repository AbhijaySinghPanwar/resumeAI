"""
test_ats_scoring.py — Unit tests for the ATS Scoring Engine v2.
"""

import pytest
from resumeai.scoring.ats_scorer import ATSScorer
import copy

def get_weak_fresher():
    return {
        "contact": {"name": "Weak Fresher", "email": "weak@example.com"},
        "education": [{"degree": "BS", "institution": "Univ", "end_date": "2025"}],
        "experience": [],
        "projects": [
            {"name": "Simple App", "description": "A simple app"}
        ],
        "skills": {"flat_list": ["python", "html", "css"]},
        "metadata": {"anomaly_count": 0}
    }

def get_strong_fresher():
    return {
        "contact": {"name": "Strong Fresher", "email": "strong@example.com", "github": "github.com/strong"},
        "education": [{"degree": "BS CS", "institution": "Top Univ", "gpa": "3.9", "end_date": "2024"}],
        "experience": [],
        "projects": [
            {
                "name": "AI Predictor", "description": "Machine learning model.",
                "technologies": ["Python", "TensorFlow", "FastAPI"],
                "bullets": ["Achieved 95% accuracy on test set", "Improved latency by 45%"],
                "url": "https://vercel.app/project1"
            },
            {
                "name": "Cloud Dashboard", "description": "Data analytics dashboard.",
                "technologies": ["React", "AWS", "Node.js"],
                "bullets": ["Served 10000 users", "Deployed to aws"],
                "url": "https://github.com/strong/dashboard"
            },
            {
                "name": "DB Optimizer", "description": "Optimized postgres.",
                "technologies": ["SQL", "PostgreSQL", "Docker"],
                "bullets": ["Reduced queries by 10x"]
            }
        ],
        "skills": {"flat_list": [
            "python", "java", "react", "node.js", "aws", "docker", 
            "kubernetes", "sql", "postgresql", "machine learning", 
            "tensorflow", "fastapi", "django", "git", "github", 
            "linux", "bash", "agile", "scrum", "c++"
        ]},
        "certifications": [{"name": "AWS Certified"}],
        "leadership": [{"role": "President", "organization": "CS Club"}],
        "metadata": {"anomaly_count": 0}
    }

def get_experienced():
    return {
        "contact": {"name": "Exp Dev", "email": "exp@example.com", "github": "github.com/exp"},
        "education": [{"degree": "BS", "institution": "Univ"}],
        "experience": [
            {"bullets": ["Led team", "Improved latency by 50%"]},
            {"bullets": ["Developed microservices with Docker"]},
            {"bullets": ["Optimized DB, saved $50000"]}
        ],
        "projects": [{"name": "Side Project", "technologies": ["React"]}],
        "skills": {"flat_list": ["python", "docker", "aws", "react", "sql"]},
        "metadata": {"anomaly_count": 0}
    }

def test_schema_locks():
    scorer = ATSScorer()
    res = scorer.score(get_strong_fresher())
    
    assert "overall_score" in res
    assert "candidate_type" in res
    assert "resume_tier" in res
    assert "recruiter_readiness" in res
    assert "readiness_band" in res
    assert "project_quality_score" in res
    assert "project_quality_breakdown" in res
    assert "skill_diversity_score" in res
    assert "strongest_section" in res
    assert "weakest_section" in res
    assert "strengths" in res
    assert "risks" in res
    assert "improvements" in res
    assert "grade" in res
    assert "resume_completeness" in res

def test_emergent_scores():
    scorer = ATSScorer()
    
    weak_res = scorer.score(get_weak_fresher())
    strong_res = scorer.score(get_strong_fresher())
    exp_res = scorer.score(get_experienced())
    
    # Assertions
    assert strong_res["overall_score"] > weak_res["overall_score"]
    assert exp_res["overall_score"] > weak_res["overall_score"]
    
    # Check Candidate Types
    assert weak_res["candidate_type"] == "FRESHER"
    assert strong_res["candidate_type"] == "FRESHER"
    assert exp_res["candidate_type"] == "EXPERIENCED"
    
def test_metrics_improve_score():
    scorer = ATSScorer()
    base = get_strong_fresher()
    
    # Remove metrics
    no_metrics = copy.deepcopy(base)
    for p in no_metrics["projects"]:
        p["bullets"] = ["Did some work"]
        
    score_with = scorer.score(base)
    res_without = scorer.score(no_metrics)
    assert score_with["project_quality_breakdown"]["breakdowns"][0]["metrics"] > res_without["project_quality_breakdown"]["breakdowns"][0]["metrics"]
    assert score_with["overall_score"] > res_without["overall_score"]

def test_deployment_improves_score():
    scorer = ATSScorer()
    
    base = get_strong_fresher()
    base["projects"] = [base["projects"][0]] # Use the vercel one
    res_with = scorer.score(base)
    
    base_no_deploy = get_strong_fresher()
    base_no_deploy["projects"] = [base_no_deploy["projects"][0]]
    base_no_deploy["projects"][0]["url"] = ""
    res_without = scorer.score(base_no_deploy)
    
    assert res_with["project_quality_breakdown"]["breakdowns"][0]["deployment"] > res_without["project_quality_breakdown"]["breakdowns"][0]["deployment"]

def test_skill_diversity_improves_score():
    scorer = ATSScorer()
    base = get_strong_fresher()
    
    low_div = copy.deepcopy(base)
    low_div["skills"]["flat_list"] = ["python", "python3", "python programming"] * 7
    
    score_with = scorer.score(base)
    score_without = scorer.score(low_div)
    
    assert score_with["skill_diversity_score"] > score_without["skill_diversity_score"]

def test_github_improves_score():
    scorer = ATSScorer()
    base = get_strong_fresher()
    
    no_git = copy.deepcopy(base)
    no_git["contact"]["github"] = ""
    no_git["projects"][1]["url"] = ""
    
    score_with = scorer.score(base)
    score_without = scorer.score(no_git)
    
    assert score_with["overall_score"] > score_without["overall_score"]

def test_github_recommendation_logic():
    scorer = ATSScorer()
    # Has github -> no suggestion
    res_with = scorer.score(get_strong_fresher())
    assert not any("GitHub URLs detected" in imp for imp in res_with["improvements"])
    
    # No github -> suggestion
    resume_without_github = get_strong_fresher()
    resume_without_github["contact"]["github"] = ""
    resume_without_github["projects"][1]["url"] = ""
    res_without = scorer.score(resume_without_github)
    assert any("GitHub" in imp for imp in res_without["improvements"])

def test_calibration_strong_student():
    scorer = ATSScorer()
    # 2 internships, 3 projects, CGPA > 9.5, certifications, quantified achievements
    student = {
        "contact": {"name": "Calibration Student", "email": "cal@cal.com", "phone": "123", "github": "github.com/cal", "linkedin": "linkedin.com/cal"},
        "education": [{"degree": "BTech", "institution": "IIT", "end_date": "2025", "gpa": "9.81"}],
        "experience": [
            {"bullets": ["Developed backend API with 10+ bug fixes", "Optimized queries and improved performance by 20%"]},
            {"bullets": ["Engineered data pipeline with 15+ critical defects identified", "Implemented CI/CD resulting in 10+ merged PRs"]}
        ],
        "projects": [
            {
                "name": "Machine Learning Model",
                "description": "A deep learning model for NLP.",
                "technologies": ["Python", "PyTorch", "FastAPI"],
                "bullets": ["Trained LLM achieving 99% accuracy", "Optimized inference speed", "Created pipelines"]
            },
            {
                "name": "Distributed DB",
                "description": "Custom database engine.",
                "technologies": ["C++", "Distributed Systems", "Database"],
                "bullets": ["Handled queries", "Implemented raft consensus"]
            },
            {
                "name": "Cloud Backend",
                "description": "Microservices backend.",
                "technologies": ["Node.js", "AWS", "Docker"],
                "bullets": ["Deployed microservices", "Reduced costs", "Optimized routing"]
            }
        ],
        "skills": {"flat_list": [
            "python", "java", "c++", "react", "node.js", "aws", "docker",
            "kubernetes", "sql", "postgresql", "machine learning", "pytorch",
            "fastapi", "git", "github", "linux"
        ]},
        "certifications": [
            {"name": "AWS Certified Solutions Architect"},
            {"name": "DeepLearning.AI NLP"}
        ],
        "awards": ["Branch Topper", "Merit Scholarship"],
        "metadata": {"anomaly_count": 0}
    }
    
    res = scorer.score(student)
    
    assert 80 <= res["overall_score"] <= 95, f"Score out of bounds: {res['overall_score']}"
    assert 80 <= res["recruiter_readiness"] <= 95, f"Readiness out of bounds: {res['recruiter_readiness']}"
