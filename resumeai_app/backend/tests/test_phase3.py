"""
tests/test_phase3.py — Unit tests for Phase 3 AI services.

Tests cover:
  - BulletImprover (with Gemini mocked)
  - ProjectEnhancer (with Gemini mocked)
  - InterviewGenerator (with Gemini mocked)
  - Fallback paths when Gemini is unavailable
  - FastAPI endpoint integration tests
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_RESUME = {
    "contact": {"name": "Abhijay Singh Panwar", "email": "abhijay@example.com"},
    "summary": "CS student passionate about backend development.",
    "skills": {
        "flat_list": ["Python", "FastAPI", "SQL", "Docker", "Git"],
        "categories": [{"category": "Languages", "skills": ["Python", "C++"]}],
    },
    "projects": [
        {
            "name": "SkillSwap",
            "description": "Peer-to-peer skill exchange platform",
            "technologies": ["FastAPI", "PostgreSQL", "React"],
            "bullets": ["Built REST API", "Implemented JWT auth"],
        }
    ],
    "experience": [
        {"title": "Software Intern", "company": "TechCorp", "bullets": ["Developed backend APIs"]}
    ],
    "education": [
        {"degree": "B.Tech", "field_of_study": "Computer Science", "institution": "IIT Delhi"}
    ],
    "certifications": [],
    "leadership": [],
}

SAMPLE_BULLET = "Worked on backend APIs for internal tools"
SAMPLE_JD = "Looking for a Python backend engineer with FastAPI and SQL experience."


# ── BulletImprover tests ──────────────────────────────────────────────────────

class TestBulletImprover:
    def _make_improver(self, gemini_response: str):
        from services.gemini_service import GeminiService
        from services.bullet_improver import BulletImprover
        mock_gemini = MagicMock(spec=GeminiService)
        mock_gemini.is_available = True
        mock_gemini.generate.return_value = gemini_response
        return BulletImprover(mock_gemini)

    def test_returns_three_variants(self):
        payload = json.dumps({
            "ats_version": "Engineered RESTful APIs serving 50K daily requests using FastAPI and PostgreSQL.",
            "professional_version": "Led development of internal tooling APIs, improving team productivity by 30%.",
            "concise_version": "Built scalable backend APIs for internal tooling.",
        })
        improver = self._make_improver(payload)
        result = improver.improve(SAMPLE_BULLET, "experience")
        assert "ats_version" in result
        assert "professional_version" in result
        assert "concise_version" in result

    def test_ats_version_non_empty(self):
        payload = json.dumps({
            "ats_version": "Developed RESTful APIs using Python and FastAPI.",
            "professional_version": "Led API development initiatives.",
            "concise_version": "Built APIs used by 5K users.",
        })
        improver = self._make_improver(payload)
        result = improver.improve(SAMPLE_BULLET)
        assert len(result["ats_version"]) > 10

    def test_concise_version_brevity(self):
        payload = json.dumps({
            "ats_version": "Developed backend APIs.",
            "professional_version": "Led API development.",
            "concise_version": "Built fast, reliable APIs.",
        })
        improver = self._make_improver(payload)
        result = improver.improve(SAMPLE_BULLET)
        word_count = len(result["concise_version"].split())
        assert word_count <= 15, f"concise_version too long: {word_count} words"

    def test_raises_on_empty_bullet(self):
        from services.bullet_improver import BulletImprover
        from services.gemini_service import GeminiService
        mock_gemini = MagicMock(spec=GeminiService)
        mock_gemini.is_available = True
        improver = BulletImprover(mock_gemini)
        with pytest.raises(ValueError):
            improver.improve("", "experience")

    def test_fallback_when_gemini_unavailable(self):
        from services.bullet_improver import BulletImprover
        from services.gemini_service import GeminiService
        mock_gemini = MagicMock(spec=GeminiService)
        mock_gemini.is_available = False
        improver = BulletImprover(mock_gemini)
        result = improver.improve(SAMPLE_BULLET)
        assert "ats_version" in result
        assert "professional_version" in result
        assert "concise_version" in result

    def test_handles_gemini_returning_markdown_fences(self):
        payload = "```json\n" + json.dumps({
            "ats_version": "Built APIs.",
            "professional_version": "Developed APIs.",
            "concise_version": "Fast APIs.",
        }) + "\n```"
        improver = self._make_improver(payload)
        result = improver.improve(SAMPLE_BULLET)
        assert result["ats_version"] == "Built APIs."


# ── ProjectEnhancer tests ─────────────────────────────────────────────────────

class TestProjectEnhancer:
    def _make_enhancer(self, gemini_response: str):
        from services.gemini_service import GeminiService
        from services.project_enhancer import ProjectEnhancer
        mock_gemini = MagicMock(spec=GeminiService)
        mock_gemini.is_available = True
        mock_gemini.generate.return_value = gemini_response
        return ProjectEnhancer(mock_gemini)

    def test_returns_three_variants(self):
        payload = json.dumps({
            "ats_version": "Developed SkillSwap using FastAPI, PostgreSQL, and React.",
            "technical_version": "Architected microservices backend with JWT auth and RESTful APIs.",
            "recruiter_version": "Built a platform connecting 500+ students for skill sharing.",
        })
        enhancer = self._make_enhancer(payload)
        result = enhancer.enhance("SkillSwap", "Peer-to-peer skill exchange platform")
        assert "ats_version" in result
        assert "technical_version" in result
        assert "recruiter_version" in result

    def test_raises_on_empty_project_name(self):
        from services.project_enhancer import ProjectEnhancer
        from services.gemini_service import GeminiService
        mock_gemini = MagicMock(spec=GeminiService)
        mock_gemini.is_available = True
        enhancer = ProjectEnhancer(mock_gemini)
        with pytest.raises(ValueError):
            enhancer.enhance("", "some description")

    def test_raises_on_empty_description(self):
        from services.project_enhancer import ProjectEnhancer
        from services.gemini_service import GeminiService
        mock_gemini = MagicMock(spec=GeminiService)
        mock_gemini.is_available = True
        enhancer = ProjectEnhancer(mock_gemini)
        with pytest.raises(ValueError):
            enhancer.enhance("MyProject", "")

    def test_fallback_when_gemini_unavailable(self):
        from services.project_enhancer import ProjectEnhancer
        from services.gemini_service import GeminiService
        mock_gemini = MagicMock(spec=GeminiService)
        mock_gemini.is_available = False
        enhancer = ProjectEnhancer(mock_gemini)
        result = enhancer.enhance("SkillSwap", "Skill exchange platform")
        assert "ats_version" in result
        assert "technical_version" in result
        assert "recruiter_version" in result


# ── InterviewGenerator tests ──────────────────────────────────────────────────

class TestInterviewGenerator:
    def _make_generator(self, gemini_response: str):
        from services.gemini_service import GeminiService
        from services.interview_generator import InterviewGenerator
        mock_gemini = MagicMock(spec=GeminiService)
        mock_gemini.is_available = True
        mock_gemini.generate.return_value = gemini_response
        return InterviewGenerator(mock_gemini)

    def test_returns_three_categories(self):
        payload = json.dumps({
            "technical_questions": ["Q1", "Q2", "Q3", "Q4", "Q5"],
            "project_questions": ["P1", "P2", "P3", "P4"],
            "behavioral_questions": ["B1", "B2", "B3", "B4"],
        })
        gen = self._make_generator(payload)
        result = gen.generate(SAMPLE_RESUME, SAMPLE_JD)
        assert "technical_questions" in result
        assert "project_questions" in result
        assert "behavioral_questions" in result

    def test_technical_questions_are_list(self):
        payload = json.dumps({
            "technical_questions": ["Q1", "Q2", "Q3", "Q4", "Q5"],
            "project_questions": ["P1", "P2", "P3", "P4"],
            "behavioral_questions": ["B1", "B2", "B3", "B4"],
        })
        gen = self._make_generator(payload)
        result = gen.generate(SAMPLE_RESUME, SAMPLE_JD)
        assert isinstance(result["technical_questions"], list)
        assert len(result["technical_questions"]) > 0

    def test_raises_on_empty_resume(self):
        from services.interview_generator import InterviewGenerator
        from services.gemini_service import GeminiService
        mock_gemini = MagicMock(spec=GeminiService)
        mock_gemini.is_available = True
        gen = InterviewGenerator(mock_gemini)
        with pytest.raises(ValueError):
            gen.generate({}, SAMPLE_JD)

    def test_raises_on_empty_jd(self):
        from services.interview_generator import InterviewGenerator
        from services.gemini_service import GeminiService
        mock_gemini = MagicMock(spec=GeminiService)
        mock_gemini.is_available = True
        gen = InterviewGenerator(mock_gemini)
        with pytest.raises(ValueError):
            gen.generate(SAMPLE_RESUME, "")

    def test_fallback_when_gemini_unavailable(self):
        from services.interview_generator import InterviewGenerator
        from services.gemini_service import GeminiService
        mock_gemini = MagicMock(spec=GeminiService)
        mock_gemini.is_available = False
        gen = InterviewGenerator(mock_gemini)
        result = gen.generate(SAMPLE_RESUME, SAMPLE_JD)
        assert "technical_questions" in result
        assert "project_questions" in result
        assert "behavioral_questions" in result
        assert len(result["technical_questions"]) >= 3


# ── FastAPI endpoint tests ────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.engine import Base, get_db
    from main import app

    _engine = create_engine("sqlite:///./test_phase3_client.db", connect_args={"check_same_thread": False})
    _Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    Base.metadata.create_all(bind=_engine)

    def _override_db():
        db = _Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestAIEndpoints:
    def test_ai_status_endpoint(self, client):
        resp = client.get("/ai/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data
        assert "active_model" in data

    def test_improve_bullet_endpoint_empty_bullet(self, client):
        resp = client.post("/ai/improve-bullet", json={"bullet": "", "context": "experience"})
        assert resp.status_code == 400

    def test_improve_bullet_valid(self, client):
        """Returns 200 even without Gemini key (uses fallback)."""
        resp = client.post("/ai/improve-bullet", json={
            "bullet": "Worked on APIs for internal services",
            "context": "experience",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "ats_version" in data
        assert "professional_version" in data
        assert "concise_version" in data

    def test_enhance_project_valid(self, client):
        resp = client.post("/ai/enhance-project", json={
            "project_name": "SkillSwap",
            "description": "Peer-to-peer skill exchange platform built with FastAPI.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "ats_version" in data
        assert "technical_version" in data
        assert "recruiter_version" in data

    def test_enhance_project_empty_name(self, client):
        resp = client.post("/ai/enhance-project", json={
            "project_name": "",
            "description": "Some description",
        })
        assert resp.status_code == 400

    def test_interview_questions_valid(self, client):
        resp = client.post("/ai/interview-questions", json={
            "resume_data": SAMPLE_RESUME,
            "job_description": SAMPLE_JD,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "technical_questions" in data
        assert "project_questions" in data
        assert "behavioral_questions" in data

    def test_interview_questions_empty_jd(self, client):
        resp = client.post("/ai/interview-questions", json={
            "resume_data": SAMPLE_RESUME,
            "job_description": "",
        })
        assert resp.status_code == 400
