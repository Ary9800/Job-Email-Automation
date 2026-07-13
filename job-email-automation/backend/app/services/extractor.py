import json
import re
from pathlib import Path

from app.models import ExtractedJobData
from app.services.job_normalizer import extract_experience, normalize_extracted
from app.services.llm import OllamaError, ollama
from app.services.ocr_fallback import extract_text_from_image

EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

BLOCKED_DOMAINS = {
    "linkedin.com", "example.com", "email.com",
}

EMAIL_CONTEXT_PATTERNS = [
    r"share\s+(?:your\s+)?(?:cv|resume)[s]?\s+at[:\s]*",
    r"interested\s+candidates\s+can\s+share[^@\n]{0,100}at[:\s]*",
    r"send\s+(?:your\s+)?resume[s]?\s+(?:to|at)[:\s]*",
    r"mail\s+(?:us\s+)?at[:\s]*",
    r"reach\s+(?:out\s+)?(?:us\s+)?at[:\s]*",
    r"contact[:\s]*",
    r"email[:\s]*",
]

STRUCTURED_PROMPT = """Analyze this LinkedIn job posting screenshot.

The email address found is: {email}

Extract details from the post. Return ONLY valid JSON:

{{
  "recruiter_email": "{email}",
  "recruiter_name": "first name of poster",
  "role": "EXACT job title from post e.g. Java Backend Engineer, Java Software Engineer, Java Developer — do NOT default to Java Developer",
  "company": "company name e.g. SPEC INDIA",
  "job_description": "brief summary",
  "location": "city",
  "source_platform": "LinkedIn",
  "skills_required": ["Java", "Spring Boot"],
  "experience_required": "e.g. 2+ years",
  "employment_type": null,
  "key_responsibilities": [],
  "content_summary": "what this post is about",
  "confidence": 0.9
}}

Return ONLY JSON."""


def _parse_json_response(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\n?", "", content)
        content = re.sub(r"\n?```$", "", content)
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        content = match.group(0)
    return json.loads(content)


def _is_valid_recruiter_email(email: str) -> bool:
    email = email.strip().lower().rstrip(".")
    if not EMAIL_PATTERN.fullmatch(email):
        return False
    domain = email.split("@")[1]
    if domain in BLOCKED_DOMAINS or domain.endswith("linkedin.com"):
        return False
    return True


def _clean_email(raw: str) -> str:
    raw = raw.strip()
    match = EMAIL_PATTERN.search(raw)
    if match:
        return match.group(0).rstrip(".")
    return raw.rstrip(".,;:")


def _extract_emails_from_text(text: str) -> list[str]:
    if not text:
        return []

    found: list[str] = []

    for pattern in EMAIL_CONTEXT_PATTERNS:
        for match in re.finditer(
            pattern + r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
            text,
            re.IGNORECASE | re.DOTALL,
        ):
            email = _clean_email(match.group(1))
            if _is_valid_recruiter_email(email) and email not in found:
                found.append(email)

    for match in EMAIL_PATTERN.finditer(text):
        email = _clean_email(match.group(0))
        if _is_valid_recruiter_email(email) and email not in found:
            found.append(email)

    return found


def _parse_job_details_from_text(text: str, email: str) -> dict:
    """Extract basic fields from OCR text using patterns."""
    data: dict = {
        "recruiter_email": email,
        "source_platform": "LinkedIn",
        "confidence": 0.7,
    }

    # Role — detect most specific title from OCR text
    from app.services.job_normalizer import detect_role_from_text

    role = detect_role_from_text(text)
    if role:
        data["role"] = role

    # Experience — separate field
    exp = extract_experience(text)
    if exp:
        data["experience_required"] = exp

    # Company
    company_patterns = [
        r"(NebuLogic\s*Technologies?)",
        r"([A-Z][a-zA-Z]*Logic)\s*Technologies",
        r"(?:Hiring at|We're Hiring at)\s+([A-Z][A-Z0-9\s&\-]+(?:INDIA|Technologies|Tech|Ltd|Inc|Pvt)[^\n,]*)",
        r"SPEC\s*INDIA",
        r"([A-Z][A-Za-z\s]+Technologies)",
        r"Apidel\s*Technologies",
    ]
    for pat in company_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            data["company"] = m.group(1).strip() if m.lastindex else m.group(0).strip()
            break

    # Location
    loc_m = re.search(r"(?:Location|📍)[:\s]*([A-Za-z\s]+)", text)
    if loc_m:
        data["location"] = loc_m.group(1).strip()

    # Recruiter name — line before "HR" or first capitalized name at top
    name_m = re.search(r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text, re.MULTILINE)
    if name_m:
        data["recruiter_name"] = name_m.group(1).strip()

    # Skills
    skills = re.findall(r"(?:Java|Spring Boot|Spring Framework|SQL|AWS|REST APIs?|Python)[^,\n]*", text, re.I)
    if skills:
        data["skills_required"] = list(dict.fromkeys(s.strip() for s in skills[:8]))

    return data


def _find_email(image_path: Path) -> tuple[str | None, str, str]:
    """
    Returns (email, ocr_text, method_used).
    Priority: 1) Local OCR (always works)  2) Ollama vision (if running)
    """
    ocr_text = extract_text_from_image(image_path)
    emails = _extract_emails_from_text(ocr_text)
    if emails:
        return emails[0], ocr_text, "ocr"

    # Ollama fallback if local OCR missed it
    if ollama.is_available():
        try:
            scan = ollama.chat_with_image(
                "List every email address visible in this image, one per line. Nothing else.",
                image_path,
            )
            ocr_text += "\n" + scan
            emails = _extract_emails_from_text(scan)
            if emails:
                return emails[0], ocr_text, "ollama"
        except OllamaError:
            pass

    return None, ocr_text, "none"


def _extract_structured(image_path: Path, email: str, ocr_text: str) -> dict:
    # Try Ollama for rich extraction
    if ollama.is_available():
        try:
            prompt = STRUCTURED_PROMPT.format(email=email)
            content = ollama.chat_with_image(prompt, image_path)
            data = _parse_json_response(content)
            data["recruiter_email"] = email
            return data
        except (OllamaError, json.JSONDecodeError, ValueError):
            pass

    # Fallback: parse from OCR text
    return _parse_job_details_from_text(ocr_text, email)


def extract_job_from_screenshot(image_path: Path) -> ExtractedJobData:
    email, ocr_text, method = _find_email(image_path)

    if not email:
        hint = "Could not find recruiter email in screenshot."
        if not ocr_text.strip():
            hint += " OCR could not read the image — try a clearer screenshot."
        elif ollama.is_available():
            hint += " Email not detected in text — enter it manually below."
        else:
            hint += " (Ollama offline — using local OCR only)"

        return ExtractedJobData(
            recruiter_email=None,
            confidence=0.0,
            raw_text=ocr_text[:800] if ocr_text else hint,
            source_platform="LinkedIn",
        )

    data = _extract_structured(image_path, email, ocr_text)
    data["recruiter_email"] = email
    data["raw_text"] = ocr_text[:800] if ocr_text else None
    data = normalize_extracted(data)
    return ExtractedJobData(**data)
