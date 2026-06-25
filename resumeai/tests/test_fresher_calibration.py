"""Calibration benchmarks for technically strong entry-level resumes."""

import copy

import pytest

from resumeai.scoring.ats_scorer import ATSScorer
from resumeai.scoring.scoring_rules import (
    METRIC_RE,
    score_awards,
    score_certifications_leadership,
    score_contact,
    score_experience,
    score_formatting,
    score_keywords,
    score_skills,
)


def profile_a_average_student():
    return {
        "contact": {
            "name": "Profile A",
            "email": "a@example.com",
            "phone": "9999999999",
            "github": "github.com/profile-a",
            "linkedin": "linkedin.com/in/profile-a",
        },
        "education": [
            {"degree": "B.Tech CSE", "institution": "State University", "end_date": "2026", "gpa": "7.8"}
        ],
        "experience": [],
        "projects": [
            {
                "name": "Task Manager",
                "description": "Full-stack task management application with a relational schema.",
                "technologies": ["React", "Flask", "SQLite"],
                "bullets": [
                    "Built reusable frontend components and backend routes",
                    "Designed the database schema and implemented authentication",
                ],
                "url": "https://github.com/profile-a/task-manager",
            },
            {
                "name": "Weather Dashboard",
                "description": "Dashboard integrating a third-party REST API.",
                "technologies": ["JavaScript", "REST API"],
                "bullets": [
                    "Integrated weather APIs and handled error states",
                    "Deployed the responsive dashboard on Vercel",
                ],
                "url": "https://profile-a-weather.vercel.app",
            },
        ],
        "skills": {"flat_list": [
            "python", "javascript", "react", "flask", "sql",
            "git", "html", "css", "rest api", "sqlite",
        ]},
        "certifications": [{"name": "Python Foundations"}],
        "leadership": [],
        "awards": [],
        "metadata": {"anomaly_count": 0},
    }


def profile_b_strong_fresher():
    return {
        "contact": {
            "name": "Profile B",
            "email": "b@example.com",
            "phone": "9999999998",
            "github": "github.com/profile-b",
            "linkedin": "linkedin.com/in/profile-b",
        },
        "education": [
            {"degree": "B.Tech CSE", "institution": "Engineering College", "end_date": "2026", "gpa": "8.7"},
            {"degree": "Class XII", "institution": "CBSE School", "end_date": "2022", "gpa": "92.4"},
        ],
        "experience": [],
        "projects": [
            {
                "name": "Resume Intelligence Platform",
                "description": "Full-stack AI platform with asynchronous API processing.",
                "technologies": ["React", "FastAPI", "PostgreSQL", "Docker"],
                "bullets": [
                    "Architected REST APIs and implemented JWT authentication",
                    "Integrated an NLP pipeline and designed normalized database schemas",
                ],
                "url": "https://github.com/profile-b/resume-platform",
            },
            {
                "name": "IoT Monitoring System",
                "description": "Real-time IoT telemetry system for sensor monitoring.",
                "technologies": ["Raspberry Pi", "MQTT", "WebSocket", "Redis"],
                "bullets": [
                    "Engineered an event-driven telemetry pipeline",
                    "Streamed sensor events to a real-time dashboard",
                ],
                "url": "",
            },
            {
                "name": "Cloud Document Assistant",
                "description": "Cloud-ready LLM assistant with vector search.",
                "technologies": ["Python", "PyTorch", "AWS", "Docker"],
                "bullets": [
                    "Built document ingestion and embedding pipelines",
                    "Integrated an LLM API with retrieval and citations",
                ],
                "url": "https://github.com/profile-b/document-assistant",
            },
        ],
        "skills": {"flat_list": [
            "python", "javascript", "typescript", "react", "fastapi",
            "postgresql", "redis", "docker", "aws", "pytorch",
            "machine learning", "nlp", "git", "linux", "websocket",
        ]},
        "certifications": [
            {"name": "AWS Cloud Practitioner"},
            {"name": "DeepLearning.AI Machine Learning"},
        ],
        "leadership": [],
        "awards": [],
        "metadata": {"anomaly_count": 0},
    }


