from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.job import JobDescription
from app.schemas.job import JobDescriptionCreate, JobDescriptionUpdate
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository[JobDescription, JobDescriptionCreate, JobDescriptionUpdate]):
    def __init__(self):
        super().__init__(JobDescription)

    async def get_by_user(
        self, db: AsyncSession, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[JobDescription]:
        result = await db.execute(
            select(JobDescription)
            .where(JobDescription.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .order_by(JobDescription.id.desc())
        )
        return list(result.scalars().all())

    async def get_active_jobs(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[JobDescription]:
        result = await db.execute(
            select(JobDescription)
            .where(JobDescription.is_active == True)
            .offset(skip)
            .limit(limit)
            .order_by(JobDescription.id.desc())
        )
        return list(result.scalars().all())


job_repository = JobRepository()
