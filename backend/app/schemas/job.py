from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.job import EmploymentType, ExperienceLevel


class JobDescriptionBase(BaseModel):
    title: str
    department: Optional[str] = None
    location: Optional[str] = None
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    experience_level: ExperienceLevel = ExperienceLevel.MID_LEVEL
    min_years_experience: Optional[int] = 0
    max_years_experience: Optional[int] = None
    description_raw: str
    responsibilities: Optional[str] = None
    qualifications: Optional[str] = None
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    metadata_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)
    is_active: Optional[bool] = True


class JobDescriptionCreate(JobDescriptionBase):
    pass


class JobDescriptionUpdate(BaseModel):
    title: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[EmploymentType] = None
    experience_level: Optional[ExperienceLevel] = None
    min_years_experience: Optional[int] = None
    max_years_experience: Optional[int] = None
    description_raw: Optional[str] = None
    responsibilities: Optional[str] = None
    qualifications: Optional[str] = None
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    metadata_fields: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class JobDescriptionResponse(JobDescriptionBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
