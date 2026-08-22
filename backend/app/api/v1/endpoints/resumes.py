import logging
import os
import uuid
from typing import List, Optional
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.core.exceptions import BadRequestException
from app.models.user import User
from app.schemas.candidate import CandidateCreate
from app.schemas.resume import ResumeResponse
from app.services.resume_service import resume_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resumes", tags=["Resumes"])


async def _run_background_parse(resume_id: int):
    """Background task worker for asynchronous resume parsing."""
    async with AsyncSessionLocal() as session:
        try:
            await resume_service.parse_and_process_resume(session, resume_id=resume_id)
        except Exception as e:
            logger.error(f"Background parsing task failed for resume {resume_id}: {e}")


@router.post(
    "/upload",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and parse candidate resume (PDF or Text)",
)
async def upload_resume(
    file: UploadFile = File(..., description="Resume document (PDF, TXT, or DOCX)"),
    full_name: str = Form(..., description="Candidate full name"),
    email: Optional[str] = Form(None, description="Candidate email address"),
    phone: Optional[str] = Form(None, description="Candidate contact phone number"),
    linkedin_url: Optional[str] = Form(None, description="Candidate LinkedIn profile URL"),
    github_url: Optional[str] = Form(None, description="Candidate GitHub profile URL"),
    portfolio_url: Optional[str] = Form(None, description="Candidate Portfolio URL"),
    parse_immediately: bool = Query(
        True,
        description="Whether to parse synchronously before returning or trigger in background",
    ),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a resume file and process candidate screening data:
    1. Validates file extension and size.
    2. Saves file safely to persistent storage.
    3. Creates or links Candidate record.
    4. Automatically extracts raw text, redacts PII, and parses structured schema using Cloud LLM.
    """
    # 1. Validate extension
    file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise BadRequestException(
            f"Unsupported file format '.{file_ext}'. Allowed formats: {settings.ALLOWED_EXTENSIONS}"
        )

    # 2. Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # 3. Generate unique filename & persist
    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    file_size = 0
    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            file_size = len(content)
            if file_size == 0:
                raise BadRequestException("The uploaded file is empty (0 bytes).")
            buffer.write(content)
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise BadRequestException(f"Failed to save uploaded file: {str(e)}")

    # 4. Check file size limit
    if file_size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise BadRequestException(
            f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB"
        )

    # 5. Get or create Candidate
    candidate = await resume_service.get_or_create_candidate(
        db,
        candidate_in=CandidateCreate(
            full_name=full_name,
            email=email,
            phone=phone,
            linkedin_url=linkedin_url,
            github_url=github_url,
            portfolio_url=portfolio_url,
        ),
    )

    # 6. Register Resume in Database (PENDING)
    resume = await resume_service.register_resume(
        db,
        candidate=candidate,
        file_name=file.filename,
        file_path=file_path,
        file_type=file_ext,
        file_size=file_size,
    )

    # 7. Parsing Execution
    if parse_immediately:
        resume = await resume_service.parse_and_process_resume(db, resume_id=resume.id)
    else:
        background_tasks.add_task(_run_background_parse, resume_id=resume.id)

    return await resume_service.get_resume_by_id(db, resume_id=resume.id)


@router.post(
    "/{resume_id}/reparse",
    response_model=ResumeResponse,
    summary="Re-trigger parsing pipeline for an existing resume",
)
async def reparse_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-run text extraction, anonymization, and LLM schema parsing on a resume."""
    return await resume_service.parse_and_process_resume(db, resume_id=resume_id)


@router.get("/", response_model=List[ResumeResponse], summary="List uploaded resumes")
async def list_resumes(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List uploaded resumes with candidate details and parsing status."""
    return await resume_service.list_resumes(db, skip=skip, limit=limit)


@router.get(
    "/{resume_id}",
    response_model=ResumeResponse,
    summary="Get detailed parsed resume by ID",
)
async def get_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get single resume details including raw text and structured parsed data."""
    return await resume_service.get_resume_by_id(db, resume_id=resume_id)
