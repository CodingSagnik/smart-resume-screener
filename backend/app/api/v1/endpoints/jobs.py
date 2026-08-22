from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.job import (
    JobDescriptionCreate,
    JobDescriptionResponse,
    JobDescriptionUpdate,
)
from app.services.job_service import job_service

router = APIRouter(prefix="/jobs", tags=["Job Descriptions"])


@router.post("/", response_model=JobDescriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_job_description(
    job_in: JobDescriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new job description."""
    return await job_service.create_job(db, job_in=job_in, current_user=current_user)


@router.get("/", response_model=List[JobDescriptionResponse])
async def list_job_descriptions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """List job descriptions."""
    return await job_service.list_jobs(db, skip=skip, limit=limit, active_only=active_only)


@router.get("/{job_id}", response_model=JobDescriptionResponse)
async def get_job_description(
    job_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get single job description by ID."""
    return await job_service.get_job_by_id(db, job_id=job_id)


@router.put("/{job_id}", response_model=JobDescriptionResponse)
async def update_job_description(
    job_id: int,
    job_update: JobDescriptionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update job description."""
    return await job_service.update_job(
        db, job_id=job_id, job_update=job_update, current_user=current_user
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_description(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete job description."""
    await job_service.delete_job(db, job_id=job_id, current_user=current_user)
    return None
