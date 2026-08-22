from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.candidate import Candidate
from app.schemas.candidate import CandidateCreate, CandidateUpdate
from app.repositories.base import BaseRepository


class CandidateRepository(BaseRepository[Candidate, CandidateCreate, CandidateUpdate]):
    def __init__(self):
        super().__init__(Candidate)

    async def get_by_email(self, db: AsyncSession, *, email: str) -> Optional[Candidate]:
        result = await db.execute(select(Candidate).where(Candidate.email == email))
        return result.scalars().first()


candidate_repository = CandidateRepository()
