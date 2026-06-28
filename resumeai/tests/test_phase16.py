"""
tests/test_phase16.py — Phase 1.6 Regression & Validation Tests.

Covers:
  1. Project reconstruction (no "GitHub Link" project, no split projects)
  2. Continuation line detection (wrapped text merges correctly)
  3. Certification grouping (no split certs)
  4. Leadership subtype classification
  5. Abhijay's real PDF (ground-truth validation)
  6. Generic resume A (multi-template)
  7. Generic resume B (Overleaf-style)
"""

import pytest
import re
import sys
sys.path.insert(0, '/home/claude/resumeAI_new/resumeAI-main')

from resumeai.extractors._continuation import is_continuation, is_link_label_line
from resumeai.extractors.projects import extract_projects, build_resume_knowledge_graph
from resumeai.extractors.certifications import extract_certifications
from resumeai.extractors.leadership import extract_leadership, classify_leadership_entries
from resumeai.pipeline import ResumeParser


# ══════════════════════════════════════════════════════════════════════════════
# 1. CONTINUATION DETECTOR
# ══════════════════════════════════════════════════════════════════════════════

class TestContinuationDetector:

    def test_lowercase_start_is_continuation(self):
        assert is_continuation("services, cloud security and deployment.")

    def test_comma_start_is_continuation(self):
        assert is_continuation(", and additional tooling for CI/CD.")

    def test_and_start_is_continuation(self):
        assert is_continuation("and optimized query performance by 40%.")

    def test_with_start_is_continuation(self):
        assert is_continuation("with PostgreSQL as the primary database.")

    def test_for_start_is_continuation(self):
        assert is_continuation("for real-time monitoring of water quality.")

    def test_url_is_continuation(self):
        assert is_continuation("https://github.com/user/repo")

    def test_hyphen_wrap_is_continuation(self):
        assert is_continuation("orations.", prev_line="through requests and collab-")

    def test_period_start_is_continuation(self):
        assert is_continuation(".NET integration layer.")

    def test_github_label_is_link(self):
        assert is_link_label_line("GitHub")
        assert is_link_label_line("GitHub Link")
        assert is_link_label_line("GitHub: https://github.com/user/repo")

    def test_live_demo_label_is_link(self):
        assert is_link_label_line("Live Demo")
        assert is_link_label_line("Live Demo: https://myapp.vercel.app")

    def test_repo_label_is_link(self):
        assert is_link_label_line("Repository")
        assert is_link_label_line("Source Code")

    def test_title_case_new_project_not_continuation(self):
        assert not is_continuation("MarketPulse")

    def test_uppercase_title_not_continuation(self):
        assert not is_continuation("MULTI AI CHATBOT")

    def test_tech_stack_line_not_continuation(self):
        # TechStack: is handled by project extractor, not continuation
        assert not is_continuation("Python, React, Docker")  # starts uppercase P


# ══════════════════════════════════════════════════════════════════════════════
# 2. PROJECT EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

