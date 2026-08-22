import json
import logging
import re
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.exceptions import BadRequestException, EntityNotFoundException
from app.models.job import JobDescription
from app.models.resume import ParsingStatus, Resume
from app.models.screening_result import ScreeningResult, ScreeningStatus
from app.repositories.job_repository import job_repository
from app.repositories.resume_repository import resume_repository
from app.repositories.screening_repository import screening_repository
from app.schemas.screening_result import (
    LLMScreeningEvaluation,
    ScreeningResultCreate,
    ScreeningResultUpdate,
)
from app.services.resume_service import resume_service

logger = logging.getLogger(__name__)

SCREENING_SYSTEM_PROMPT = """You are an expert AI Technical Recruiter and Talent Assessor.
Compare the following candidate resume with the provided job description and evaluate candidate fit objectively.

Rate candidate fit on a 1-10 scale with clear, analytical justification.

You MUST respond strictly with a valid, parseable JSON object matching this exact JSON schema:

{
  "skills_match_score": <integer from 1 to 10>,
  "experience_match_score": <integer from 1 to 10>,
  "overall_score": <integer from 1 to 10>,
  "matched_skills": ["Skill1", "Skill2"],
  "missing_skills": ["Skill3", "Skill4"],
  "justification": "A detailed paragraph explaining the rating, highlighting candidate strengths, experience relevance, and potential gaps relative to the job requirements."
}

SCORING GUIDELINES (1 to 10 Scale):
- 9-10 (Exceptional Match): Exceeds core requirements; strong relevant experience and all critical skills.
- 7-8 (Strong Match): Meets key requirements; strong skill overlap with minor easily-trained gaps.
- 5-6 (Moderate Match): Partial skill/experience alignment; meets some requirements but has noticeable gaps.
- 3-4 (Weak Match): Missing multiple critical skills or lacking required seniority/domain experience.
- 1-2 (Poor Match): Unrelated background or severe mismatch in technical stack and experience.

CRITICAL RULES:
1. Return ONLY the valid JSON object without surrounding markdown fences or conversational preambles.
2. Carefully inspect both required skills and nice-to-have skills against the candidate's skills and work history.
3. Provide an objective, bias-free justification paragraph explaining exactly why the candidate received the assigned scores.
"""


def _clean_json_text(raw_response: str) -> str:
    """Clean markdown codeblocks and isolate JSON text."""
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _dev_mock_screening(
    resume_skills: List[str],
    job_description_raw: str,
    required_skills: List[str],
) -> Dict[str, Any]:
    """
    Fallback heuristic scoring for local development when GEMINI_API_KEY is not set.
    """
    logger.warning("GEMINI_API_KEY not configured. Running fallback heuristic screening evaluation.")
    
    resume_skills_lower = {s.lower() for s in resume_skills}
    job_skills_lower = {s.lower() for s in required_skills}
    
    # If no required skills were tagged in job, extract common tech words
    if not job_skills_lower:
        words = re.findall(r"\b[a-zA-Z0-9#+.]{2,20}\b", job_description_raw.lower())
        job_skills_lower = {w for w in words if w in {"python", "fastapi", "django", "react", "postgresql", "docker", "aws", "sql", "git"}}
    
    matched = [s for s in resume_skills if s.lower() in job_skills_lower or any(s.lower() in w for w in job_skills_lower)]
    missing = [s for s in required_skills if s.lower() not in resume_skills_lower]
    
    total_target = max(len(job_skills_lower), 1)
    overlap_ratio = len(matched) / total_target
    
    score = min(max(int(overlap_ratio * 10), 5), 9) if matched else 4
    
    return {
        "skills_match_score": score,
        "experience_match_score": max(score - 1, 3),
        "overall_score": score,
        "matched_skills": matched if matched else resume_skills[:3],
        "missing_skills": missing if missing else ["Advanced Domain Specialization"],
        "justification": (
            f"Candidate demonstrates alignment in {', '.join(matched[:4]) if matched else 'foundational skills'}. "
            f"Overall profile shows good potential for the role with a skills match rating of {score}/10."
        ),
    }


