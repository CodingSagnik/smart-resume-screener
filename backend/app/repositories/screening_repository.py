from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.screening_result import ScreeningResult, ScreeningStatus
from app.schemas.screening_result import ScreeningResultCreate, ScreeningResultUpdate
from app.repositories.base import BaseRepository


class ScreeningRepository(
    BaseRepository[ScreeningResult, ScreeningResultCreate, ScreeningResultUpdate]
):
    def __init__(self):
        super().__init__(ScreeningResult)

    async def get_by_job_and_resume(
        self, db: AsyncSession, *, job_id: int, resume_id: int
    ) -> Optional[ScreeningResult]:
        result = await db.execute(
            select(ScreeningResult).where(
                ScreeningResult.job_id == job_id,
                ScreeningResult.resume_id == resume_id,
            )
        )
        return result.scalars().first()

    async def get_by_job(
        self,
        db: AsyncSession,
        *,
        job_id: int,
        status: Optional[ScreeningStatus] = None,
        min_score: Optional[float] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ScreeningResult]:
        query = (
            select(ScreeningResult)
            .options(
                selectinload(ScreeningResult.resume).selectinload(
                    ScreeningResult.resume.property.mapper.class_.candidate
                )
            )
            .where(ScreeningResult.job_id == job_id)
        )

        if status:
            query = query.where(ScreeningResult.status == status)
        if min_score is not None:
            query = query.where(ScreeningResult.match_score >= min_score)

        query = query.order_by(ScreeningResult.match_score.desc()).offset(skip).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())


screening_repository = ScreeningRepository()