def profile_c_internships_and_deployments():
    profile = copy.deepcopy(profile_b_strong_fresher())
    profile["contact"]["name"] = "Profile C"
    profile["experience"] = [
        {
            "title": "Software Engineering Intern",
            "company": "Product Startup",
            "bullets": [
                "Developed FastAPI services and implemented Redis caching",
                "Optimized database queries and reduced API latency by 30%",
            ],
        },
        {
            "title": "AI Engineering Intern",
            "company": "Research Lab",
            "bullets": [
                "Engineered an NLP evaluation pipeline",
                "Deployed a Docker inference API and resolved 10+ defects",
            ],
        },
    ]
    profile["leadership"] = [{"role": "Technical Lead", "organization": "Developer Club"}]
    profile["projects"][0]["bullets"].append(
        "Containerized services and deployed the application on Render"
    )
    profile["projects"][1]["url"] = "https://profile-c-iot.onrender.com"
    profile["projects"][1]["bullets"].append(
        "Implemented Redis caching and alert persistence"
    )
    profile["projects"][2]["bullets"].append(
        "Deployed containerized services to AWS"
    )
    profile["awards"] = ["Hackathon Finalist"]
    return profile


BENCHMARKS = {
    "A": (profile_a_average_student, (65, 75)),
    "B": (profile_b_strong_fresher, (80, 86)),
    "C": (profile_c_internships_and_deployments, (85, 90)),
}


def _legacy_project_score(projects):
    complexity_keywords = {
        "machine learning", "ai", "llm", "fastapi", "docker", "aws", "cloud",
        "microservices", "tensorflow", "pytorch", "react", "node.js",
        "distributed systems", "streamlit", "api", "database", "sql", "nosql",
    }
    deployment_domains = ["vercel.app", "netlify.app", "render.com", "railway.app", "aws", "azure", "gcp"]
    technical = documentation = links = deployment = metrics = 0
    for project in projects:
        text = " ".join(project.get("bullets", [])) + " " + (project.get("description") or "")
        lower = text.lower()
        combined = " ".join(project.get("technologies", [])).lower() + " " + lower
        technical += min(15, sum(1 for keyword in complexity_keywords if keyword in combined) * 5)
        if project.get("technologies"):
            technical += 5
        if project.get("name") and project.get("description"):
            documentation += 5
        if len(project.get("bullets", [])) >= 3:
            documentation += 8
        url = (project.get("url") or "").lower()
        if "github.com" in url:
            links += 5
        if any(domain in url for domain in deployment_domains) and "github.com" not in url:
            deployment += 5
        elif any(domain in lower for domain in deployment_domains):
            deployment += 5
        metrics += len(METRIC_RE.findall(lower)) * 5
    return min(40, technical) + min(25, documentation) + min(10, links) + min(10, deployment) + min(15, metrics)


def legacy_score_snapshot(resume):
    exp_count = len(resume.get("experience", []))
    candidate_type = "FRESHER" if exp_count == 0 else ("EARLY CAREER" if exp_count <= 2 else "EXPERIENCED")
    if candidate_type == "FRESHER":
        weights = {"contact": 10, "education": 15, "experience": 0, "projects": 30, "skills": 15, "keywords": 10, "certifications": 10, "formatting": 5, "awards": 5}
    elif candidate_type == "EARLY CAREER":
        weights = {"contact": 10, "education": 10, "experience": 15, "projects": 20, "skills": 15, "keywords": 10, "certifications": 10, "formatting": 5, "awards": 5}
    else:
        raise AssertionError("Calibration fixtures only cover entry-level profiles")

    contact = score_contact(resume.get("contact", {}))
    education = 100.0
    experience, experience_bonus = score_experience(resume.get("experience", []))
    projects = _legacy_project_score(resume.get("projects", []))
    skills, _ = score_skills(resume.get("skills", {}))
    keywords = score_keywords(resume)
    credentials = score_certifications_leadership(
        resume.get("certifications", []), resume.get("leadership", [])
    )
    formatting = score_formatting(resume)
    text = " ".join(str(resume.get(section, "")) for section in (
        "experience", "projects", "education", "leadership", "certifications", "awards", "summary"
    ))
    awards = score_awards(resume.get("awards", []), text)

    section_values = {
        "contact": contact,
        "education": education,
        "experience": experience,
        "projects": projects,
        "skills": skills,
        "keywords": keywords,
        "certifications": credentials,
        "formatting": formatting,
        "awards": awards,
    }
    overall = sum(round(section_values[key] * weight / 100) for key, weight in weights.items())
    overall += round(experience_bonus * weights["experience"] / 100)

    calibration_bonus = 0
    if projects >= 70:
        calibration_bonus += 1
    calibration_bonus += 1  # complete education produces edu_base >= 90
    if len(resume.get("certifications", [])) >= 5:
        calibration_bonus += 1
    if resume.get("contact", {}).get("github"):
        calibration_bonus += 1
    if resume.get("contact", {}).get("linkedin"):
        calibration_bonus += 1
    overall = min(100, overall + min(5, calibration_bonus))

    if candidate_type == "FRESHER":
        readiness = round(overall * 0.55 + projects * 0.30 + education * 0.10 + formatting * 0.05)
    else:
        readiness = round(overall * 0.60 + projects * 0.25 + experience * 0.10 + formatting * 0.05)
    return {"overall_score": overall, "project_quality_score": projects, "recruiter_readiness": readiness}


