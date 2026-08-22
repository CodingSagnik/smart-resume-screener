import re
import logging
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Optional spaCy NER loader
_nlp = None
_spacy_attempted = False


def _get_spacy_nlp():
    """Lazy load spaCy NLP model if installed."""
    global _nlp, _spacy_attempted
    if not _spacy_attempted:
        _spacy_attempted = True
        try:
            import spacy

            try:
                _nlp = spacy.load("en_core_web_sm")
                logger.info("Loaded spaCy en_core_web_sm model for NER redaction.")
            except Exception:
                logger.info(
                    "spaCy installed but 'en_core_web_sm' model not found. "
                    "Falling back to regex-based PII redaction."
                )
        except ImportError:
            logger.info("spaCy not installed. Using advanced regex-based PII redaction.")
    return _nlp


# Regex Patterns for PII
EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", re.IGNORECASE
)

# Matches international & regional phone formats: +1-202-555-0125, (555) 000-1234, +91 98765 43210, 555.123.4567, etc.
PHONE_REGEX = re.compile(
    r"(?:(?:\+?\d{1,3}[-.\s*]?)?(?:\(?\d{2,4}\)?[-.\s*]?)?\d{3,4}[-.\s*]?\d{3,4}(?:[-.\s*]?\d{1,5})?|\b\d{10}\b)",
    re.VERBOSE,
)

# Social & Portfolio URLs (LinkedIn, GitHub, Kaggle, Twitter, Medium, personal sites)
URL_REGEX = re.compile(
    r"(?:https?:\/\/)?(?:www\.)?(?:linkedin\.com\/(?:in|profile)\/[a-zA-Z0-9_-]+|github\.com\/[a-zA-Z0-9_-]+|twitter\.com\/[a-zA-Z0-9_-]+|x\.com\/[a-zA-Z0-9_-]+|[a-zA-Z0-9_-]+\.(?:me|io|dev|app|portfolio|tech|com))\b",
    re.IGNORECASE,
)

# General URL fallback
GENERAL_URL_REGEX = re.compile(
    r"\bhttps?:\/\/[^\s/$.?#].[^\s]*\b", re.IGNORECASE
)

# Postal codes / ZIP codes
ZIP_CODE_REGEX = re.compile(
    r"\b\d{5}(?:-\d{4})?\b|\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", re.IGNORECASE
)


