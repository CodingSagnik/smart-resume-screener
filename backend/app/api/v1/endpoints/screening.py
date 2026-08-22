import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Body, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_optional_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import BadRequestException, EntityNotFoundException
from app.models.job import JobDescription
from app.models.screening_result import ScreeningStatus
from app.models.user import User
from app.repositories.job_repository import job_repository
from app.repositories.screening_repository import screening_repository
from app.schemas.candidate import CandidateCreate
from app.schemas.job import JobDescriptionCreate
from app.schemas.screening_result import (
    BatchScreeningRequest,
    ScreeningResultResponse,
    ScreeningResultUpdate,
)
from app.services.job_service import job_service
from app.services.resume_service import resume_service
from app.services.screening_service import screening_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/screening", tags=["Screening & Semantic Matching"])


@router.post(
    "/quick-screen",
    response_model=ScreeningResultResponse,
    status_code=status.HTTP_200_OK,
    summary="1-Click Quick Screen: upload a resume and paste job description to get instant AI evaluation",
)
async def quick_screen(
    file: UploadFile = File(..., description="Resume document (PDF, TXT, or DOCX)"),
    job_description: str = Form(..., description="Raw text of the Job Description"),
    job_title: Optional[str] = Form("Target Role", description="Job Title"),
    full_name: Optional[str] = Form("Applicant", description="Candidate Name"),
    email: Optional[str] = Form(None, description="Candidate Email"),
    phone: Optional[str] = Form(None, description="Candidate Phone"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_current_user),
):
    """
    1-Click Quick Screen Endpoint:
    Accepts job description text and an uploaded resume file simultaneously,
    processes text extraction, PII anonymization, and executes Gemini AI screening.
    """
    if not job_description.strip():
        raise BadRequestException("Job description cannot be empty.")

    # 1. Validate file extension
    file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise BadRequestException(
            f"Unsupported file format '.{file_ext}'. Allowed formats: {settings.ALLOWED_EXTENSIONS}"
        )

    # 2. Save uploaded file to disk
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    with open(file_path, "wb") as buffer:
        content = await file.read()
        if len(content) == 0:
            raise BadRequestException("Uploaded file is empty (0 bytes).")
        buffer.write(content)

    # 3. Create or link Job Description
    job = await job_service.create_job(
        db,
        job_in=JobDescriptionCreate(
            title=job_title.strip() if job_title else "Target Role",
            description_raw=job_description.strip(),
        ),
        current_user=current_user,
    )

    # 4. Create or link Candidate & Register Resume
    candidate = await resume_service.get_or_create_candidate(
        db,
        candidate_in=CandidateCreate(
            full_name=full_name.strip() if full_name else "Applicant",
            email=email,
            phone=phone,
        ),
    )
    resume = await resume_service.register_resume(
        db,
        candidate=candidate,
        file_name=file.filename,
        file_path=file_path,
        file_type=file_ext,
        file_size=len(content),
    )

    # 5. Execute AI screening
    return await screening_service.screen_candidate_for_job(
        db, job_id=job.id, resume_id=resume.id
    )


@router.post(
    "/jobs/{job_id}/screen/{resume_id}",
    response_model=ScreeningResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Screen and rate a resume against a job description using Gemini AI",
)
async def screen_candidate(
    job_id: int,
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Core AI Screening Endpoint:
    1. Loads the Job Description and Parsed Resume.
    2. Sends the anonymized resume and job details to Google Gemini (gemini-1.5-flash).
    3. Enforces structured JSON evaluation:
       - skills_match_score (1-10)
       - experience_match_score (1-10)
       - overall_score (1-10)
       - matched_skills & missing_skills
       - justification
    4. Persists the score and detailed feedback in the database.
    5. Returns the complete screening result.
    """
    result = await screening_service.screen_candidate_for_job(
        db, job_id=job_id, resume_id=resume_id
    )
    return result


@router.post(
    "/jobs/{job_id}/batch-screen",
    response_model=List[ScreeningResultResponse],
    summary="Batch screen multiple resumes against a job description",
)
async def batch_screen_candidates(
    job_id: int,
    request: BatchScreeningRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run AI screening evaluation for a list of candidate resumes against a job description."""
    return await screening_service.batch_screen_candidates(
        db, job_id=job_id, resume_ids=request.resume_ids
    )


@router.get(
    "/jobs/{job_id}/candidates",
    response_model=List[ScreeningResultResponse],
    summary="Get ranked candidate screening results for a job",
)
async def list_job_candidates(
    job_id: int,
    status_filter: Optional[ScreeningStatus] = Query(None, alias="status"),
    min_score: Optional[float] = Query(
        None, ge=0.0, le=100.0, description="Filter candidates by minimum match score (0-100)"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve ranked candidate screening results for a specific job posting.
    Results are pre-sorted with the highest match score first.
    """
    return await screening_repository.get_by_job(
        db,
        job_id=job_id,
        status=status_filter,
        min_score=min_score,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/jobs/{job_id}/candidates/{resume_id}",
    response_model=ScreeningResultResponse,
    summary="Get specific screening result for a candidate and job",
)
async def get_candidate_screening(
    job_id: int,
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve detailed match scores, skills analysis, and justification for a specific candidate."""
    result = await screening_repository.get_by_job_and_resume(
        db, job_id=job_id, resume_id=resume_id
    )
    if not result:
        raise EntityNotFoundException("ScreeningResult", f"job:{job_id}, resume:{resume_id}")
    return result


@router.patch(
    "/jobs/{job_id}/candidates/{resume_id}/status",
    response_model=ScreeningResultResponse,
    summary="Update candidate application pipeline status (e.g. shortlisted, interview, rejected)",
)
async def update_candidate_status(
    job_id: int,
    resume_id: int,
    new_status: ScreeningStatus = Body(..., embed=True),
    notes: Optional[str] = Body(None, embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update applicant pipeline status and recruiter notes."""
    result = await screening_repository.get_by_job_and_resume(
        db, job_id=job_id, resume_id=resume_id
    )
    if not result:
        raise EntityNotFoundException("ScreeningResult", f"job:{job_id}, resume:{resume_id}")

    update_in = ScreeningResultUpdate(status=new_status, notes=notes)
    return await screening_repository.update(db, db_obj=result, obj_in=update_in)
