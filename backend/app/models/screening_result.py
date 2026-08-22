import enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from sqlalchemy import Enum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.job import JobDescription
    from app.models.resume import Resume


class ScreeningStatus(str, enum.Enum):
    APPLIED = "applied"
    SCREENED = "screened"
    SHORTLISTED = "shortlisted"
    INTERVIEW = "interview"
    REJECTED = "rejected"


class ScreeningResult(Base, TimestampMixin):
    __tablename__ = "screening_results"
    __table_args__ = (
        UniqueConstraint("job_id", "resume_id", name="uq_job_resume_screening"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Scoring (0.0 to 100.0)
    match_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    skills_match_score: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    experience_match_score: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    education_match_score: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)

    # Granular analysis results
    analysis_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    matched_skills: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    missing_skills: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    detailed_feedback: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict, nullable=True)

    # Status in hiring workflow
    status: Mapped[ScreeningStatus] = mapped_column(
        Enum(ScreeningStatus), default=ScreeningStatus.SCREENED, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    job: Mapped["JobDescription"] = relationship("JobDescription", back_populates="screening_results")
    resume: Mapped["Resume"] = relationship("Resume", back_populates="screening_results")
