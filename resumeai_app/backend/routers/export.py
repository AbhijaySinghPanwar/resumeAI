"""
backend/routers/export.py — Export endpoints (PDF / JSON / CSV).

POST /export/pdf    — generate and download a PDF analysis report
POST /export/json   — download a structured JSON report
POST /export/csv    — download a CSV summary
"""
from __future__ import annotations

import os, sys
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.responses import success
from core.logger import get_logger
from database.engine import get_db
from database.models import User
from services.export_service import generate_pdf, generate_json, generate_csv
from services.auth_service import get_current_user, get_optional_user

import io

logger = get_logger(__name__)

router = APIRouter(prefix="/export", tags=["Export"])


# ── Request Model ─────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    """
    Payload for all export endpoints.
    Accepts the raw analysis data returned by /api/parse, /api/score, and /api/match.
    """
    candidate: dict = {}
    ats_analysis: dict = {}
    jd_match: dict = {}
    skills: dict = {}
    projects: List[dict] = []
    recommendations: List[str] = []


# ── PDF ───────────────────────────────────────────────────────────────────────

@router.post(
    "/pdf",
    summary="Export analysis as PDF",
    description=(
        "Generate a professionally formatted PDF report containing the candidate's "
        "ATS score, breakdown, skills, projects, JD match, and recommendations."
    ),
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF file"},
    },
)
def export_pdf(
    req: ExportRequest,
    current_user: Optional[User] = Depends(get_optional_user),
):
    try:
        pdf_bytes = generate_pdf(req.model_dump())
        name = req.candidate.get("name", "resume").replace(" ", "_").lower()
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"resumeai_{name}_{ts}.pdf"

        logger.info(
            "PDF export generated: user_id=%s filename=%s size=%d",
            current_user.id if current_user else "guest",
            filename,
            len(pdf_bytes),
        )
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as exc:
        logger.error("PDF generation error: %s", exc, exc_info=True)
        raise HTTPException(500, f"PDF generation failed: {exc}")


# ── JSON ──────────────────────────────────────────────────────────────────────

@router.post(
    "/json",
    summary="Export analysis as JSON",
    description="Download a structured JSON file containing all analysis data.",
)
def export_json(
    req: ExportRequest,
    current_user: Optional[User] = Depends(get_optional_user),
):
    try:
        data = generate_json(req.model_dump())
        name = req.candidate.get("name", "resume").replace(" ", "_").lower()
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"resumeai_{name}_{ts}.json"

        import json
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        logger.info("JSON export generated: user_id=%s", current_user.id if current_user else "guest")
        return StreamingResponse(
            io.BytesIO(json_str.encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as exc:
        logger.error("JSON export error: %s", exc, exc_info=True)
        raise HTTPException(500, f"JSON export failed: {exc}")


# ── CSV ───────────────────────────────────────────────────────────────────────

@router.post(
    "/csv",
    summary="Export analysis as CSV",
    description="Download a CSV file summarizing key resume metrics and scores.",
)
def export_csv(
    req: ExportRequest,
    current_user: Optional[User] = Depends(get_optional_user),
):
    try:
        csv_str = generate_csv(req.model_dump())
        name = req.candidate.get("name", "resume").replace(" ", "_").lower()
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"resumeai_{name}_{ts}.csv"

        logger.info("CSV export generated: user_id=%s", current_user.id if current_user else "guest")
        return StreamingResponse(
            io.BytesIO(csv_str.encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as exc:
        logger.error("CSV export error: %s", exc, exc_info=True)
        raise HTTPException(500, f"CSV export failed: {exc}")
