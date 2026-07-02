"""
backend/repositories/report_repo.py — Data access for ATSReport and JDReport.
"""
from __future__ import annotations

import json
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.models import ATSReport, JDReport, Resume
from core.logger import get_logger

logger = get_logger(__name__)


class ReportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── ATSReport ─────────────────────────────────────────────────────────────

    def create_ats(
        self,
        resume_id: int,
        ats_score: float,
        ats_breakdown: dict,
        suggestions: Optional[list] = None,
        commit: bool = True,
    ) -> ATSReport:
        report = ATSReport(
            resume_id=resume_id,
            ats_score=ats_score,
            ats_breakdown=json.dumps(ats_breakdown),
            suggestions=json.dumps(suggestions or []),
        )
        self.db.add(report)
        if commit:
            self.db.commit()
            self.db.refresh(report)
        else:
            self.db.flush()
        logger.info("ATSReport saved: id=%d resume_id=%d score=%.1f", report.id, resume_id, ats_score)
        return report

    def get_ats_by_user(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[List[ATSReport], int]:
        """Return (ats_reports, total) for all resumes owned by this user — newest first."""
        query = (
            self.db.query(ATSReport)
            .join(Resume, ATSReport.resume_id == Resume.id)
            .filter(Resume.user_id == user_id)
        )
        total = query.count()
        items = (
            query
            .order_by(desc(ATSReport.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_ats_by_id(self, report_id: int, user_id: int) -> Optional[ATSReport]:
        return (
            self.db.query(ATSReport)
            .join(Resume)
            .filter(ATSReport.id == report_id, Resume.user_id == user_id)
            .first()
        )

    def delete_ats(self, report_id: int, user_id: int) -> bool:
        report = self.get_ats_by_id(report_id, user_id)
        if not report:
            return False
        self.db.delete(report)
        self.db.commit()
        return True

    # ── JDReport ──────────────────────────────────────────────────────────────

    def create_jd(
        self,
        resume_id: int,
        jd_text: str,
        match_score: float,
        matched_skills: list,
        missing_skills: list,
        learning_roadmap: Optional[dict] = None,
        job_title: Optional[str] = None,
        commit: bool = True,
    ) -> JDReport:
        report = JDReport(
            resume_id=resume_id,
            jd_text=jd_text,
            match_score=match_score,
            matched_skills=json.dumps(matched_skills),
            missing_skills=json.dumps(missing_skills),
            learning_roadmap=json.dumps(learning_roadmap or {}),
            job_title=job_title,
        )
        self.db.add(report)
        if commit:
            self.db.commit()
            self.db.refresh(report)
        else:
            self.db.flush()
        logger.info("JDReport saved: id=%d resume_id=%d score=%.1f", report.id, resume_id, match_score)
        return report

    def get_jd_by_user(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[List[JDReport], int]:
        query = (
            self.db.query(JDReport)
            .join(Resume, JDReport.resume_id == Resume.id)
            .filter(Resume.user_id == user_id)
        )
        total = query.count()
        items = (
            query
            .order_by(desc(JDReport.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def get_jd_by_id(self, report_id: int, user_id: int) -> Optional[JDReport]:
        return (
            self.db.query(JDReport)
            .join(Resume)
            .filter(JDReport.id == report_id, Resume.user_id == user_id)
            .first()
        )

    def delete_jd(self, report_id: int, user_id: int) -> bool:
        report = self.get_jd_by_id(report_id, user_id)
        if not report:
            return False
        self.db.delete(report)
        self.db.commit()
        return True

    # ── User Stats ────────────────────────────────────────────────────────────

    def get_user_stats(self, user_id: int) -> dict:
        """Return aggregated statistics for the dashboard stats cards."""
        from sqlalchemy import func

        total_resumes = (
            self.db.query(func.count(Resume.id))
            .filter(Resume.user_id == user_id)
            .scalar() or 0
        )
        avg_ats = (
            self.db.query(func.avg(ATSReport.ats_score))
            .join(Resume)
            .filter(Resume.user_id == user_id)
            .scalar()
        )
        avg_match = (
            self.db.query(func.avg(JDReport.match_score))
            .join(Resume)
            .filter(Resume.user_id == user_id)
            .scalar()
        )
        total_ats = (
            self.db.query(func.count(ATSReport.id))
            .join(Resume)
            .filter(Resume.user_id == user_id)
            .scalar() or 0
        )
        total_jd = (
            self.db.query(func.count(JDReport.id))
            .join(Resume)
            .filter(Resume.user_id == user_id)
            .scalar() or 0
        )
        return {
            "total_resumes": total_resumes,
            "average_ats_score": round(avg_ats, 1) if avg_ats else None,
            "average_match_score": round(avg_match, 1) if avg_match else None,
            "total_reports": total_ats + total_jd,
            "total_ats_reports": total_ats,
            "total_jd_reports": total_jd,
        }
