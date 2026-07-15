import shutil
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
RESUME_DIR = BASE_DIR / "resumes"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_vision_model: str = "llama3.2-vision"
    ollama_text_model: str = "llama3.2"
    ollama_timeout: float = 180.0

    # Sender profile
    sender_name: str = "Your Name"
    sender_email: str = ""
    sender_phone: str = ""

    # Candidate profile (for AI email generation)
    candidate_current_role: str = ""
    candidate_years_experience: str = "3+ years"
    candidate_key_skills: str = "Java, Spring Boot, REST APIs, SQL, and frontend frameworks"
    candidate_experience_summary: str = (
        "I have 3+ years of hands-on experience in Java Full Stack Application Development, "
        "working with technologies such as Java, Spring Boot, REST APIs, SQL, and frontend frameworks."
    )

    # SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    # Resume — put your PDF path here (absolute or relative to backend folder)
    default_resume_path: str = ""

    # Email template (static fallback)
    email_subject_template: str = "Application for {role} at {company}"
    email_body_template: str = """Hi {recruiter_name},

I came across your LinkedIn post regarding the opening for the {role} role at {company} and found the opportunity closely aligned with my skills and experience.

{experience_summary}

Please find my resume attached for your reference. I would appreciate the opportunity to discuss how my experience can contribute to your team.

Looking forward to hearing from you.

Thanks & Regards,
{sender_name}"""

    max_upload_size_mb: int = 10

    # Optional SerpAPI key for more stable Google results (falls back to DuckDuckGo)
    # Get a key at https://serpapi.com — leave empty to use free DuckDuckGo search
    serpapi_api_key: str = ""

    # Allow bookmarklet calls from LinkedIn pages
    allow_linkedin_cors: bool = True


settings = Settings()

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESUME_DIR.mkdir(parents=True, exist_ok=True)


def resolve_resume_path(resume_filename: str | None = None) -> Path | None:
    """Find resume file: uploaded name first, then .env path, then any file in resumes/."""
    if resume_filename:
        uploaded = RESUME_DIR / resume_filename
        if uploaded.exists() and uploaded.is_file():
            return uploaded

    if settings.default_resume_path:
        path = Path(settings.default_resume_path)
        if not path.is_absolute():
            path = BASE_DIR / path
        if path.exists() and path.is_file():
            return path

    # Fallback: default names
    for name in ("default_resume.pdf", "resume.pdf", "default_resume.docx", "resume.docx"):
        p = RESUME_DIR / name
        if p.exists() and p.is_file():
            return p

    # Last resort: newest uploaded resume in resumes/ folder
    candidates = [
        p for p in RESUME_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in {".pdf", ".doc", ".docx"}
        and p.name.lower() != "readme.txt"
    ]
    if candidates:
        return max(candidates, key=lambda p: p.stat().st_mtime)

    return None


def ensure_default_resume_in_store() -> tuple[str | None, str | None]:
    """
    Copy .env resume into resumes/ folder for consistent serving.
    Returns (stored_filename, display_name).
    Falls back to newest uploaded resume if .env path is missing.
    """
    source = resolve_resume_path()
    if not source:
        return None, None

    if source.parent == RESUME_DIR:
        return source.name, source.name

    dest = RESUME_DIR / f"default_resume{source.suffix.lower()}"
    try:
        if not dest.exists() or source.stat().st_mtime > dest.stat().st_mtime:
            shutil.copy2(source, dest)
    except OSError:
        return source.name, source.name

    return dest.name, source.name