async def compare_resume_and_job_with_gemini(
    parsed_resume_dict: Dict[str, Any],
    job_description_raw: str,
    job_title: str = "",
    required_skills: Optional[List[str]] = None,
    preferred_skills: Optional[List[str]] = None,
    experience_level: Optional[str] = None,
    min_years_experience: Optional[int] = None,
) -> LLMScreeningEvaluation:
    """
    Send parsed resume JSON and raw job description to Google Gemini (gemini-1.5-flash)
    using structured JSON mode.
    """
    api_key = settings.GEMINI_API_KEY
    model_name = settings.GEMINI_MODEL or "gemini-1.5-flash"
    req_skills = required_skills or []
    pref_skills = preferred_skills or []

    # Build evaluation prompt context
    job_context = f"""=== TARGET JOB DESCRIPTION ===
Title: {job_title}
Experience Level: {experience_level or 'Not specified'}
Minimum Years Experience Required: {min_years_experience or 0}
Required Skills: {', '.join(req_skills) if req_skills else 'See description'}
Preferred Skills: {', '.join(pref_skills) if pref_skills else 'None specified'}

Job Details:
{job_description_raw}
"""

    resume_context = f"""=== CANDIDATE RESUME (ANONYMIZED) ===
Summary:
{parsed_resume_dict.get('summary') or 'N/A'}

Extracted Skills:
{', '.join(parsed_resume_dict.get('skills', []))}

Work Experience History:
{json.dumps(parsed_resume_dict.get('work_experiences', []), indent=2)}

Education:
{json.dumps(parsed_resume_dict.get('education', []), indent=2)}

Certifications:
{json.dumps(parsed_resume_dict.get('certifications', []), indent=2)}
"""

    prompt = f"{SCREENING_SYSTEM_PROMPT}\n\n{job_context}\n\n{resume_context}"

    if not api_key:
        raw_output = _dev_mock_screening(
            resume_skills=parsed_resume_dict.get("skills", []),
            job_description_raw=job_description_raw,
            required_skills=req_skills,
        )
        return LLMScreeningEvaluation.model_validate(raw_output)

    # 1. Try modern google-genai SDK
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        clean_text = _clean_json_text(response.text)
        result_dict = json.loads(clean_text)
        return LLMScreeningEvaluation.model_validate(result_dict)
    except (ImportError, AttributeError):
        pass
    except Exception as e:
        logger.warning(f"google-genai SDK failed: {e}. Trying google.generativeai fallback...")

    # 2. Fallback to google.generativeai SDK
    try:
        import google.generativeai as gai

        gai.configure(api_key=api_key)
        model = gai.GenerativeModel(
            model_name=model_name,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.2,
            },
        )
        response = model.generate_content(prompt)
        clean_text = _clean_json_text(response.text)
        result_dict = json.loads(clean_text)
        return LLMScreeningEvaluation.model_validate(result_dict)
    except Exception as e:
        logger.error(f"Gemini API screening evaluation failed: {e}")
        raise ValueError(f"Gemini screening evaluation failed: {str(e)}")


