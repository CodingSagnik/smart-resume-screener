import json
import logging
import re
from typing import Any, Dict, Optional
from app.core.config import settings
from app.schemas.resume import ResumeParsedData

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert ATS (Applicant Tracking System) and AI Resume Parser.
Your task is to analyze the provided anonymized resume text and extract all key professional details.

You MUST respond strictly with a valid, parseable JSON object matching this exact JSON schema:

{
  "summary": "Professional summary or career objective statement",
  "skills": ["Skill1", "Skill2", "Skill3"],
  "work_experiences": [
    {
      "company": "Company Name or [REDACTED_COMPANY]",
      "position": "Job Title",
      "location": "City, Country or Remote (optional)",
      "start_date": "YYYY-MM or YYYY (optional)",
      "end_date": "YYYY-MM or Present (optional)",
      "is_current": true/false,
      "description": "Overview of duties and impact",
      "highlights": ["Key achievement 1", "Key achievement 2"],
      "technologies": ["Tech1", "Tech2"]
    }
  ],
  "education": [
    {
      "institution": "University / College name",
      "degree": "Degree (e.g., Bachelor of Science, Master of Science)",
      "field_of_study": "Major / Field (e.g., Computer Science)",
      "start_year": "YYYY (optional)",
      "end_year": "YYYY (optional)",
      "grade_gpa": "GPA or grade (optional)"
    }
  ],
  "certifications": [
    {
      "name": "Certification Title",
      "issuer": "Issuing Organization (e.g., AWS, Microsoft, Google)",
      "issue_date": "YYYY (optional)",
      "expiry_date": "YYYY (optional)",
      "credential_id": "Credential ID (optional)"
    }
  ],
  "languages": ["English", "Spanish"],
  "total_experience_years": 5.5,
  "parsed_metadata": {
    "confidence_score": 0.95,
    "has_clear_dates": true
  }
}

CRITICAL RULES:
1. Return ONLY the JSON object. Do not include introductory text, explanations, or markdown formatting outside the JSON.
2. The candidate's PII has been deliberately redacted (e.g. [REDACTED_NAME], [REDACTED_EMAIL], [REDACTED_PHONE]) for bias-free blind screening. Do not attempt to guess or hallucinate personal identifying information.
3. Normalize all skills into distinct, concise technical and domain skill tags (e.g., "Python", "FastAPI", "Kubernetes", "Machine Learning").
4. Calculate total_experience_years as accurately as possible based on the work experience timeline.
"""


def _clean_json_response(raw_response: str) -> str:
    """Strip markdown code block fences and isolate the valid JSON string."""
    cleaned = raw_response.strip()
    # Remove markdown codeblocks (```json ... ``` or ``` ...)
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


async def _parse_with_gemini(anonymized_text: str) -> Dict[str, Any]:
    """Call Google Gemini API using google-genai or google.generativeai SDK."""
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured in environment variables.")

    model_name = settings.GEMINI_MODEL or "gemini-1.5-flash"
    prompt = f"{SYSTEM_PROMPT}\n\nANONYMIZED RESUME TEXT:\n{anonymized_text}"

    # Try Google GenAI SDK (new standard)
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        return json.loads(_clean_json_response(response.text))
    except (ImportError, AttributeError):
        pass

    # Fallback to google.generativeai SDK
    try:
        import google.generativeai as gai

        gai.configure(api_key=api_key)
        model = gai.GenerativeModel(
            model_name=model_name,
            generation_config={"response_mime_type": "application/json", "temperature": 0.1},
        )
        response = model.generate_content(prompt)
        return json.loads(_clean_json_response(response.text))
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        raise ValueError(f"Gemini API parsing failed: {str(e)}")


async def _parse_with_openai(anonymized_text: str) -> Dict[str, Any]:
    """Call OpenAI API using the official async client with JSON mode."""
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured in environment variables.")

    model_name = settings.OPENAI_MODEL or "gpt-4o-mini"

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Please parse this anonymized resume:\n\n{anonymized_text}",
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        content = response.choices[0].message.content
        return json.loads(_clean_json_response(content))
    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}")
        raise ValueError(f"OpenAI API parsing failed: {str(e)}")


def _dev_mock_parser(anonymized_text: str) -> Dict[str, Any]:
    """
    Heuristic rule-based fallback parser for development / local testing
    when no LLM API key has been configured yet.
    """
    logger.warning(
        "No LLM API Key provided (GEMINI_API_KEY / OPENAI_API_KEY). "
        "Using development heuristic parser."
    )
    # Extract simple keywords
    common_skills = [
        "Python", "JavaScript", "TypeScript", "React", "Node.js", "FastAPI",
        "Django", "PostgreSQL", "MongoDB", "Docker", "Kubernetes", "AWS",
        "Git", "REST API", "GraphQL", "Java", "C++", "SQL", "HTML", "CSS", "CI/CD"
    ]
    detected_skills = [s for s in common_skills if re.search(r"\b" + re.escape(s) + r"\b", anonymized_text, re.IGNORECASE)]

    return {
        "summary": "Extracted candidate profile from uploaded resume.",
        "skills": detected_skills if detected_skills else ["General Technical Skills"],
        "work_experiences": [
            {
                "company": "Company (Redacted / Extracted)",
                "position": "Software Engineer",
                "location": "Remote",
                "start_date": "2021-01",
                "end_date": "Present",
                "is_current": True,
                "description": "Developed backend microservices and APIs.",
                "highlights": ["Built scalable services", "Optimized database performance"],
                "technologies": detected_skills[:4] if detected_skills else ["Python", "FastAPI"],
            }
        ],
        "education": [
            {
                "institution": "University (Extracted)",
                "degree": "Bachelor of Science",
                "field_of_study": "Computer Science or Related Field",
                "start_year": "2017",
                "end_year": "2021",
                "grade_gpa": None,
            }
        ],
        "certifications": [],
        "languages": ["English"],
        "total_experience_years": 3.0,
        "parsed_metadata": {
            "parser_mode": "dev_heuristic_fallback",
            "message": "Set GEMINI_API_KEY or OPENAI_API_KEY in .env for full AI parsing.",
        },
    }


async def parse_resume_with_llm(anonymized_text: str) -> ResumeParsedData:
    """
    Send anonymized resume text to configured Cloud LLM (Gemini / OpenAI)
    and parse into validated Pydantic ResumeParsedData schema.
    """
    if not anonymized_text or not anonymized_text.strip():
        raise ValueError("Resume text is empty. Cannot perform LLM extraction.")

    provider = (settings.LLM_PROVIDER or "gemini").lower()
    raw_data: Optional[Dict[str, Any]] = None

    # Check if provider keys are configured
    if provider == "gemini" and settings.GEMINI_API_KEY:
        raw_data = await _parse_with_gemini(anonymized_text)
    elif provider == "openai" and settings.OPENAI_API_KEY:
        raw_data = await _parse_with_openai(anonymized_text)
    elif settings.GEMINI_API_KEY:
        raw_data = await _parse_with_gemini(anonymized_text)
    elif settings.OPENAI_API_KEY:
        raw_data = await _parse_with_openai(anonymized_text)
    else:
        # Development fallback mode
        raw_data = _dev_mock_parser(anonymized_text)

    # Validate and structure data with Pydantic
    try:
        parsed_result = ResumeParsedData.model_validate(raw_data)
        return parsed_result
    except Exception as e:
        logger.error(f"Pydantic schema validation error on LLM response: {e}")
        raise ValueError(f"LLM output failed schema validation: {str(e)}")
