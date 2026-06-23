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