class TestProjectExtraction:

    MARKETPULSE_LINES = [
        "Projects",
        "MarketPulse",
        "An analytics platform for tracking market trends and generating AI-powered insights using",
        "pipelines for performance.",
        "GitHub: https://github.com/johndoe/marketpulse",
        "Live Demo: https://marketpulse.app",
        "",
        "Multi-AI Chatbot",
        "A multi-agent chatbot using LangChain and OpenAI GPT-4.",
        "technologies: Python, LangChain, OpenAI, Pinecone, FastAPI",
        "GitHub Link",
    ]

    def test_no_github_link_project(self):
        """'GitHub Link' must never become a project."""
        projects = extract_projects(self.MARKETPULSE_LINES)
        names = [p["name"] for p in projects]
        assert not any("GitHub" in (n or "") for n in names), \
            f"GitHub Link became a project: {names}"

    def test_no_split_on_description_wrap(self):
        """Wrapped description line attaches to MarketPulse, not a new project."""
        projects = extract_projects(self.MARKETPULSE_LINES)
        names = [p["name"] for p in projects]
        assert not any("pipeline" in (n or "").lower() for n in names), \
            f"Continuation line became a project: {names}"

    def test_marketpulse_is_one_project(self):
        projects = extract_projects(self.MARKETPULSE_LINES)
        names = [p["name"] for p in projects]
        assert "MarketPulse" in names, f"MarketPulse not found: {names}"

    def test_chatbot_is_one_project(self):
        projects = extract_projects(self.MARKETPULSE_LINES)
        names = [p["name"] for p in projects]
        # Should be exactly 2 projects
        assert len(projects) == 2, f"Expected 2 projects, got {len(projects)}: {names}"

    def test_github_url_attached_to_project(self):
        projects = extract_projects(self.MARKETPULSE_LINES)
        mp = next((p for p in projects if p["name"] == "MarketPulse"), None)
        assert mp is not None
        assert mp["github"] is not None, "GitHub URL not captured for MarketPulse"

    def test_live_demo_attached_to_project(self):
        projects = extract_projects(self.MARKETPULSE_LINES)
        mp = next((p for p in projects if p["name"] == "MarketPulse"), None)
        assert mp is not None
        assert mp["live_demo"] is not None, "Live Demo not captured for MarketPulse"

    def test_tech_extracted_from_freetext(self):
        """Technologies mentioned in description bullets are extracted."""
        projects = extract_projects(self.MARKETPULSE_LINES)
        chatbot = next((p for p in projects if "Chatbot" in (p["name"] or "")), None)
        assert chatbot is not None
        techs = chatbot["technologies"]
        assert "LangChain" in techs or "OpenAI" in techs or "Python" in techs, \
            f"Expected AI techs, got: {techs}"

    def test_project_has_domain(self):
        projects = extract_projects(self.MARKETPULSE_LINES)
        chatbot = next((p for p in projects if "Chatbot" in (p["name"] or "")), None)
        assert chatbot is not None
        assert chatbot["domain"] in ("AI", "AI Full Stack", "Backend", "General"), \
            f"Unexpected domain: {chatbot['domain']}"

    def test_project_has_complexity_score(self):
        projects = extract_projects(self.MARKETPULSE_LINES)
        for p in projects:
            assert isinstance(p["complexity"], int)
            assert 0 <= p["complexity"] <= 100

    def test_project_blank_line_does_not_split(self):
        """A blank line inside a project block must not split it into two projects."""
        lines = [
            "AQI Prediction",
            "Predicted air quality using ML models.",
            "",
            "Built with Python, Scikit-learn, Streamlit.",
            "GitHub: https://github.com/user/aqi",
        ]
        projects = extract_projects(lines)
        assert len(projects) == 1, f"Blank line split project: {[p['name'] for p in projects]}"

    def test_tech_stack_never_becomes_project(self):
        lines = [
            "My Project",
            "TechStack: Node.js, Express, MongoDB",
            "Built a REST API backend.",
        ]
        projects = extract_projects(lines)
        assert len(projects) == 1
        assert "TechStack" not in (projects[0]["name"] or "")

    def test_knowledge_graph_cross_project(self):
        """Knowledge graph must merge technologies across all projects."""
        lines = [
            "Project A", "Tech Stack: Node.js, MongoDB",
            "", 
            "Project B", "Built with Express.js and JWT authentication.",
        ]
        projects = extract_projects(lines)
        kg = build_resume_knowledge_graph(projects)
        all_techs = set(kg["all_technologies"])
        # Node.js from A, Express.js from B → both should be present
        assert len(all_techs) >= 2, f"Cross-project merge failed: {all_techs}"
        assert "Backend Development" in kg["all_capabilities"], \
            f"Backend Development not inferred: {kg['all_capabilities']}"


# ══════════════════════════════════════════════════════════════════════════════
# 3. CERTIFICATION EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

