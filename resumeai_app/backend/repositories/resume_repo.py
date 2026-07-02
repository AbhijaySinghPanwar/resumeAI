"""
backend/repositories/resume_repo.py — Data access layer for Resume.
"""
from __future__ import annotations

import json
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from database.models import Resume
from core.logger import get_logger

logger = get_logger(__name__)


class ResumeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        user_id: int,
        filename: str,
        parsed_json: dict,
        ats_score: Optional[float] = None,
        commit: bool = True,
    ) -> Resume:
        resume = Resume(
            user_id=user_id,
            filename=filename,
            parsed_json=json.dumps(parsed_json),
            ats_score=ats_score,
        )
        self.db.add(resume)
        if commit:
            self.db.commit()
            self.db.refresh(resume)
        else:
            self.db.flush()
            
        logger.info("Resume saved: id=%d user_id=%d filename=%s", resume.id, user_id, filename)
        return resume

    def get_by_id(self, resume_id: int) -> Optional[Resume]:
        return (
            self.db.query(Resume)
            .options(joinedload(Resume.ats_reports), joinedload(Resume.jd_reports))
            .filter(Resume.id == resume_id)
            .first()
        )

    def get_by_user(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
    ) -> Tuple[List[Resume], int]:
        """Return (resumes_page, total_count) for a user — newest first."""
        query = (
            self.db.query(Resume)
            .options(joinedload(Resume.ats_reports), joinedload(Resume.jd_reports))
            .filter(Resume.user_id == user_id)
        )
        if search:
            query = query.filter(Resume.filename.ilike(f"%{search}%"))

        total = query.count()
        items = (
            query
            .order_by(desc(Resume.uploaded_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def delete(self, resume_id: int, user_id: int) -> bool:
        resume = (
            self.db.query(Resume)
            .filter(Resume.id == resume_id, Resume.user_id == user_id)
            .first()
        )
        if not resume:
            return False
        self.db.delete(resume)
        self.db.commit()
        logger.info("Resume deleted: id=%d", resume_id)
        return True

    def exists_for_user(self, resume_id: int, user_id: int) -> bool:
        return (
            self.db.query(Resume.id)
            .filter(Resume.id == resume_id, Resume.user_id == user_id)
            .first()
        ) is not None
