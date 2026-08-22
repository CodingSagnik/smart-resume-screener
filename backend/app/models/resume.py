import enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from sqlalchemy import BigInteger, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.screening_result import ScreeningResult


class ParsingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Resume(Base, TimestampMixin):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # File storage metadata
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # pdf, docx, etc.
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)

    # Parsing status & raw output
    parsing_status: Mapped[ParsingStatus] = mapped_column(
        Enum(ParsingStatus), default=ParsingStatus.PENDING, nullable=False
    )
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Parsed structured sections (JSON/JSONB format for maximum flexibility)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    skills: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    work_experiences: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    education: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    certifications: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    languages: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    parsed_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict, nullable=True)

    # Relationships
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="resumes")
    screening_results: Mapped[List["ScreeningResult"]] = relationship(
        "ScreeningResult", back_populates="resume", cascade="all, delete-orphan"
    )