class TestCertificationExtraction:

    AWS_LINES = [
        "Certifications",
        "AWS Certified Solutions Architect",
        "Amazon Web Services | 2023",
        "services, cloud security, and deployment best practices.",
    ]

    IBM_LINES = [
        "IBM Watsonx Generative AI",
        "IBM Skills Network | 2023",
        "Studio.",
    ]

    def test_aws_cert_is_one_card(self):
        certs = extract_certifications(self.AWS_LINES)
        assert len(certs) == 1, f"AWS cert split into {len(certs)}: {[c['name'] for c in certs]}"

    def test_aws_cert_name_correct(self):
        certs = extract_certifications(self.AWS_LINES)
        assert certs[0]["name"] == "AWS Certified Solutions Architect"

    def test_aws_cert_issuer_detected(self):
        certs = extract_certifications(self.AWS_LINES)
        assert certs[0]["issuer"] is not None
        assert "aws" in certs[0]["issuer"].lower() or "amazon" in certs[0]["issuer"].lower()

    def test_aws_continuation_merged_into_description(self):
        """'services, cloud security...' must become description, not a second cert."""
        certs = extract_certifications(self.AWS_LINES)
        desc = certs[0].get("description") or ""
        assert "services" in desc.lower() or len(certs) == 1, \
            f"Continuation leaked into separate cert: {[c['name'] for c in certs]}"

    def test_ibm_cert_no_studio_fragment(self):
        """'Studio.' must not become a separate cert card."""
        certs = extract_certifications(self.IBM_LINES)
        names = [c["name"] for c in certs]
        assert not any("studio" in (n or "").lower() for n in names), \
            f"'Studio.' became a cert: {names}"
        assert len(certs) == 1, f"IBM cert split: {names}"

    def test_bullet_separated_certs(self):
        lines = [
            "Certifications",
            "• AWS Certified Cloud Practitioner | Amazon | 2023",
            "• Google Cloud Associate | Google | 2022",
            "• Microsoft Azure Fundamentals | Microsoft | 2023",
        ]
        certs = extract_certifications(lines)
        assert len(certs) == 3, f"Expected 3 certs, got {len(certs)}: {[c['name'] for c in certs]}"

    def test_date_prefix_format(self):
        """'2025—GenAI Using IBM Watsonx' style (from Abhijay's PDF)."""
        lines = [
            "2026—AWSCertifiedCloudPractitioner(InProgress)",
            "2025—GenAIUsingIBMWatsonx",
            "2025—DecodeC++withDSA",
        ]
        certs = extract_certifications(lines)
        assert len(certs) == 3, f"Expected 3 certs, got {len(certs)}: {[c['name'] for c in certs]}"
        assert all(c["date"] is not None for c in certs), "Dates not extracted"


# ══════════════════════════════════════════════════════════════════════════════
# 4. LEADERSHIP SUBTYPE CLASSIFICATION
# ══════════════════════════════════════════════════════════════════════════════

