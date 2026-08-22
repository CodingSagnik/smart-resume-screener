import os
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import BadRequestException, EntityNotFoundException
from app.models.candidate import Candidate
from app.models.resume import ParsingStatus, Resume
from app.models.screening_result import ScreeningResult, ScreeningStatus
from app.repositories.candidate_repository import candidate_repository
from app.repositories.job_repository import job_repository
from app.repositories.resume_repository import resume_repository
from app.repositories.screening_repository import screening_repository
from app.schemas.candidate import CandidateCreate
from app.schemas.resume import ResumeCreate, ResumeParsedData, ResumeUpdate
from app.schemas.screening_result import ScreeningResultCreate


class ResumeService:
    @staticmethod
    async def get_or_create_candidate(
        db: AsyncSession, *, candidate_in: CandidateCreate
    ) -> Candidate:
        if candidate_in.email:
            candidate = await candidate_repository.get_by_email(
                db, email=candidate_in.email
            )
            if candidate:
                return candidate
        return await candidate_repository.create(db, obj_in=candidate_in)

    @staticmethod
    async def register_resume(
        db: AsyncSession,
        *,
        candidate: Candidate,
        file_name: str,
        file_path: str,
        file_type: str,
        file_size: int,
    ) -> Resume:
        resume_in = ResumeCreate(
            candidate_id=candidate.id,
            file_name=file_name,
            file_path=file_path,
            file_type=file_type,
            file_size_bytes=file_size,
        )
        return await resume_repository.create(db, obj_in=resume_in)

    @staticmethod
    async def get_resume_by_id(db: AsyncSession, *, resume_id: int) -> Resume:
        resume = await resume_repository.get_with_candidate(db, id=resume_id)
        if not resume:
            raise EntityNotFoundException("Resume", resume_id)
        return resume

    @staticmethod
    async def list_resumes(
        db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[Resume]:
        return await resume_repository.get_multi(db, skip=skip, limit=limit)

    @staticmethod
    async def apply_to_job(
        db: AsyncSession, *, job_id: int, resume_id: int
    ) -> ScreeningResult:
        job = await job_repository.get(db, id=job_id)
        if not job:
            raise EntityNotFoundException("JobDescription", job_id)

        resume = await resume_repository.get(db, id=resume_id)
        if not resume:
            raise EntityNotFoundException("Resume", resume_id)

        existing = await screening_repository.get_by_job_and_resume(
            db, job_id=job_id, resume_id=resume_id
        )
        if existing:
            return existing

        screening_in = ScreeningResultCreate(
            job_id=job_id,
            resume_id=resume_id,
            status=ScreeningStatus.APPLIED,
        )
        return await screening_repository.create(db, obj_in=screening_in)

    @staticmethod
    async def get_job_screenings(
        db: AsyncSession,
        *,
        job_id: int,
        status: Optional[ScreeningStatus] = None,
        min_score: Optional[float] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ScreeningResult]:
        return await screening_repository.get_by_job(
            db,
            job_id=job_id,
            status=status,
            min_score=min_score,
            skip=skip,
            limit=limit,
        )


resume_service = ResumeService()