@pytest.mark.parametrize("label,fixture,expected_range", [
    (label, fixture, expected_range)
    for label, (fixture, expected_range) in BENCHMARKS.items()
])
def test_fresher_benchmark_ranges(label, fixture, expected_range):
    result = ATSScorer().score(fixture())
    assert expected_range[0] <= result["overall_score"] <= expected_range[1], (
        f"Profile {label}: {result['overall_score']} not in {expected_range}"
    )


def test_project_quality_uses_requested_weighting():
    result = ATSScorer().score(profile_b_strong_fresher())
    breakdown = result["project_quality_breakdown"]
    assert breakdown["technical_complexity"] <= 35
    assert breakdown["implementation_depth"] <= 25
    assert breakdown["documentation"] <= 15
    assert breakdown["links"] <= 10
    assert breakdown["metrics"] <= 15
    assert result["project_quality_score"] == sum(
        breakdown[key]
        for key in ("technical_complexity", "implementation_depth", "documentation", "links", "metrics")
    )


def test_strong_metric_free_engineering_is_not_undervalued():
    metric_free = profile_b_strong_fresher()
    result = ATSScorer().score(metric_free)
    assert result["project_quality_breakdown"]["metrics"] == 0
    assert result["project_quality_score"] >= 75
    assert 80 <= result["overall_score"] <= 86


def test_fresher_academic_thresholds_and_class_xii_bonus():
    scorer = ATSScorer()
    near_full = profile_a_average_student()
    near_full["education"] = [
        {"degree": "B.Tech", "institution": "College", "gpa": "8.5"}
    ]
    full = copy.deepcopy(near_full)
    full["education"][0]["gpa"] = "9.0"
    xii_bonus = copy.deepcopy(full)
    xii_bonus["education"].append(
        {"degree": "Class XII", "institution": "CBSE School", "gpa": "91.0"}
    )

    near_result = scorer.score(near_full)
    full_result = scorer.score(full)
    bonus_result = scorer.score(xii_bonus)
    assert near_result["breakdown"]["education"]["score"] >= 14
    assert full_result["breakdown"]["education"]["score"] == 15
    assert bonus_result["bonus_breakdown"]["education_excellence_bonus"] == 1


def test_recruiter_readiness_rewards_fresher_evidence():
    result = ATSScorer().score(profile_b_strong_fresher())
    readiness = result["recruiter_readiness_breakdown"]
    assert readiness["project_quality"] > 0
    assert readiness["skill_diversity"] > 0
    assert readiness["projects_portfolio"] == 3
    assert readiness["certifications_leadership"] == 2
    assert readiness["github_presence"] == 3
    assert "experience" not in readiness


def test_legacy_snapshots_are_reproducible():
    snapshots = {
        label: legacy_score_snapshot(fixture())
        for label, (fixture, _) in BENCHMARKS.items()
    }
    assert snapshots == {
        "A": {"overall_score": 72, "project_quality_score": 50, "recruiter_readiness": 70},
        "B": {"overall_score": 80, "project_quality_score": 65, "recruiter_readiness": 78},
        "C": {"overall_score": 93, "project_quality_score": 85, "recruiter_readiness": 89},
    }