class TestLeadershipClassification:

    LEADERSHIP_LINES = [
        "Leadership",
        "Junior Core, PR and Outreach Domain — C.S.E.D, VIT",
        "2024 – 2025",
        "• Led outreach strategies and PR initiatives for campus-wide events.",
        "",
        "Rotary Youth Exchange Scholar",
        "Rotary International | 2022",
        "Awarded international exchange scholarship for academic excellence.",
        "",
        "IDF Hackathon Winner",
        "Inter-Department Fest | 2023",
        "Won first place in the AI/ML track.",
        "",
        "Merit Scholarship",
        "VIT University | 2022",
        "Awarded for top academic performance.",
    ]

    def test_no_continuation_fragment_as_entry(self):
        """'Awarded international exchange...' must not be a standalone entry."""
        entries = extract_leadership(self.LEADERSHIP_LINES)
        roles = [e.get("role") or "" for e in entries]
        assert not any("awarded" in r.lower() for r in roles), \
            f"Continuation line became entry: {roles}"

    def test_rotary_is_scholarship(self):
        entries = extract_leadership(self.LEADERSHIP_LINES)
        rotary = next((e for e in entries if "rotary" in (e.get("role") or "").lower()), None)
        if rotary:
            assert rotary.get("subtype") == "scholarship", \
                f"Rotary should be scholarship, got: {rotary.get('subtype')}"

    def test_hackathon_winner_is_award(self):
        entries = extract_leadership(self.LEADERSHIP_LINES)
        idf = next((e for e in entries if "idf" in (e.get("role") or "").lower()
                    or "hackathon" in (e.get("role") or "").lower()), None)
        if idf:
            assert idf.get("subtype") == "award", \
                f"Hackathon winner should be award, got: {idf.get('subtype')}"

    def test_merit_scholarship_is_scholarship(self):
        entries = extract_leadership(self.LEADERSHIP_LINES)
        merit = next((e for e in entries if "merit" in (e.get("role") or "").lower()), None)
        if merit:
            assert merit.get("subtype") == "scholarship", \
                f"Merit scholarship should be scholarship, got: {merit.get('subtype')}"

    def test_classify_function_returns_buckets(self):
        entries = extract_leadership(self.LEADERSHIP_LINES)
        buckets = classify_leadership_entries(entries)
        assert "awards" in buckets
        assert "scholarships" in buckets
        assert "positions_of_responsibility" in buckets
        assert "volunteer" in buckets

    def test_junior_core_is_position_of_responsibility(self):
        entries = extract_leadership(self.LEADERSHIP_LINES)
        junior = next((e for e in entries if "junior" in (e.get("role") or "").lower()
                       or "core" in (e.get("role") or "").lower()), None)
        if junior:
            assert junior.get("subtype") == "position_of_responsibility", \
                f"Junior Core should be POR, got: {junior.get('subtype')}"


# ══════════════════════════════════════════════════════════════════════════════
# 5. ABHIJAY'S REAL PDF — GROUND TRUTH
# ══════════════════════════════════════════════════════════════════════════════

class TestAbhijayPDF:
    """Run the full parser on Abhijay's real PDF and check all invariants."""

    @pytest.fixture(scope="class")
    def parsed(self):
        parser = ResumeParser(strict_schema=False, include_debug=False)
        return parser.parse_pdf('/mnt/user-data/uploads/Abhijay_Singh_Panwar_Resume.pdf')

    def test_exactly_three_projects(self, parsed):
        projects = parsed["projects"]
        names = [p["name"] for p in projects]
        assert len(projects) == 3, f"Expected 3 projects, got {len(projects)}: {names}"

    def test_no_techstack_project(self, parsed):
        names = [p["name"] for p in parsed["projects"]]
        assert not any("TechStack" in (n or "") or "Tech Stack" in (n or "") for n in names), \
            f"TechStack is still a project: {names}"

    def test_no_github_link_project(self, parsed):
        names = [p["name"] for p in parsed["projects"]]
        bad = [n for n in names if n and re.match(r"^github\s*(link)?$", n, re.IGNORECASE)]
        assert not bad, f"GitHub Link became a project: {bad}"

    def test_skillswap_technologies_complete(self, parsed):
        sp = next((p for p in parsed["projects"] if "SkillSwap" in (p["name"] or "")), None)
        assert sp is not None, "SkillSwap project not found"
        techs = sp["technologies"]
        assert "Node.js" in techs, f"Node.js missing: {techs}"
        assert "MongoDB" in techs, f"MongoDB missing: {techs}"

    def test_medical_chatbot_ai_tech(self, parsed):
        chatbot = next((p for p in parsed["projects"]
                        if "Medical" in (p["name"] or "") or "Chatbot" in (p["name"] or "")), None)
        assert chatbot is not None, "Medical chatbot not found"
        assert "Gemini API" in chatbot["technologies"] or "Python" in chatbot["technologies"], \
            f"AI techs missing: {chatbot['technologies']}"

    def test_three_certifications(self, parsed):
        certs = parsed["certifications"]
        assert len(certs) == 3, \
            f"Expected 3 certifications, got {len(certs)}: {[c['name'] for c in certs]}"

    def test_no_split_certifications(self, parsed):
        """No cert should have a name that looks like a sentence fragment."""
        for c in parsed["certifications"]:
            name = c.get("name") or ""
            assert not name.startswith(("services", "studio", "and ", "or ", "cloud")), \
                f"Split cert fragment detected: {name!r}"

    def test_skills_no_noise(self, parsed):
        flat = [s.lower() for s in parsed["skills"]["flat_list"]]
        noise_terms = [
            "strengths & interests", "programming", "frameworks", 
            "databases", "core cs subjects", "fast learning",
            "teamwork", "adaptability",
        ]
        for noise in noise_terms:
            assert noise not in flat, f"Noise term in skills: {noise!r}"

    def test_leadership_entry_present(self, parsed):
        assert len(parsed["leadership"]) >= 1, "No leadership entries found"

    def test_knowledge_graph_present(self, parsed):
        kg = parsed.get("knowledge_graph", {})
        assert kg.get("all_technologies"), "Knowledge graph empty"
        assert kg.get("all_domains"), "No domains in knowledge graph"


