from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import EntityNotFoundException, ForbiddenException
from app.models.job import JobDescription
from app.models.user import User, UserRole
from app.repositories.job_repository import job_repository
from app.schemas.job import JobDescriptionCreate, JobDescriptionUpdate


class JobService:
    @staticmethod
    async def create_job(
        db: AsyncSession, *, job_in: JobDescriptionCreate, current_user: User
    ) -> JobDescription:
        job_data = job_in.model_dump()
        job_data["user_id"] = current_user.id
        return await job_repository.create(db, obj_in=job_data)

    @staticmethod
    async def get_job_by_id(db: AsyncSession, *, job_id: int) -> JobDescription:
        job = await job_repository.get(db, id=job_id)
        if not job:
            raise EntityNotFoundException("JobDescription", job_id)
        return job

    @staticmethod
    async def list_jobs(
        db: AsyncSession, *, skip: int = 0, limit: int = 100, active_only: bool = True
    ) -> List[JobDescription]:
        if active_only:
            return await job_repository.get_active_jobs(db, skip=skip, limit=limit)
        return await job_repository.get_multi(db, skip=skip, limit=limit)

    @staticmethod
    async def update_job(
        db: AsyncSession,
        *,
        job_id: int,
        job_update: JobDescriptionUpdate,
        current_user: User,
    ) -> JobDescription:
        job = await JobService.get_job_by_id(db, job_id=job_id)
        if job.user_id != current_user.id and current_user.role != UserRole.ADMIN:
            raise ForbiddenException("You do not have permission to modify this job")
        return await job_repository.update(db, db_obj=job, obj_in=job_update)

    @staticmethod
    async def delete_job(
        db: AsyncSession, *, job_id: int, current_user: User
    ) -> JobDescription:
        job = await JobService.get_job_by_id(db, job_id=job_id)
        if job.user_id != current_user.id and current_user.role != UserRole.ADMIN:
            raise ForbiddenException("You do not have permission to delete this job")
        return await job_repository.remove(db, id=job_id)


job_service = JobService()
