"""
tests/test_phase4_export.py — Export service and endpoint tests.

Covers:
  - generate_pdf() produces non-empty bytes
  - generate_json() returns expected keys
  - generate_csv() contains expected headers
  - /export/pdf returns PDF content type
  - /export/json returns application/json  
  - /export/csv returns text/csv
  - Export works without authentication (guest mode)
"""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.engine import Base, get_db
from main import app

# Test DB override
TEST_DB_URL = "sqlite:///./test_phase4_export.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

SAMPLE_EXPORT_PAYLOAD = {
    "candidate": {"name": "Jane Doe", "email": "jane@example.com"},
    "ats_analysis": {
        "score": 78.5,
        "breakdown": {"contact": 10, "skills": 35, "experience": 33.5},
    },
    "jd_match": {
        "job_title": "Backend Engineer",
        "match_score": 72.0,
        "matched_skills": ["Python", "FastAPI", "SQL"],
        "missing_skills": ["Kubernetes", "AWS"],
    },
    "skills": {"flat_list": ["Python", "FastAPI", "SQL", "Git"]},
    "projects": [
        {
            "name": "ResumeAI",
            "description": "AI-powered resume platform",
            "technologies": ["FastAPI", "Python"],
        }
    ],
    "recommendations": [
        "Add quantified achievements",
        "Include a professional summary",
    ],
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ── Service Unit Tests ────────────────────────────────────────────────────────

class TestExportService:
    def test_generate_pdf_returns_bytes(self):
        from services.export_service import generate_pdf
        pdf = generate_pdf(SAMPLE_EXPORT_PAYLOAD)
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000
        # PDF magic bytes
        assert pdf[:4] == b"%PDF"

    def test_generate_json_structure(self):
        from services.export_service import generate_json
        result = generate_json(SAMPLE_EXPORT_PAYLOAD)
        assert "export_metadata" in result
        assert "candidate" in result
        assert "ats_analysis" in result
        assert "jd_match" in result
        assert result["export_metadata"]["source"] == "ResumeAI v4.0.0"

    def test_generate_csv_contains_headers(self):
        from services.export_service import generate_csv
        csv_str = generate_csv(SAMPLE_EXPORT_PAYLOAD)
        assert "ATS Score" in csv_str
        assert "Jane Doe" in csv_str
        assert "Generated At" in csv_str
        assert "Backend Engineer" in csv_str

    def test_generate_pdf_with_empty_data(self):
        from services.export_service import generate_pdf
        pdf = generate_pdf({})
        assert isinstance(pdf, bytes)
        assert len(pdf) > 0

    def test_generate_json_with_minimal_data(self):
        from services.export_service import generate_json
        result = generate_json({"candidate": {"name": "Min User"}})
        assert "candidate" in result


# ── Export Endpoints ──────────────────────────────────────────────────────────

class TestExportEndpoints:
    def test_pdf_export_guest(self, client):
        resp = client.post("/export/pdf", json=SAMPLE_EXPORT_PAYLOAD)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "jane_doe" in resp.headers["content-disposition"]
        assert resp.content[:4] == b"%PDF"

    def test_json_export_guest(self, client):
        resp = client.post("/export/json", json=SAMPLE_EXPORT_PAYLOAD)
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]
        data = json.loads(resp.content)
        assert "export_metadata" in data

    def test_csv_export_guest(self, client):
        resp = client.post("/export/csv", json=SAMPLE_EXPORT_PAYLOAD)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        text = resp.content.decode("utf-8")
        assert "ATS Score" in text

    def test_pdf_export_empty_payload(self, client):
        resp = client.post("/export/pdf", json={})
        assert resp.status_code == 200
        assert resp.content[:4] == b"%PDF"

    def test_json_export_includes_metadata(self, client):
        resp = client.post("/export/json", json=SAMPLE_EXPORT_PAYLOAD)
        data = json.loads(resp.content)
        assert data["candidate"]["name"] == "Jane Doe"
        assert data["ats_analysis"]["score"] == 78.5
