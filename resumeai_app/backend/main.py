"""
backend/main.py — FastAPI server for ResumeAI Parser v8.0.0
Endpoints:
  POST /api/parse        — upload PDF or plain text, returns full parse result
  POST /api/score        — score a parsed result against a JD
  POST /api/export       — export to greenhouse / lever / workday / csv
  POST /api/match        — Phase 2: full resume ↔ JD match analysis
  POST /api/parse_jd     — Phase 2: parse a raw job description
  GET  /api/health       — health check
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import time
import json
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from resumeai.pipeline import ResumeParser
from resumeai.ats.gate import ATSGate
from resumeai.ats.scorer import ResumeScorer
from resumeai.ats.exporters import (
    to_generic_json, to_greenhouse, to_lever, to_workday, to_csv_row
)

# ── Phase 2 imports ───────────────────────────────────────────────────────────
from resumeai.matching.jd_parser import parse_job_description
from resumeai.matching.skill_matcher import SkillMatcher
from resumeai.matching.gap_analyzer import generate_skill_gap
from resumeai.matching.roadmap_generator import generate_learning_roadmap

app = FastAPI(title="ResumeAI API", version="8.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

parser  = ResumeParser(strict_schema=False, include_debug=True)
gate    = ATSGate()
scorer  = ResumeScorer()
matcher = SkillMatcher()  # singleton — embedding model loaded once on first use


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "8.0.0"}


# ── Parse ─────────────────────────────────────────────────────────────────────

@app.post("/api/parse")
async def parse_resume(
    file: Optional[UploadFile] = File(None),
    text: Optional[str]        = Form(None),
):
    if file and file.filename:
        raw = await file.read()
        if file.filename.lower().endswith(".pdf"):
            result = parser.parse_pdf(raw)
        else:
            result = parser.parse_text(raw.decode("utf-8", errors="replace"))
    elif text:
        result = parser.parse_text(text)
    else:
        raise HTTPException(400, "Provide either a file upload or text field.")

    gate_decision = gate.evaluate(result)
    
    # Calculate deterministic ATS Score
    from resumeai.scoring.ats_scorer import ATSScorer
    ats_score_result = ATSScorer().score(result)

    return {
        "result":   result,
        "gate":     gate_decision.to_dict(),
        "ats_score": ats_score_result,
    }


# ── Score ─────────────────────────────────────────────────────────────────────

class ScoreRequest(BaseModel):
    parse_result: dict
    job_description: str

@app.post("/api/score")
def score_resume(req: ScoreRequest):
    report = scorer.score(req.parse_result, req.job_description)
    return report.to_dict()


# ── Export ────────────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    parse_result: dict
    format: str   # generic_json | greenhouse | lever | workday | csv

@app.post("/api/export")
def export_resume(req: ExportRequest):
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


# ── Phase 2: Parse JD ────────────────────────────────────────────────────────

class ParseJDRequest(BaseModel):
    job_description: str

@app.post("/api/parse_jd")
def parse_jd(req: ParseJDRequest):
    """
    Parse a raw job description into structured fields.
    Returns: title, required_skills, preferred_skills,
             experience_requirements, responsibilities, keywords
    """
    if not req.job_description.strip():
        raise HTTPException(400, "job_description must not be empty.")
    parsed = parse_job_description(req.job_description)
    return parsed.to_dict()


# ── Phase 2: Match ────────────────────────────────────────────────────────────

class MatchRequest(BaseModel):
    parse_result: dict
    job_description: str

@app.post("/api/match")
def match_resume(req: MatchRequest):
    """
    Full resume ↔ job description matching analysis.

    Input:
        parse_result:    Dict returned by /api/parse
        job_description: Raw JD text string

    Response:
        match_score:          Overall weighted score 0-100
        match_grade:          A+ / A / B+ / B / C / D
        component_scores:     skills / semantic / experience / education
        matched_skills:       Skills present in both resume and JD
        missing_skills:       Required JD skills absent from resume
        recommended_skills:   Preferred JD skills also absent
        recommended_learning: Curated learning resources for missing skills
        parsed_jd:            Structured JD for frontend display
    """
    if not req.job_description.strip():
        raise HTTPException(400, "job_description must not be empty.")
    if not req.parse_result:
        raise HTTPException(400, "parse_result must not be empty.")

    try:
        parsed_jd = parse_job_description(req.job_description)
        result = matcher.calculate_match_score(req.parse_result, parsed_jd)

        return {
            **result.to_dict(),
            "parsed_jd": parsed_jd.to_dict(),
        }
    except Exception as e:
        raise HTTPException(500, f"Matching engine error: {str(e)}")


# ── Phase 3: AI Services ───────────────────────────────────────────────────────

import logging

# Ensure the backend directory is on sys.path so 'services' is importable
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from services.gemini_service import GeminiService
from services.bullet_improver import BulletImprover
from services.project_enhancer import ProjectEnhancer
from services.interview_generator import InterviewGenerator

logging.basicConfig(level=logging.INFO)

_gemini   = GeminiService()
_bullet   = BulletImprover(_gemini)
_enhancer = ProjectEnhancer(_gemini)
_interview = InterviewGenerator(_gemini)


# ── Pydantic models ───────────────────────────────────────────────────────────

class BulletRequest(BaseModel):
    bullet: str
    context: str = "experience"   # "project" | "experience"

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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/ai/improve-bullet", response_model=BulletResponse)
def improve_bullet(req: BulletRequest):
    """
    Rewrite a resume bullet into ATS-optimized, professional, and concise variants.
    """
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


@app.post("/ai/enhance-project", response_model=ProjectResponse)
def enhance_project(req: ProjectRequest):
    """
    Rewrite a project description into ATS, technical, and recruiter variants.
    """
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


@app.post("/ai/interview-questions", response_model=InterviewResponse)
def generate_interview_questions(req: InterviewRequest):
    """
    Generate personalized technical, project, and behavioral interview questions.
    """
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


@app.get("/ai/status")
def ai_status():
    """
    Check Gemini API availability and report the active model.

    Returns:
        { "available": true,  "active_model": "models/gemini-2.5-flash" }
        { "available": false, "active_model": null }
    """
    return _gemini.status_dict()
