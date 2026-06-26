"""
backend/database/models.py — SQLAlchemy ORM models for Phase 4.

Schema:
    User (1) ──< Resume (many)
    Resume (1) ──< ATSReport (many)
    Resume (1) ──< JDReport  (many)

Indexes are created on all commonly-queried foreign key + timestamp columns.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    String, Text, Integer, Float, Boolean,
    DateTime, ForeignKey, Index, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.engine import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── User ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[int]           = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str]         = mapped_column(String(120), nullable=False)
    email: Mapped[str]        = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str]= mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    is_active: Mapped[bool]   = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    resumes: Mapped[List["Resume"]] = relationship(
        "Resume", back_populates="user", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
        }


# ── Resume ────────────────────────────────────────────────────────────────────

class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int]            = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str]      = mapped_column(String(255), nullable=False)
    parsed_json: Mapped[str]   = mapped_column(Text, nullable=False)   # JSON string
    ats_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )
    user_id: Mapped[int]       = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Relationships
    user: Mapped["User"]           = relationship("User", back_populates="resumes")
    ats_reports: Mapped[List["ATSReport"]] = relationship(
        "ATSReport", back_populates="resume", cascade="all, delete-orphan"
    )
    jd_reports: Mapped[List["JDReport"]] = relationship(
        "JDReport", back_populates="resume", cascade="all, delete-orphan"
    )

    # Composite index for user_id + uploaded_at (common sort query)
    __table_args__ = (
        Index("ix_resumes_user_uploaded", "user_id", "uploaded_at"),
    )

    @property
    def parsed(self) -> dict:
        return json.loads(self.parsed_json)

    def to_dict(self, include_parsed: bool = False) -> dict:
        jd_score = None
        if self.jd_reports:
            jd_score = max(r.match_score for r in self.jd_reports)
            
        d = {
            "id": self.id,
            "filename": self.filename,
            "ats_score": self.ats_score,
            "jd_score": jd_score,
            "uploaded_at": self.uploaded_at.isoformat(),
            "user_id": self.user_id,
            "ats_report_count": len(self.ats_reports) if self.ats_reports else 0,
            "jd_report_count": len(self.jd_reports) if self.jd_reports else 0,
        }
        if include_parsed:
            d["parsed_json"] = self.parsed
        return d


# ── ATSReport ─────────────────────────────────────────────────────────────────

class ATSReport(Base):
    __tablename__ = "ats_reports"

    id: Mapped[int]             = mapped_column(Integer, primary_key=True, index=True)
    ats_score: Mapped[float]    = mapped_column(Float, nullable=False)
    ats_breakdown: Mapped[str]  = mapped_column(Text, nullable=False)   # JSON string
    suggestions: Mapped[str]    = mapped_column(Text, nullable=True)    # JSON string
    created_at: Mapped[datetime]= mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )
    resume_id: Mapped[int]      = mapped_column(
        Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Relationships
    resume: Mapped["Resume"] = relationship("Resume", back_populates="ats_reports")

    __table_args__ = (
        Index("ix_ats_reports_resume_created", "resume_id", "created_at"),
    )

    @property
    def breakdown(self) -> dict:
        return json.loads(self.ats_breakdown)

    @property
    def suggestions_list(self) -> list:
        return json.loads(self.suggestions) if self.suggestions else []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ats_score": self.ats_score,
            "ats_breakdown": self.breakdown,
            "suggestions": self.suggestions_list,
            "created_at": self.created_at.isoformat(),
            "resume_id": self.resume_id,
        }


# ── JDReport ──────────────────────────────────────────────────────────────────

class JDReport(Base):
    __tablename__ = "jd_reports"

    id: Mapped[int]               = mapped_column(Integer, primary_key=True, index=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    jd_text: Mapped[str]          = mapped_column(Text, nullable=False)
    match_score: Mapped[float]    = mapped_column(Float, nullable=False)
    matched_skills: Mapped[str]   = mapped_column(Text, nullable=False)   # JSON array
    missing_skills: Mapped[str]   = mapped_column(Text, nullable=False)   # JSON array
    learning_roadmap: Mapped[str] = mapped_column(Text, nullable=True)    # JSON
    created_at: Mapped[datetime]  = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )
    resume_id: Mapped[int]        = mapped_column(
        Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Relationships
    resume: Mapped["Resume"] = relationship("Resume", back_populates="jd_reports")

    __table_args__ = (
        Index("ix_jd_reports_resume_created", "resume_id", "created_at"),
    )

    @property
    def matched(self) -> list:
        return json.loads(self.matched_skills)

    @property
    def missing(self) -> list:
        return json.loads(self.missing_skills)

    @property
    def roadmap(self) -> dict:
        return json.loads(self.learning_roadmap) if self.learning_roadmap else {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_title": self.job_title,
            "jd_text": self.jd_text[:500] + "..." if len(self.jd_text) > 500 else self.jd_text,
            "match_score": self.match_score,
            "matched_skills": self.matched,
            "missing_skills": self.missing,
            "learning_roadmap": self.roadmap,
            "created_at": self.created_at.isoformat(),
            "resume_id": self.resume_id,
        }
