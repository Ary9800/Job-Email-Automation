from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    EXTRACTED = "extracted"
    EMAIL_GENERATED = "email_generated"
    SENT = "sent"
    FAILED = "failed"


class ExtractedJobData(BaseModel):
    recruiter_email: Optional[str] = None
    recruiter_name: Optional[str] = None
    role: Optional[str] = None
    company: Optional[str] = None
    job_description: Optional[str] = None
    location: Optional[str] = None
    source_platform: Optional[str] = None
    skills_required: Optional[list[str]] = None
    experience_required: Optional[str] = None
    employment_type: Optional[str] = None
    key_responsibilities: Optional[list[str]] = None
    content_summary: Optional[str] = None
    confidence: float = 0.0
    raw_text: Optional[str] = None


class CandidateProfile(BaseModel):
    current_role: str = ""
    years_experience: str = ""
    key_skills: str = ""
    experience_summary: str = ""


class GeneratedEmail(BaseModel):
    subject: str
    body: str
    to_email: str
    to_name: Optional[str] = None
    source: str = "ai"  # "ai" or "static"


class JobItem(BaseModel):
    id: str
    filename: str
    status: JobStatus = JobStatus.PENDING
    source_type: str = "screenshot"  # screenshot | linkedin_post | pasted
    source_url: Optional[str] = None
    extracted: Optional[ExtractedJobData] = None
    email: Optional[GeneratedEmail] = None
    email_ai: Optional[GeneratedEmail] = None
    email_static: Optional[GeneratedEmail] = None
    error: Optional[str] = None
    # Phase 3 tracker
    outcome: str = "none"  # none | waiting | replied | interview | rejected | hired | no_response
    sent_at: Optional[str] = None
    outcome_updated_at: Optional[str] = None
    notes: Optional[str] = None
    resume_filename: Optional[str] = None


class UpdateOutcomeRequest(BaseModel):
    outcome: str  # waiting | replied | interview | rejected | hired | no_response
    notes: Optional[str] = None


class SchedulerConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    hour: Optional[int] = None
    minute: Optional[int] = None
    time_period: Optional[str] = None
    experience_range: Optional[str] = None
    roles: Optional[list[str]] = None
    auto_import: Optional[bool] = None
    auto_generate: Optional[bool] = None


class ResumeProfile(BaseModel):
    id: str
    label: str
    filename: Optional[str] = None
    role_keywords: list[str] = Field(default_factory=list)


class ResumeProfilesUpdate(BaseModel):
    profiles: list[ResumeProfile]


class RoleTemplateItem(BaseModel):
    id: str
    label: str
    role_keywords: list[str] = Field(default_factory=list)
    subject_template: str = "Application for {role} at {company}"
    body_template: Optional[str] = None


class RoleTemplatesUpdate(BaseModel):
    templates: list[RoleTemplateItem]


class LinkedInPostResult(BaseModel):
    id: str
    url: str = ""
    title: str = ""
    snippet: str = ""
    role: Optional[str] = None
    company: Optional[str] = None
    recruiter_email: Optional[str] = None
    recruiter_name: Optional[str] = None
    experience_required: Optional[str] = None
    score: float = 0.0
    has_email: bool = False
    is_hr_post: bool = False


class SenderProfile(BaseModel):
    name: str = "Your Name"
    email: EmailStr
    phone: str = ""


class SmtpConfig(BaseModel):
    host: str = "smtp.gmail.com"
    port: int = 587
    user: str
    password: str
    use_tls: bool = True


class EmailTemplate(BaseModel):
    subject_template: str = "Application for {role} at {company}"
    body_template: str = """Hi {recruiter_name},

I came across your LinkedIn post regarding the opening for the {role} role at {company} and found the opportunity closely aligned with my skills and experience.

{experience_summary}

Please find my resume attached for your reference. I would appreciate the opportunity to discuss how my experience can contribute to your team.

Looking forward to hearing from you.

Thanks & Regards,
{sender_name}"""


class FindJobsSearchRequest(BaseModel):
    roles: list[str] = Field(default_factory=lambda: [
        "Java Backend Engineer",
        "Java Backend Developer",
        "Java Full Stack Developer",
        "Java Software Engineer",
        "Java Developer",
        "Software Engineer",
        "Backend Engineer",
    ])
    max_results: int = 30
    # day | week | month
    time_period: str = "week"
    # any | 2+ | 2-3 | 2-4 | 3+ | 3-5
    experience_range: str = "2-4"


class FindJobsSearchResponse(BaseModel):
    posts: list[LinkedInPostResult]
    count: int
    roles_searched: list[str]
    time_period: str = "week"
    experience_range: str = "2-4"
    search_provider: str = "ddgs"


class EnrichPostRequest(BaseModel):
    url: str
    # Optional existing snippet to merge with fetched page text
    snippet: str = ""


class EnrichPostResponse(BaseModel):
    url: str
    recruiter_email: Optional[str] = None
    emails: list[str] = Field(default_factory=list)
    text: str = ""
    login_wall: bool = False
    ok: bool = False
    error: Optional[str] = None
    post: Optional[LinkedInPostResult] = None


class BookmarkletCaptureRequest(BaseModel):
    """Sent from LinkedIn bookmarklet (selected text + page URL)."""
    text: str = ""
    url: Optional[str] = None
    auto_generate: bool = True
    sender: Optional[SenderProfile] = None
    template: Optional[EmailTemplate] = None
    candidate: Optional[CandidateProfile] = None


class FindJobsImportRequest(BaseModel):
    posts: list[LinkedInPostResult]
    auto_generate: bool = True
    sender: Optional[SenderProfile] = None
    template: Optional[EmailTemplate] = None
    candidate: Optional[CandidateProfile] = None


class PasteJobRequest(BaseModel):
    """Paste LinkedIn post URL and/or full post text when snippet has no email."""
    text: str = ""
    url: Optional[str] = None
    auto_generate: bool = True
    sender: Optional[SenderProfile] = None
    template: Optional[EmailTemplate] = None
    candidate: Optional[CandidateProfile] = None


class ProcessRequest(BaseModel):
    sender: SenderProfile
    smtp: SmtpConfig
    template: EmailTemplate = Field(default_factory=EmailTemplate)
    candidate: CandidateProfile = Field(default_factory=CandidateProfile)
    auto_send: bool = False
    resume_filename: Optional[str] = None


class SendEmailRequest(BaseModel):
    job_id: str
    sender: SenderProfile
    smtp: SmtpConfig
    resume_filename: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    to_email: Optional[str] = None


class GenerateEmailRequest(BaseModel):
    sender: SenderProfile
    template: EmailTemplate = Field(default_factory=EmailTemplate)
    candidate: CandidateProfile = Field(default_factory=CandidateProfile)


class FixEmailRequest(BaseModel):
    recruiter_email: str
    recruiter_name: Optional[str] = None
    role: Optional[str] = None
    company: Optional[str] = None


class SaveDraftRequest(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    to_email: Optional[str] = None
    to_name: Optional[str] = None
    source: Optional[str] = None  # ai | static


class BatchSendRequest(BaseModel):
    job_ids: list[str]
    sender: SenderProfile
    smtp: SmtpConfig
    resume_filename: Optional[str] = None