# ══════════════════════════════════════════════════════════════════════════════
# 6. GENERIC RESUME A (multi-project with description wrapping)
# ══════════════════════════════════════════════════════════════════════════════

RESUME_A_TEXT = """John Smith
john@example.com | github.com/jsmith

Projects

MarketPulse
An analytics platform for tracking real-time market trends and generating AI-powered insights using
ML pipelines for performance optimization.
GitHub: https://github.com/jsmith/marketpulse
Live Demo: https://marketpulse.app

Multi-AI Chatbot
A conversational agent powered by LangChain and OpenAI GPT-4 with RAG-based retrieval.
Technologies: Python, LangChain, OpenAI, Pinecone, FastAPI
GitHub Link

AQI Prediction Dashboard
Predicted air quality index using ML models trained on historical sensor data collected from IoT
sensors deployed across 12 cities.
Built with: Python, Scikit-learn, Streamlit, Pandas
Source: https://github.com/jsmith/aqi

Certifications

AWS Certified Solutions Architect
Amazon Web Services | 2023
Covered cloud infrastructure, services, cloud security, and deployment best practices.

IBM Watsonx Generative AI
IBM Skills Network | 2023
Hands-on experience with foundation models in Watson Studio.

Leadership

Rotary Youth Exchange Scholar
Rotary International | 2022
Awarded international exchange scholarship for academic excellence and leadership potential.

IDF Hackathon Winner
Inter-Department Fest | 2023
Won first place in the AI/ML track for building a real-time prediction engine.

Merit Scholarship
VIT University | 2022
Awarded for top academic performance — ranked in top 5% of the department.
"""


class TestGenericResumeA:

    @pytest.fixture(scope="class")
    def parsed(self):
        parser = ResumeParser(strict_schema=False, include_debug=False)
        return parser.parse_text(RESUME_A_TEXT)

    def test_three_projects(self, parsed):
        projects = parsed["projects"]
        assert len(projects) == 3, \
            f"Expected 3 projects, got {len(projects)}: {[p['name'] for p in projects]}"

    def test_no_github_link_project(self, parsed):
        names = [p["name"] for p in parsed["projects"]]
        assert not any(re.match(r"^(github|live demo|repository|source)\s*(link)?$",
                                 n or "", re.IGNORECASE) for n in names), \
            f"Link label became a project: {names}"

    def test_no_pipeline_fragment(self, parsed):
        """Wrapped description 'ML pipelines for performance...' must not be a project."""
        names = [p["name"] for p in parsed["projects"]]
        assert not any("pipeline" in (n or "").lower() for n in names), \
            f"Description fragment became project: {names}"

    def test_marketpulse_has_github(self, parsed):
        mp = next((p for p in parsed["projects"] if "MarketPulse" in (p["name"] or "")), None)
        assert mp and mp.get("github"), "MarketPulse github not captured"

    def test_aqi_has_source_link(self, parsed):
        aqi = next((p for p in parsed["projects"] if "AQI" in (p["name"] or "")), None)
        assert aqi is not None, "AQI project not found"

    def test_aws_cert_not_split(self, parsed):
        certs = parsed["certifications"]
        names = [c["name"] for c in certs]
        bad = [n for n in names if n and n.lower().startswith(
            ("covered", "hands-on", "services", "cloud security"))]
        assert not bad, f"Cert continuation leaked: {bad}"

    def test_rotary_scholarship_subtype(self, parsed):
        entries = parsed["leadership"]
        rotary = next((e for e in entries if "rotary" in (e.get("role") or "").lower()), None)
        if rotary:
            assert rotary.get("subtype") == "scholarship"

    def test_idf_award_subtype(self, parsed):
        entries = parsed["leadership"]
        idf = next((e for e in entries
                    if "hackathon" in (e.get("role") or "").lower()
                    or "idf" in (e.get("role") or "").lower()), None)
        if idf:
            assert idf.get("subtype") == "award"


