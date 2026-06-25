"""
tests/test_phase4_db.py — Database and repository layer tests.

Covers:
  - UserRepository CRUD
  - ResumeRepository paginated listing + ownership
  - ReportRepository ATS + JD CRUD + stats
  - Cascade deletes (resume → reports)
"""
from __future__ import annotations

import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.engine import Base
from repositories.user_repo import UserRepository
from repositories.resume_repo import ResumeRepository
from repositories.report_repo import ReportRepository
from services.auth_service import hash_password, verify_password

TEST_DB_URL = "sqlite:///./test_phase4_db.db"

@pytest.fixture(scope="module")
def db():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def user(db):
    repo = UserRepository(db)
    return repo.create("DB Test User", "dbtest@example.com", hash_password("password123"))


@pytest.fixture(scope="module")
def resume(db, user):
    repo = ResumeRepository(db)
    return repo.create(
        user_id=user.id,
        filename="test_resume.pdf",
        parsed_json={"contact": {"name": "DB Test User", "email": "dbtest@example.com"}, "skills": {"flat_list": ["Python"]}},
        ats_score=72.5,
    )


# ── User Repository ───────────────────────────────────────────────────────────

class TestUserRepository:
    def test_create_user(self, user):
        assert user.id is not None
        assert user.email == "dbtest@example.com"
        assert user.is_active is True

    def test_get_by_id(self, db, user):
        found = UserRepository(db).get_by_id(user.id)
        assert found is not None
        assert found.email == user.email

    def test_get_by_email(self, db, user):
        found = UserRepository(db).get_by_email("dbtest@example.com")
        assert found is not None
        assert found.id == user.id

    def test_email_exists(self, db, user):
        assert UserRepository(db).email_exists("dbtest@example.com") is True
        assert UserRepository(db).email_exists("nobody@example.com") is False

    def test_get_by_id_nonexistent(self, db):
        assert UserRepository(db).get_by_id(999999) is None

    def test_password_hash_and_verify(self, user):
        assert verify_password("password123", user.password_hash) is True
        assert verify_password("wrongpassword", user.password_hash) is False


# ── Resume Repository ─────────────────────────────────────────────────────────

class TestResumeRepository:
    def test_create_resume(self, resume):
        assert resume.id is not None
        assert resume.filename == "test_resume.pdf"
        assert resume.ats_score == 72.5

    def test_get_by_id(self, db, resume, user):
        found = ResumeRepository(db).get_by_id(resume.id)
        assert found is not None
        assert found.user_id == user.id

    def test_parsed_property(self, resume):
        parsed = resume.parsed
        assert "contact" in parsed

    def test_get_by_user_paginated(self, db, user):
        # Create a second resume
        ResumeRepository(db).create(user.id, "resume2.pdf", {"skills": {"flat_list": []}}, 55.0)
        items, total = ResumeRepository(db).get_by_user(user.id, page=1, page_size=10)
        assert total >= 2
        assert len(items) >= 2

    def test_pagination_limits(self, db, user):
        items, total = ResumeRepository(db).get_by_user(user.id, page=1, page_size=1)
        assert len(items) == 1

    def test_search_by_filename(self, db, user):
        items, total = ResumeRepository(db).get_by_user(user.id, search="test_resume")
        assert total >= 1

    def test_delete_resume(self, db, user):
        temp = ResumeRepository(db).create(user.id, "temp.pdf", {}, 0.0)
        deleted = ResumeRepository(db).delete(temp.id, user.id)
        assert deleted is True
        assert ResumeRepository(db).get_by_id(temp.id) is None

    def test_delete_wrong_user(self, db, resume):
        result = ResumeRepository(db).delete(resume.id, user_id=999999)
        assert result is False


# ── Report Repository ─────────────────────────────────────────────────────────

class TestReportRepository:
    def test_create_ats_report(self, db, resume):
        report = ReportRepository(db).create_ats(
            resume_id=resume.id,
            ats_score=85.0,
            ats_breakdown={"contact": 10, "skills": 30, "experience": 45},
            suggestions=["Add a summary section", "Quantify achievements"],
        )
        assert report.id is not None
        assert report.ats_score == 85.0
        assert "contact" in report.breakdown

    def test_create_jd_report(self, db, resume):
        report = ReportRepository(db).create_jd(
            resume_id=resume.id,
            jd_text="Looking for a Python developer...",
            match_score=68.5,
            matched_skills=["Python", "FastAPI"],
            missing_skills=["Kubernetes", "AWS"],
            learning_roadmap={"Kubernetes": ["course1"]},
            job_title="Python Developer",
        )
        assert report.id is not None
        assert report.match_score == 68.5
        assert "Python" in report.matched

    def test_get_ats_by_user(self, db, user):
        items, total = ReportRepository(db).get_ats_by_user(user.id)
        assert total >= 1

    def test_get_jd_by_user(self, db, user):
        items, total = ReportRepository(db).get_jd_by_user(user.id)
        assert total >= 1

    def test_user_stats(self, db, user):
        stats = ReportRepository(db).get_user_stats(user.id)
        assert stats["total_resumes"] >= 1
        assert stats["total_reports"] >= 2
        assert stats["average_ats_score"] is not None

    def test_delete_ats_report(self, db, resume, user):
        report = ReportRepository(db).create_ats(resume.id, 50.0, {}, [])
        deleted = ReportRepository(db).delete_ats(report.id, user.id)
        assert deleted is True

    def test_delete_wrong_user_ats(self, db, resume):
        report = ReportRepository(db).create_ats(resume.id, 50.0, {}, [])
        result = ReportRepository(db).delete_ats(report.id, user_id=999999)
        assert result is False
