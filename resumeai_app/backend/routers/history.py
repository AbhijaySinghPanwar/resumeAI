"""
backend/routers/history.py — Resume history endpoints (authenticated).

GET    /history/resumes          — paginated list of user's resumes
GET    /history/resumes/{id}     — detail view with ATS + JD reports
DELETE /history/resumes/{id}     — delete a resume (cascades to reports)
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
from repositories.resume_repo import ResumeRepository
from services.auth_service import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/history", tags=["Resume History"])


@router.get(
    "/resumes",
    summary="List user's resume history",
    description=(
        "Returns a paginated list of all resumes uploaded by the authenticated user, "
        "sorted by upload date descending. Supports search and pagination."
    ),
)
def list_resumes(
    page: int      = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: str    = Query("", description="Filter by filename"),
    current_user: User    = Depends(get_current_user),
    db: Session           = Depends(get_db),
):
    repo = ResumeRepository(db)
    items, total = repo.get_by_user(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        search=search or None,
    )
    logger.info("Listing resumes for user_id=%d page=%d", current_user.id, page)
    return paginated(
        items=[r.to_dict() for r in items],
        total=total,
        page=page,
        page_size=page_size,
        message="Resume history retrieved.",
    )


@router.get(
    "/resumes/{resume_id}",
    summary="Get a single resume with its reports",
    description="Returns full parsed JSON and all associated ATS + JD reports.",
)
def get_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
    repo = ResumeRepository(db)
    resume = repo.get_by_id(resume_id)

    if not resume or resume.user_id != current_user.id:
        raise HTTPException(404, "Resume not found.")

    data = resume.to_dict(include_parsed=True)
    data["ats_reports"] = [r.to_dict() for r in resume.ats_reports]
    data["jd_reports"]  = [r.to_dict() for r in resume.jd_reports]

    return success(data=data, message="Resume retrieved.")


@router.delete(
    "/resumes/{resume_id}",
    summary="Delete a resume and all its reports",
    description="Permanently deletes the resume and all associated ATS/JD reports.",
)
def delete_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
    deleted = ResumeRepository(db).delete(resume_id, current_user.id)
    if not deleted:
        raise HTTPException(404, "Resume not found or not authorized.")
    logger.info("Resume deleted: id=%d user_id=%d", resume_id, current_user.id)
    return success(data=None, message="Resume deleted successfully.")
