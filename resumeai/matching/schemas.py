"""
matching/schemas.py — Pydantic schemas for Phase 2 Job Matching Engine.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ComponentScores(BaseModel):
    skills: Optional[float] = Field(None, description="Skill overlap score 0-100. None if no skills extracted.")
    semantic: float = Field(..., description="Semantic similarity score 0-100")
    experience: float = Field(..., description="Experience alignment score 0-100")
    education: Union[float, str] = Field(..., description="Education alignment score 0-100 or 'Not Applicable'")


class MatchResult(BaseModel):
    match_score: int = Field(..., description="Overall weighted match score 0-100")
    match_grade: str = Field(..., description="Letter grade: A+, A, B+, B, C, D")
    component_scores: ComponentScores
    matched_skills: List[str]
    missing_skills: List[str]
    recommended_skills: List[str]
    recommended_learning: List["RoadmapItem"]
    debug_info: Optional[Dict] = Field(None, description="Full scoring trace for debugging")

    def to_dict(self) -> dict:
        return self.model_dump()



class RoadmapItem(BaseModel):
    skill: str
    resource_type: str = Field(..., description="certification | course | project | book")
    recommendation: str
    url: Optional[str] = None
    estimated_time: Optional[str] = None
    difficulty: Optional[str] = None


class SkillGapResult(BaseModel):
    matched_skills: List[str]
    missing_skills: List[str]
    recommended_skills: List[str]
    match_percentage: float

    def to_dict(self) -> dict:
        return self.model_dump()


class ParsedJD(BaseModel):
    title: str = ""
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    experience_requirements: List[str] = Field(default_factory=list)
    education_requirements: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)

    def to_dict(self) -> dict:
        return self.model_dump()


MatchResult.model_rebuild()
