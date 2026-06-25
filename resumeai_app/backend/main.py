"""
backend/main.py — FastAPI server for ResumeAI v4.0.0
Phases 1–4: Parse → ATS → JD Match → Gemini AI → Auth → History → Reports → Export

Existing Phase 1–3 endpoints remain fully backward-compatible.
New Phase 4 endpoints are added without modifying existing response formats.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import time
import json
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── Ensure backend dir is on path (for services/, repositories/, etc.) ─────────
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# ── Core ───────────────────────────────────────────────────────────────────────
from core.config import settings
from core.logger import get_logger

import logging
logging.basicConfig(level=logging.INFO)
logger = get_logger(__name__)

# ── Database setup (create tables via Alembic; also keep create_all as safety net) ──
from database.engine import engine, get_db
from database.models import Base

# Run migrations if alembic is configured, otherwise fall back to create_all
try:
    from alembic.config import Config as AlembicConfig
    from alembic import command as alembic_command
    _alembic_cfg_path = os.path.join(_backend_dir, "alembic.ini")
    if os.path.exists(_alembic_cfg_path):
        _alembic_cfg = AlembicConfig(_alembic_cfg_path)
        alembic_command.upgrade(_alembic_cfg, "head")
        logger.info("Database migrated to latest version via Alembic.")
    else:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created via SQLAlchemy (no alembic.ini found).")
except Exception as _e:
    logger.warning("Alembic migration skipped (%s) — using create_all fallback.", _e)
    Base.metadata.create_all(bind=engine)

# ── ResumeAI core imports ──────────────────────────────────────────────────────
from resumeai.pipeline import ResumeParser
from resumeai.ats.gate import ATSGate
from resumeai.ats.scorer import ResumeScorer
from resumeai.ats.exporters import (
    to_generic_json, to_greenhouse, to_lever, to_workday, to_csv_row
)
from resumeai.matching.jd_parser import parse_job_description
from resumeai.matching.skill_matcher import SkillMatcher
from resumeai.matching.gap_analyzer import generate_skill_gap
from resumeai.matching.roadmap_generator import generate_learning_roadmap

# ── Phase 3: AI Services ───────────────────────────────────────────────────────
from services.gemini_service import GeminiService
from services.bullet_improver import BulletImprover
from services.project_enhancer import ProjectEnhancer
from services.interview_generator import InterviewGenerator

# ── Phase 4: Auth dependency ───────────────────────────────────────────────────
from services.auth_service import get_optional_user
from repositories.resume_repo import ResumeRepository
from repositories.report_repo import ReportRepository
from sqlalchemy.orm import Session

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ResumeAI API",
    version="4.0.0",
    description=(
        "ResumeAI — Intelligent Resume Intelligence Platform. "
        "Parse, score, match, improve with AI, and manage resume history."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singletons ────────────────────────────────────────────────────────────────
parser  = ResumeParser(strict_schema=False, include_debug=True)
gate    = ATSGate()
scorer  = ResumeScorer()
matcher = SkillMatcher()

_gemini    = GeminiService()
_bullet    = BulletImprover(_gemini)
_enhancer  = ProjectEnhancer(_gemini)
_interview = InterviewGenerator(_gemini)

# ── Phase 4 Routers ───────────────────────────────────────────────────────────
from routers.auth    import router as auth_router
from routers.history import router as history_router
from routers.reports import router as reports_router
from routers.export  import router as export_router

app.include_router(auth_router)
app.include_router(history_router)
app.include_router(reports_router)
app.include_router(export_router)

logger.info("ResumeAI v4.0.0 started. Gemini: %s", _gemini.active_model or "fallback")


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Request/Response Models (defined before routes that reference them)
# ─────────────────────────────────────────────────────────────────────────────

class ScoreRequest(BaseModel):
    parse_result: dict
    job_description: str

class ExportRequest(BaseModel):
    parse_result: dict
    format: str

class ParseJDRequest(BaseModel):
    job_description: str

class MatchRequest(BaseModel):
    parse_result: dict
    job_description: str
    resume_id: Optional[int] = None   # Phase 4: if provided, saves JD report

class BulletRequest(BaseModel):
    bullet: str
    context: str = "experience"

class BulletResponse(BaseModel):
    ats_version: str
    professional_version: str
    concise_version: str

class ProjectRequest(BaseModel):
    project_name: str
    description: str

class ProjectResponse(BaseModel):
    ats_version: str
    technical_version: str
    recruiter_version: str

class InterviewRequest(BaseModel):
    resume_data: dict
    job_description: str

class InterviewResponse(BaseModel):
    technical_questions: list
    project_questions: list
    behavioral_questions: list


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1–3 Endpoints  (response format UNCHANGED for backward compatibility)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["System"],
         summary="Health check", description="Returns server status and version.")
def health():
    return {"status": "ok", "version": "4.0.0"}


@app.post("/api/parse", tags=["Resume Parsing"],
          summary="Parse a resume PDF or plain text",
          description=(
              "Upload a PDF/DOCX file or paste plain text. Returns full structured parse result, "
              "ATS gate decision, and ATS score. If a valid JWT is present, the resume and ATS "
              "report are automatically saved to the database."
          ))
async def parse_resume(
    file: Optional[UploadFile] = File(None),
    text: Optional[str]        = Form(None),
    current_user               = Depends(get_optional_user),
    db: Session                = Depends(get_db),
):
    if file and file.filename:
        raw = await file.read()
        filename = file.filename
        if file.filename.lower().endswith(".pdf"):
            result = parser.parse_pdf(raw)
        else:
            result = parser.parse_text(raw.decode("utf-8", errors="replace"))
    elif text:
        result = parser.parse_text(text)
        filename = "plain_text.txt"
    else:
        raise HTTPException(400, "Provide either a file upload or text field.")

    gate_decision = gate.evaluate(result)

    from resumeai.scoring.ats_scorer import ATSScorer
    ats_score_result = ATSScorer().score(result)

    # ── Auto-save when authenticated ──────────────────────────────────────
    saved_resume_id = None
    if current_user:
        try:
            resume = ResumeRepository(db).create(
                user_id=current_user.id,
                filename=filename,
                parsed_json=result,
                ats_score=ats_score_result.get("overall_score"),
            )
            ReportRepository(db).create_ats(
                resume_id=resume.id,
                ats_score=ats_score_result.get("overall_score", 0),
                ats_breakdown=ats_score_result.get("breakdown", {}),
                suggestions=ats_score_result.get("improvements", []),
            )
            saved_resume_id = resume.id
            logger.info("Auto-saved resume: id=%d user_id=%d", resume.id, current_user.id)
        except Exception as exc:
            logger.warning("Auto-save failed (non-fatal): %s", exc)

    response = {
        "result":   result,
        "gate":     gate_decision.to_dict(),
        "ats_score": ats_score_result,
    }
    if saved_resume_id:
        response["saved_resume_id"] = saved_resume_id

    return response


@app.post("/api/score", tags=["ATS Scoring"],
          summary="Score a parsed resume against a job description",
          description="Accepts a parsed resume dict and a JD text string. Returns detailed score breakdown.")
def score_resume(req: "ScoreRequest"):
    report = scorer.score(req.parse_result, req.job_description)
    return report.to_dict()


@app.post("/api/export", tags=["Legacy Export"],
          summary="Export resume to ATS formats",
          description="Export to Greenhouse, Lever, Workday, CSV, or generic JSON.")
def export_resume(req: "ExportRequest"):
    fmt = req.format.lower()
    r   = req.parse_result
    if fmt == "greenhouse":
        return to_greenhouse(r)
    elif fmt == "lever":
        return to_lever(r)
    elif fmt == "workday":
        return to_workday(r)
    elif fmt == "csv":
        return {"csv": to_csv_row(r)}
    else:
        return json.loads(to_generic_json(r, strip_debug=True))


@app.post("/api/parse_jd", tags=["JD Matching"],
          summary="Parse a raw job description",
          description="Extracts structured fields from a job description text.")
def parse_jd(req: "ParseJDRequest"):
    if not req.job_description.strip():
        raise HTTPException(400, "job_description must not be empty.")
    parsed = parse_job_description(req.job_description)
    return parsed.to_dict()


@app.post("/api/match", tags=["JD Matching"],
          summary="Match a resume to a job description",
          description=(
              "Full resume ↔ JD match analysis. Returns match score, grade, component scores, "
              "matched/missing skills, and learning roadmap. If authenticated, saves the JD report."
          ))
def match_resume(
    req: "MatchRequest",
    current_user = Depends(get_optional_user),
    db: Session  = Depends(get_db),
):
    if not req.job_description.strip():
        raise HTTPException(400, "job_description must not be empty.")
    if not req.parse_result:
        raise HTTPException(400, "parse_result must not be empty.")

    try:
        parsed_jd = parse_job_description(req.job_description)
        result = matcher.calculate_match_score(req.parse_result, parsed_jd)

        # Auto-save JD report if authenticated and a resume_id is provided
        if current_user and req.resume_id:
            try:
                jd_title = parsed_jd.to_dict().get("title", "")
                match_dict = result.to_dict()
                ReportRepository(db).create_jd(
                    resume_id=req.resume_id,
                    jd_text=req.job_description,
                    match_score=match_dict.get("match_score", 0),
                    matched_skills=match_dict.get("matched_skills", []),
                    missing_skills=match_dict.get("missing_skills", []),
                    learning_roadmap=match_dict.get("recommended_learning", {}),
                    job_title=jd_title,
                )
                logger.info("Auto-saved JD report: user_id=%d", current_user.id)
            except Exception as exc:
                logger.warning("JD auto-save failed (non-fatal): %s", exc)

        return {
            **result.to_dict(),
            "parsed_jd": parsed_jd.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Matching engine error: {str(e)}")


# ── Phase 3 AI Endpoints (UNCHANGED) ─────────────────────────────────────────

@app.post("/ai/improve-bullet", tags=["AI Assistant"],
          summary="Rewrite a resume bullet with AI",
          description="Returns 3 variants: ATS-optimized, professional, and concise.")
def improve_bullet(req: "BulletRequest"):
    if not req.bullet or not req.bullet.strip():
        raise HTTPException(400, "bullet must not be empty")
    try:
        result = _bullet.improve(req.bullet, req.context)
        return BulletResponse(**result)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Bullet improver error: {str(exc)}")


@app.post("/ai/enhance-project", tags=["AI Assistant"],
          summary="Enhance a project description with AI",
          description="Returns ATS, technical, and recruiter variants of the project description.")
def enhance_project(req: "ProjectRequest"):
    if not req.project_name or not req.project_name.strip():
        raise HTTPException(400, "project_name must not be empty")
    if not req.description or not req.description.strip():
        raise HTTPException(400, "description must not be empty")
    try:
        result = _enhancer.enhance(req.project_name, req.description)
        return ProjectResponse(**result)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Project enhancer error: {str(exc)}")


@app.post("/ai/interview-questions", tags=["AI Assistant"],
          summary="Generate personalized interview questions",
          description="AI-generated technical, project, and behavioral questions based on resume + JD.")
def generate_interview_questions(req: "InterviewRequest"):
    if not req.resume_data:
        raise HTTPException(400, "resume_data must not be empty")
    if not req.job_description or not req.job_description.strip():
        raise HTTPException(400, "job_description must not be empty")
    try:
        result = _interview.generate(req.resume_data, req.job_description)
        return InterviewResponse(**result)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Interview generator error: {str(exc)}")


@app.get("/ai/status", tags=["AI Assistant"],
         summary="Check Gemini API status",
         description="Returns availability and the currently active model name.")
def ai_status():
    return _gemini.status_dict()
