from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.screening_result import ScreeningStatus
from app.schemas.job import JobDescriptionResponse
from app.schemas.resume import ResumeResponse


class ScreeningResultBase(BaseModel):
    job_id: int
    resume_id: int
    match_score: float = 0.0
    skills_match_score: Optional[float] = 0.0
    experience_match_score: Optional[float] = 0.0
    education_match_score: Optional[float] = 0.0
    analysis_summary: Optional[str] = None
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    detailed_feedback: Optional[Dict[str, Any]] = Field(default_factory=dict)
    status: ScreeningStatus = ScreeningStatus.SCREENED
    notes: Optional[str] = None


class ScreeningResultCreate(ScreeningResultBase):
    pass


class ScreeningResultUpdate(BaseModel):
    match_score: Optional[float] = None
    skills_match_score: Optional[float] = None
    experience_match_score: Optional[float] = None
    education_match_score: Optional[float] = None
    analysis_summary: Optional[str] = None
    matched_skills: Optional[List[str]] = None
    missing_skills: Optional[List[str]] = None
    detailed_feedback: Optional[Dict[str, Any]] = None
    status: Optional[ScreeningStatus] = None
    notes: Optional[str] = None


class ScreeningResultResponse(ScreeningResultBase):
    id: int
    created_at: datetime
    updated_at: datetime
    job: Optional[JobDescriptionResponse] = None
    resume: Optional[ResumeResponse] = None

    model_config = ConfigDict(from_attributes=True)


class BatchScreeningRequest(BaseModel):
    job_id: int
    resume_ids: List[int]