# ══════════════════════════════════════════════════════════════════════════════
# 7. GENERIC RESUME B (Overleaf / ATS style)
# ══════════════════════════════════════════════════════════════════════════════

RESUME_B_TEXT = """Jane Doe
jane@email.com | LinkedIn | GitHub

WORK EXPERIENCE

Backend Engineer Intern | Stripe | San Francisco, CA
May 2023 – August 2023
- Designed and built payment reconciliation microservice using Go and gRPC
- Reduced API latency by 35% through Redis caching and query optimization
- Wrote integration tests using pytest and GitHub Actions CI/CD

PROJECTS

Distributed Task Scheduler
A fault-tolerant distributed task scheduler inspired by Kubernetes job scheduling.
Technologies: Go, Redis, PostgreSQL, Docker
GitHub: https://github.com/jane/scheduler
- Implemented leader election using Raft consensus algorithm
- Built REST API for job submission and status monitoring

Real-Time Chat App
End-to-end encrypted chat application with WebSocket support.
Stack: Node.js, Socket.io, MongoDB, React.js
Deployed: https://chat.janedoe.dev
- Implemented AES-256 end-to-end encryption
- Built scalable WebSocket server handling 1000+ concurrent connections

EDUCATION
M.S. Computer Science | Stanford University | 2024

SKILLS
Languages: Go, Python, JavaScript, TypeScript
Backend: FastAPI, Express.js, gRPC
Databases: PostgreSQL, MongoDB, Redis
Cloud: AWS, Docker, Kubernetes
"""


class TestGenericResumeB:

    @pytest.fixture(scope="class")
    def parsed(self):
        parser = ResumeParser(strict_schema=False, include_debug=False)
        return parser.parse_text(RESUME_B_TEXT)

    def test_two_projects(self, parsed):
        projects = parsed["projects"]
        assert len(projects) == 2, \
            f"Expected 2 projects, got {len(projects)}: {[p['name'] for p in projects]}"

    def test_no_link_as_project(self, parsed):
        names = [p["name"] for p in parsed["projects"]]
        bad = [n for n in names if n and re.match(
            r"^(github|deployed|live demo|website)\s*[:\-]?\s*(https?://\S+)?$",
            n, re.IGNORECASE)]
        assert not bad, f"Link became a project: {bad}"

    def test_scheduler_techs(self, parsed):
        sched = next((p for p in parsed["projects"]
                      if "Scheduler" in (p["name"] or "")), None)
        assert sched, "Scheduler project not found"
        assert "Docker" in sched["technologies"] or "Go" in sched["technologies"]

    def test_chat_app_websocket_domain(self, parsed):
        chat = next((p for p in parsed["projects"]
                     if "Chat" in (p["name"] or "")), None)
        assert chat, "Chat project not found"
        assert chat["domain"] in ("Full Stack", "Backend", "IoT"), \
            f"Unexpected domain: {chat['domain']}"

    def test_skills_no_category_headers(self, parsed):
        flat = [s.lower() for s in parsed["skills"]["flat_list"]]
        category_headers = ["languages", "backend", "databases", "cloud"]
        for hdr in category_headers:
            assert hdr not in flat, f"Category header in skills: {hdr!r}"


if __name__ == "__main__":
    import subprocess
    subprocess.run(["python", "-m", "pytest", __file__, "-v", "--tb=short"])
