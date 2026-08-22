from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.resume import ParsingStatus, Resume
from app.schemas.resume import ResumeCreate, ResumeUpdate
from app.repositories.base import BaseRepository


class ResumeRepository(BaseRepository[Resume, ResumeCreate, ResumeUpdate]):
    def __init__(self):
        super().__init__(Resume)

    async def get_with_candidate(self, db: AsyncSession, *, id: int) -> Optional[Resume]:
        result = await db.execute(
            select(Resume).options(selectinload(Resume.candidate)).where(Resume.id == id)
        )
        return result.scalars().first()

    async def get_by_candidate(
        self, db: AsyncSession, *, candidate_id: int
    ) -> List[Resume]:
        result = await db.execute(
            select(Resume)
            .where(Resume.candidate_id == candidate_id)
            .order_by(Resume.id.desc())
        )
        return list(result.scalars().all())

    async def get_by_status(
        self, db: AsyncSession, *, status: ParsingStatus, limit: int = 50
    ) -> List[Resume]:
        result = await db.execute(
            select(Resume)
            .where(Resume.parsing_status == status)
            .limit(limit)
            .order_by(Resume.created_at.asc())
        )
        return list(result.scalars().all())


resume_repository = ResumeRepository()
