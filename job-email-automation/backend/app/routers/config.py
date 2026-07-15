from fastapi import APIRouter

from app.config import ensure_default_resume_in_store, settings
from app.models import CandidateProfile, EmailTemplate, SenderProfile, SmtpConfig

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
async def get_app_config():
    """Return all settings from backend/.env — loaded automatically on app start."""
    resume_filename, resume_display = ensure_default_resume_in_store()

    smtp_configured = bool(settings.smtp_user and settings.smtp_password)
    sender_configured = bool(settings.sender_email)
    resume_configured = resume_filename is not None

    return {
        "source": "env",
        "sender": SenderProfile(
            name=settings.sender_name,
            email=settings.sender_email or "not-configured@local.dev",
            phone=settings.sender_phone,
        ).model_dump(),
        "smtp": SmtpConfig(
            host=settings.smtp_host,
            port=settings.smtp_port,
            user=settings.smtp_user,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
        ).model_dump(),
        "candidate": CandidateProfile(
            current_role=settings.candidate_current_role,
            years_experience=settings.candidate_years_experience,
            key_skills=settings.candidate_key_skills,
            experience_summary=settings.candidate_experience_summary,
        ).model_dump(),
        "template": EmailTemplate(
            subject_template=settings.email_subject_template,
            body_template=settings.email_body_template,
        ).model_dump(),
        "resume_filename": resume_filename,
        "resume_display_name": resume_display,
        "configured": {
            "smtp": smtp_configured,
            "sender": sender_configured,
            "resume": resume_configured,
            "serpapi": bool(settings.serpapi_api_key),
            "all_ready": smtp_configured and sender_configured and resume_configured,
        },
        "bookmarklet_url": "http://localhost:8000/api/find-jobs/bookmarklet",
    }