class ScreeningService:
    @staticmethod
    async def screen_candidate_for_job(
        db: AsyncSession,
        *,
        job_id: int,
        resume_id: int,
    ) -> ScreeningResult:
        """
        Evaluate and match a candidate resume against a job description:
        1. Retrieves JobDescription and Resume from database.
        2. Ensures resume text and schema have been extracted/parsed.
        3. Calls Google Gemini (gemini-1.5-flash) with structured JSON enforcement.
        4. Saves and persists match scores, skill breakdown, and justification in screening_results.
        """
        # 1. Fetch Job
        job = await job_repository.get(db, id=job_id)
        if not job:
            raise EntityNotFoundException("JobDescription", job_id)

        # 2. Fetch Resume
        resume = await resume_repository.get_with_candidate(db, id=resume_id)
        if not resume:
            raise EntityNotFoundException("Resume", resume_id)

        # 3. Ensure Resume is parsed
        if resume.parsing_status != ParsingStatus.COMPLETED or not resume.skills:
            logger.info(f"Resume {resume_id} is not fully parsed yet. Triggering parsing pipeline...")
            resume = await resume_service.parse_and_process_resume(db, resume_id=resume.id)

        # 4. Prepare resume payload dictionary
        parsed_resume_dict = {
            "summary": resume.summary,
            "skills": resume.skills or [],
            "work_experiences": resume.work_experiences or [],
            "education": resume.education or [],
            "certifications": resume.certifications or [],
            "languages": resume.languages or [],
        }

        # 5. Call Gemini Matching Engine
        evaluation: LLMScreeningEvaluation = await compare_resume_and_job_with_gemini(
            parsed_resume_dict=parsed_resume_dict,
            job_description_raw=job.description_raw,
            job_title=job.title,
            required_skills=job.required_skills,
            preferred_skills=job.preferred_skills,
            experience_level=job.experience_level.value if hasattr(job.experience_level, "value") else str(job.experience_level),
            min_years_experience=job.min_years_experience,
        )

        # 6. Retrieve or Create ScreeningResult record
        existing = await screening_repository.get_by_job_and_resume(
            db, job_id=job_id, resume_id=resume_id
        )

        # Normalization: overall_score (1-10) -> match_score (10.0 to 100.0)
        overall_scaled = float(evaluation.overall_score * 10)
        
        # Decide workflow status based on score
        hiring_status = (
            ScreeningStatus.SHORTLISTED
            if evaluation.overall_score >= 7
            else ScreeningStatus.SCREENED
        )

        detailed_feedback = {
            "overall_score_1_to_10": evaluation.overall_score,
            "skills_match_score_1_to_10": evaluation.skills_match_score,
            "experience_match_score_1_to_10": evaluation.experience_match_score,
            "model_used": settings.GEMINI_MODEL or "gemini-1.5-flash",
            "justification": evaluation.justification,
        }

        if existing:
            # Update existing screening record
            update_data = ScreeningResultUpdate(
                match_score=overall_scaled,
                skills_match_score=float(evaluation.skills_match_score),
                experience_match_score=float(evaluation.experience_match_score),
                analysis_summary=evaluation.justification,
                matched_skills=evaluation.matched_skills,
                missing_skills=evaluation.missing_skills,
                detailed_feedback=detailed_feedback,
                status=hiring_status,
            )
            result = await screening_repository.update(
                db, db_obj=existing, obj_in=update_data
            )
        else:
            # Create new screening record
            create_data = ScreeningResultCreate(
                job_id=job_id,
                resume_id=resume_id,
                match_score=overall_scaled,
                skills_match_score=float(evaluation.skills_match_score),
                experience_match_score=float(evaluation.experience_match_score),
                analysis_summary=evaluation.justification,
                matched_skills=evaluation.matched_skills,
                missing_skills=evaluation.missing_skills,
                detailed_feedback=detailed_feedback,
                status=hiring_status,
            )
            result = await screening_repository.create(db, obj_in=create_data)

        # Return refreshed entity with associations loaded
        return await screening_repository.get(db, id=result.id)

    @staticmethod
    async def batch_screen_candidates(
        db: AsyncSession,
        *,
        job_id: int,
        resume_ids: List[int],
    ) -> List[ScreeningResult]:
        """Run screening evaluation for multiple resumes against a job description."""
        results = []
        for resume_id in resume_ids:
            try:
                res = await ScreeningService.screen_candidate_for_job(
                    db, job_id=job_id, resume_id=resume_id
                )
                results.append(res)
            except Exception as e:
                logger.error(f"Failed screening resume {resume_id} for job {job_id}: {e}")
        return results


screening_service = ScreeningService()
