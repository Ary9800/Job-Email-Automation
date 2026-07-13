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
    source_type: str = "screenshot"  # screenshot | linkedin_post
    source_url: Optional[str] = None
    extracted: Optional[ExtractedJobData] = None
    email: Optional[GeneratedEmail] = None
    email_ai: Optional[GeneratedEmail] = None
    email_static: Optional[GeneratedEmail] = None
    error: Optional[str] = None


class LinkedInPostResult(BaseModel):
    id: str
    url: str
    title: str
    snippet: str = ""
    role: Optional[str] = None
    company: Optional[str] = None
    recruiter_email: Optional[str] = None
    recruiter_name: Optional[str] = None
    experience_required: Optional[str] = None
    score: float = 0.0
    has_email: bool = False
    is_hr_post: bool = False


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


class FindJobsSearchResponse(BaseModel):
    posts: list[LinkedInPostResult]
    count: int
    roles_searched: list[str]


class FindJobsImportRequest(BaseModel):
    posts: list[LinkedInPostResult]


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


class BatchSendRequest(BaseModel):
    job_ids: list[str]
    sender: SenderProfile
    smtp: SmtpConfig
    resume_filename: Optional[str] = None
