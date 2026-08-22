import logging
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
from app.services.parser.anonymizer import anonymize_resume_text
from app.services.parser.llm_parser import parse_resume_with_llm
from app.services.parser.text_extractor import extract_text_from_file

logger = logging.getLogger(__name__)


class ResumeService:
    @staticmethod
    async def get_or_create_candidate(
        db: AsyncSession, *, candidate_in: CandidateCreate
    ) -> Candidate:
        """Find candidate by email or create a new candidate record."""
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
        """Register the uploaded resume in the database with PENDING status."""
        resume_in = ResumeCreate(
            candidate_id=candidate.id,
            file_name=file_name,
            file_path=file_path,
            file_type=file_type,
            file_size_bytes=file_size,
        )
        return await resume_repository.create(db, obj_in=resume_in)

    @staticmethod
    async def parse_and_process_resume(
        db: AsyncSession, *, resume_id: int
    ) -> Resume:
        """
        Execute full end-to-end parsing pipeline:
        1. Extract raw text from PDF / DOCX / TXT.
        2. Pre-process and anonymize PII (Name, Email, Phone, URLs) for bias-free screening.
        3. Send anonymized text to Cloud LLM (Gemini/OpenAI) for structured schema extraction.
        4. Save extracted structured skills, experiences, and education to database.
        """
        resume = await resume_repository.get_with_candidate(db, id=resume_id)
        if not resume:
            raise EntityNotFoundException("Resume", resume_id)

        # Mark as processing
        resume.parsing_status = ParsingStatus.PROCESSING
        resume.error_message = None
        await db.commit()
        await db.refresh(resume)

        try:
            # 1. Raw Text Extraction
            logger.info(f"Extracting text from resume {resume_id} ({resume.file_path})...")
            raw_text = extract_text_from_file(resume.file_path, resume.file_type)
            resume.raw_text = raw_text

            # 2. PII Anonymization & Redaction
            candidate = resume.candidate
            candidate_name = candidate.full_name if candidate else None
            candidate_email = candidate.email if candidate else None
            candidate_phone = candidate.phone if candidate else None
            candidate_urls = [
                u for u in [candidate.linkedin_url, candidate.github_url, candidate.portfolio_url]
                if candidate and u
            ]

            anonymized_text, redaction_metrics = anonymize_resume_text(
                raw_text=raw_text,
                candidate_name=candidate_name,
                candidate_email=candidate_email,
                candidate_phone=candidate_phone,
                candidate_urls=candidate_urls,
            )

            # 3. LLM Parsing
            logger.info(f"Calling LLM parser for resume {resume_id}...")
            parsed_data: ResumeParsedData = await parse_resume_with_llm(anonymized_text)

            # 4. Update Resume Record
            resume.summary = parsed_data.summary
            resume.skills = parsed_data.skills
            resume.work_experiences = [
                exp.model_dump() for exp in parsed_data.work_experiences
            ]
            resume.education = [
                edu.model_dump() for edu in parsed_data.education
            ]
            resume.certifications = [
                cert.model_dump() for cert in parsed_data.certifications
            ]
            resume.languages = parsed_data.languages
            
            # Combine metadata
            merged_metadata = dict(parsed_data.parsed_metadata or {})
            merged_metadata["redaction_metrics"] = redaction_metrics
            merged_metadata["char_count"] = len(raw_text)
            resume.parsed_metadata = merged_metadata

            resume.parsing_status = ParsingStatus.COMPLETED
            resume.error_message = None

            # Update candidate experience years if available
            if candidate and parsed_data.total_experience_years:
                candidate.total_experience_years = parsed_data.total_experience_years

            await db.commit()
            await db.refresh(resume)
            logger.info(f"Successfully parsed resume {resume_id}.")
            return resume

        except Exception as e:
            logger.error(f"Error while parsing resume {resume_id}: {e}", exc_info=True)
            resume.parsing_status = ParsingStatus.FAILED
            resume.error_message = str(e)
            await db.commit()
            await db.refresh(resume)
            raise BadRequestException(f"Resume parsing failed: {str(e)}")

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
