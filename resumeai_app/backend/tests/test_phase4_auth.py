"""
tests/test_phase4_auth.py — Phase 4 Authentication tests.

Covers:
  - Signup (success, duplicate email, validation)
  - Login (success, wrong password, unknown email)
  - /auth/me (authenticated, unauthenticated)
  - /auth/logout
  - /auth/stats
  - JWT token lifecycle
  - Protected routes reject unauthenticated requests
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Test DB: isolated in-memory SQLite ───────────────────────────────────────
TEST_DB_URL = "sqlite:///./test_phase4.db"

from database.engine import Base, get_db
from main import app

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


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    """Signup + login and return Bearer headers."""
    client.post("/auth/signup", json={
        "name": "Test User",
        "email": "testuser@example.com",
        "password": "testpassword123",
    })
    resp = client.post("/auth/login", json={
        "email": "testuser@example.com",
        "password": "testpassword123",
    })
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Signup ────────────────────────────────────────────────────────────────────

class TestSignup:
    def test_signup_success(self, client):
        import time
        unique_email = f"newuser_{int(time.time())}@example.com"
        resp = client.post("/auth/signup", json={
            "name": "Alice Smith",
            "email": unique_email,
            "password": "alicepassword123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert data["data"]["user"]["email"] == unique_email

    def test_signup_duplicate_email(self, client):
        client.post("/auth/signup", json={
            "name": "Bob Jones",
            "email": "bob@example.com",
            "password": "bobpassword123",
        })
        resp = client.post("/auth/signup", json={
            "name": "Bob Jones 2",
            "email": "bob@example.com",
            "password": "bobpassword456",
        })
        assert resp.status_code == 409

    def test_signup_missing_name(self, client):
        resp = client.post("/auth/signup", json={
            "email": "noname@example.com",
            "password": "testpassword123",
        })
        assert resp.status_code == 422

    def test_signup_short_password(self, client):
        resp = client.post("/auth/signup", json={
            "name": "Short Pass",
            "email": "short@example.com",
            "password": "abc",
        })
        assert resp.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_success(self, client):
        client.post("/auth/signup", json={
            "name": "Login Test",
            "email": "logintest@example.com",
            "password": "loginpassword123",
        })
        resp = client.post("/auth/login", json={
            "email": "logintest@example.com",
            "password": "loginpassword123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert data["data"]["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        resp = client.post("/auth/login", json={
            "email": "logintest@example.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_login_unknown_email(self, client):
        resp = client.post("/auth/login", json={
            "email": "nobody@example.com",
            "password": "doesntmatter",
        })
        assert resp.status_code == 401


# ── Auth/Me ───────────────────────────────────────────────────────────────────

class TestMe:
    def test_me_authenticated(self, client, auth_headers):
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "email" in data["data"]

    def test_me_unauthenticated(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client):
        resp = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401


# ── Logout ────────────────────────────────────────────────────────────────────

class TestLogout:
    def test_logout_authenticated(self, client, auth_headers):
        resp = client.post("/auth/logout", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_logout_unauthenticated(self, client):
        resp = client.post("/auth/logout")
        assert resp.status_code == 401


# ── Stats ─────────────────────────────────────────────────────────────────────

class TestStats:
    def test_stats_authenticated(self, client, auth_headers):
        resp = client.get("/auth/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "total_resumes" in data["data"]
        assert "average_ats_score" in data["data"]
        assert "total_reports" in data["data"]

    def test_stats_unauthenticated(self, client):
        resp = client.get("/auth/stats")
        assert resp.status_code == 401


# ── Protected Routes ──────────────────────────────────────────────────────────

class TestProtectedRoutes:
    def test_history_resumes_requires_auth(self, client):
        resp = client.get("/history/resumes")
        assert resp.status_code == 401

    def test_reports_ats_requires_auth(self, client):
        resp = client.get("/reports/ats")
        assert resp.status_code == 401

    def test_reports_jd_requires_auth(self, client):
        resp = client.get("/reports/jd")
        assert resp.status_code == 401

    def test_delete_nonexistent_resume(self, client, auth_headers):
        resp = client.delete("/history/resumes/999999", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_nonexistent_ats_report(self, client, auth_headers):
        resp = client.get("/reports/ats/999999", headers=auth_headers)
        assert resp.status_code == 404
