from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.resume import ParsingStatus
from app.schemas.candidate import CandidateResponse


class WorkExperienceItem(BaseModel):
    company: str
    position: str
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: Optional[bool] = False
    description: Optional[str] = None
    highlights: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    institution: str
    degree: str
    field_of_study: Optional[str] = None
    start_year: Optional[str] = None
    end_year: Optional[str] = None
    grade_gpa: Optional[str] = None


class CertificationItem(BaseModel):
    name: str
    issuer: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    credential_id: Optional[str] = None


class ResumeParsedData(BaseModel):
    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    work_experiences: List[WorkExperienceItem] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    certifications: List[CertificationItem] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    total_experience_years: Optional[float] = 0.0
    parsed_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ResumeBase(BaseModel):
    file_name: str
    file_type: str


class ResumeCreate(ResumeBase):
    candidate_id: int
    file_path: str
    file_size_bytes: Optional[int] = None
    file_hash: Optional[str] = None


class ResumeUpdate(BaseModel):
    summary: Optional[str] = None
    skills: Optional[List[str]] = None
    work_experiences: Optional[List[Dict[str, Any]]] = None
    education: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[Dict[str, Any]]] = None
    languages: Optional[List[str]] = None
    raw_text: Optional[str] = None
    parsing_status: Optional[ParsingStatus] = None
    error_message: Optional[str] = None
    parsed_metadata: Optional[Dict[str, Any]] = None


class ResumeResponse(ResumeBase):
    id: int
    candidate_id: int
    file_path: str
    file_size_bytes: Optional[int] = None
    file_hash: Optional[str] = None
    parsing_status: ParsingStatus
    summary: Optional[str] = None
    skills: List[str] = []
    work_experiences: List[Dict[str, Any]] = []
    education: List[Dict[str, Any]] = []
    certifications: List[Dict[str, Any]] = []
    languages: List[str] = []
    raw_text: Optional[str] = None
    error_message: Optional[str] = None
    parsed_metadata: Optional[Dict[str, Any]] = None
    candidate: Optional[CandidateResponse] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
