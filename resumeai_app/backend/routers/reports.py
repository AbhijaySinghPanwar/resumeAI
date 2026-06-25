"""
backend/routers/reports.py — Saved ATS and JD reports (authenticated).

GET    /reports/ats              — paginated ATS reports
GET    /reports/ats/{id}         — single ATS report
DELETE /reports/ats/{id}         — delete ATS report
GET    /reports/jd               — paginated JD reports
GET    /reports/jd/{id}          — single JD report
DELETE /reports/jd/{id}          — delete JD report
"""
from __future__ import annotations

import os, sys
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.responses import paginated, success
from core.logger import get_logger
from database.engine import get_db
from database.models import User
from repositories.report_repo import ReportRepository
from services.auth_service import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/reports", tags=["Saved Reports"])


# ── ATS Reports ───────────────────────────────────────────────────────────────

@router.get(
    "/ats",
    summary="List saved ATS reports",
    description="Returns a paginated list of all ATS analyses saved for the authenticated user.",
)
def list_ats_reports(
    page: int      = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
    items, total = ReportRepository(db).get_ats_by_user(
        user_id=current_user.id, page=page, page_size=page_size
    )
    return paginated(
        items=[r.to_dict() for r in items],
        total=total, page=page, page_size=page_size,
        message="ATS reports retrieved.",
    )


@router.get("/ats/{report_id}", summary="Get a single ATS report")
def get_ats_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
    report = ReportRepository(db).get_ats_by_id(report_id, current_user.id)
    if not report:
        raise HTTPException(404, "ATS report not found.")
    return success(data=report.to_dict(), message="ATS report retrieved.")


@router.delete("/ats/{report_id}", summary="Delete an ATS report")
def delete_ats_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
    deleted = ReportRepository(db).delete_ats(report_id, current_user.id)
    if not deleted:
        raise HTTPException(404, "ATS report not found.")
    logger.info("ATSReport deleted: id=%d user_id=%d", report_id, current_user.id)
    return success(data=None, message="ATS report deleted.")


# ── JD Reports ────────────────────────────────────────────────────────────────

@router.get(
    "/jd",
    summary="List saved JD match reports",
    description="Returns a paginated list of all Job Description match analyses.",
)
def list_jd_reports(
    page: int      = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
    items, total = ReportRepository(db).get_jd_by_user(
        user_id=current_user.id, page=page, page_size=page_size
    )
    return paginated(
        items=[r.to_dict() for r in items],
        total=total, page=page, page_size=page_size,
        message="JD reports retrieved.",
    )


@router.get("/jd/{report_id}", summary="Get a single JD match report")
def get_jd_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
    report = ReportRepository(db).get_jd_by_id(report_id, current_user.id)
    if not report:
        raise HTTPException(404, "JD report not found.")
    return success(data=report.to_dict(), message="JD report retrieved.")


@router.delete("/jd/{report_id}", summary="Delete a JD match report")
def delete_jd_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
    deleted = ReportRepository(db).delete_jd(report_id, current_user.id)
    if not deleted:
        raise HTTPException(404, "JD report not found.")
    logger.info("JDReport deleted: id=%d user_id=%d", report_id, current_user.id)
    return success(data=None, message="JD report deleted.")
