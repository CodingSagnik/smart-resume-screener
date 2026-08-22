import os
import shutil
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import BadRequestException
from app.models.user import User
from app.schemas.candidate import CandidateCreate
from app.schemas.resume import ResumeResponse
from app.services.resume_service import resume_service

router = APIRouter(prefix="/resumes", tags=["Resumes"])


@router.post("/upload", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),
    full_name: str = Form(...),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    linkedin_url: Optional[str] = Form(None),
    github_url: Optional[str] = Form(None),
    portfolio_url: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a resume file and register the candidate record.
    The file is saved to the upload directory and a background parsing task can be triggered.
    """
    # Validate extension
    file_ext = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise BadRequestException(
            f"Unsupported file format '.{file_ext}'. Allowed formats: {settings.ALLOWED_EXTENSIONS}"
        )

    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Generate unique filename
    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    # Save file to disk
    file_size = 0
    with open(file_path, "wb") as buffer:
        content = await file.read()
        file_size = len(content)
        buffer.write(content)

    # Check file size limit (MB)
    if file_size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise BadRequestException(
            f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB"
        )

    # Get or create candidate
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

    # Register resume in database
    resume = await resume_service.register_resume(
        db,
        candidate=candidate,
        file_name=file.filename,
        file_path=file_path,
        file_type=file_ext,
        file_size=file_size,
    )

    # Return registered resume (parsing pipeline can be invoked asynchronously)
    return await resume_service.get_resume_by_id(db, resume_id=resume.id)


@router.get("/", response_model=List[ResumeResponse])
async def list_resumes(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List uploaded resumes."""
    return await resume_service.list_resumes(db, skip=skip, limit=limit)


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get single resume details including parsed sections."""
    return await resume_service.get_resume_by_id(db, resume_id=resume_id)