def anonymize_resume_text(
    raw_text: str,
    candidate_name: Optional[str] = None,
    candidate_email: Optional[str] = None,
    candidate_phone: Optional[str] = None,
    candidate_urls: Optional[List[str]] = None,
) -> Tuple[str, Dict[str, int]]:
    """
    Sanitize and redact Personally Identifiable Information (PII) from resume text.
    Removes candidate names, contact details, emails, phone numbers, and profile URLs
    to enforce bias-free, blind screening.

    Returns:
        Tuple of (anonymized_text, redaction_metrics)
    """
    if not raw_text:
        return "", {"names": 0, "emails": 0, "phones": 0, "urls": 0}

    text = raw_text
    metrics = {
        "names_redacted": 0,
        "emails_redacted": 0,
        "phones_redacted": 0,
        "urls_redacted": 0,
    }

    # 1. Redact candidate's explicitly provided email if present
    if candidate_email and candidate_email.strip():
        email_pattern = re.compile(re.escape(candidate_email.strip()), re.IGNORECASE)
        text, count = email_pattern.subn("[REDACTED_EMAIL]", text)
        metrics["emails_redacted"] += count

    # 2. General Email Redaction via Regex
    emails_found = EMAIL_REGEX.findall(text)
    if emails_found:
        text, count = EMAIL_REGEX.subn("[REDACTED_EMAIL]", text)
        metrics["emails_redacted"] += count

    # 3. Redact candidate's explicit phone
    if candidate_phone and candidate_phone.strip():
        # Clean special chars from phone to create fuzzy digits pattern
        phone_digits = re.sub(r"\D", "", candidate_phone)
        if len(phone_digits) >= 7:
            phone_pattern = re.compile(
                r"\b" + r"[-.\s()]*".join(list(phone_digits)) + r"\b"
            )
            text, count = phone_pattern.subn("[REDACTED_PHONE]", text)
            metrics["phones_redacted"] += count

    # 4. General Phone Redaction via Regex (only replace matches that have >= 7 digits)
    def redact_phone_match(match):
        matched_str = match.group(0)
        digits = re.sub(r"\D", "", matched_str)
        if len(digits) >= 7 and not (len(digits) == 4 and 1900 <= int(digits) <= 2099):  # Avoid redacting years
            metrics["phones_redacted"] += 1
            return "[REDACTED_PHONE]"
        return matched_str

    text = PHONE_REGEX.sub(redact_phone_match, text)

    # 5. Redact Candidate's Explicit URLs
    if candidate_urls:
        for url in candidate_urls:
            if url and url.strip():
                url_clean = re.sub(r"^https?:\/\/(?:www\.)?", "", url.strip(), flags=re.IGNORECASE)
                if len(url_clean) > 3:
                    url_pattern = re.compile(re.escape(url_clean), re.IGNORECASE)
                    text, count = url_pattern.subn("[REDACTED_URL]", text)
                    metrics["urls_redacted"] += count

    # 6. General URL Redaction
    text, count = URL_REGEX.subn("[REDACTED_LINK]", text)
    metrics["urls_redacted"] += count
    text, count = GENERAL_URL_REGEX.subn("[REDACTED_URL]", text)
    metrics["urls_redacted"] += count

    # 7. Candidate Explicit Name Redaction
    if candidate_name and candidate_name.strip():
        name_parts = candidate_name.strip().split()
        # Redact full name first
        full_name_pattern = re.compile(
            r"\b" + re.escape(candidate_name.strip()) + r"\b", re.IGNORECASE
        )
        text, count = full_name_pattern.subn("[REDACTED_NAME]", text)
        metrics["names_redacted"] += count

        # Redact individual name parts if they are distinct (> 2 chars and not common english words)
        for part in name_parts:
            if len(part) > 2 and part.lower() not in {"and", "the", "for", "resume", "cv"}:
                part_pattern = re.compile(r"\b" + re.escape(part) + r"\b", re.IGNORECASE)
                text, count = part_pattern.subn("[REDACTED_NAME]", text)
                metrics["names_redacted"] += count

    # 8. spaCy NER Redaction (PERSON entities)
    nlp = _get_spacy_nlp()
    if nlp:
        try:
            # Process with spaCy (limit to first 3000 tokens where names / headers appear most)
            header_sample = text[:4000]
            doc = nlp(header_sample)
            person_names = {
                ent.text.strip()
                for ent in doc.ents
                if ent.label_ == "PERSON" and len(ent.text.strip()) > 2
            }

            # Filter out false positives from common resume section headers
            stopwords = {"Curriculum", "Vitae", "Resume", "Experience", "Education", "Skills", "Projects", "Summary", "Objective"}
            person_names = {name for name in person_names if not any(w.lower() in name.lower() for w in stopwords)}

            for p_name in sorted(person_names, key=len, reverse=True):
                p_pattern = re.compile(r"\b" + re.escape(p_name) + r"\b")
                text, count = p_pattern.subn("[REDACTED_NAME]", text)
                metrics["names_redacted"] += count
        except Exception as e:
            logger.warning(f"spaCy NER redaction encountered an error: {e}")
    else:
        # Heuristic fallback: The top 1-2 lines of a resume often contain the name in title/uppercase
        lines = text.splitlines()
        if lines:
            first_line = lines[0].strip()
            # If the first line is short (< 40 chars) and doesn't contain section keywords
            if (
                0 < len(first_line) < 40
                and not any(k in first_line.lower() for k in ["resume", "curriculum", "page", "summary", "profile", "objective", "experience"])
                and re.match(r"^[A-Z][a-zA-Z\s.-]+$", first_line)
            ):
                text = text.replace(first_line, "[REDACTED_NAME]", 1)
                metrics["names_redacted"] += 1

    return text, metrics
