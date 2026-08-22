from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.screening_result import ScreeningStatus
from app.models.user import User
from app.schemas.screening_result import (
    BatchScreeningRequest,
    ScreeningResultCreate,
    ScreeningResultResponse,
    ScreeningResultUpdate,
)
from app.services.resume_service import resume_service

router = APIRouter(prefix="/screening", tags=["Screening & Matching"])


@router.post("/jobs/{job_id}/apply/{resume_id}", response_model=ScreeningResultResponse)
async def submit_resume_for_job(
    job_id: int,
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Link a candidate resume to a job description for screening."""
    return await resume_service.apply_to_job(db, job_id=job_id, resume_id=resume_id)


@router.get("/jobs/{job_id}/candidates", response_model=List[ScreeningResultResponse])
async def list_job_candidates(
    job_id: int,
    status_filter: Optional[ScreeningStatus] = Query(None, alias="status"),
    min_score: Optional[float] = Query(None, ge=0.0, le=100.0),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get ranked candidate screening results for a job description.
    Sorted by highest match score first.
    """
    return await resume_service.get_job_screenings(
        db,
        job_id=job_id,
        status=status_filter,
        min_score=min_score,
        skip=skip,
        limit=limit,
    )
