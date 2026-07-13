import json
import re

from app.models import (
    CandidateProfile,
    EmailTemplate,
    ExtractedJobData,
    GeneratedEmail,
    SenderProfile,
)
from app.services.job_normalizer import clean_company, clean_role, resolve_role
from app.services.llm import OllamaError, ollama


def _format_subject(role: str, company: str) -> str:
    role = clean_role(role) or "the position"
    company = clean_company(company) or "your organization"
    return f"Application for {role} at {company}"


def _prepare_job_fields(job: ExtractedJobData) -> tuple[str, str]:
    role = resolve_role(job.role, job.raw_text) or "the open position"
    company = clean_company(job.company, job.recruiter_email, job.raw_text) or "your organization"
    return role, company


def _safe_format(template: str, values: dict) -> str:
    result = template
    for key, value in values.items():
        result = result.replace("{" + key + "}", str(value or ""))
    return result


def _recruiter_first_name(name: str | None) -> str:
    if not name:
        return "there"
    return name.strip().split()[0].rstrip("-")


def _normalize_email(job: ExtractedJobData) -> tuple[str, str | None]:
    to_email = job.recruiter_email or ""
    if to_email and not re.match(r"^[^@]+@[^@]+\.[^@]+$", to_email):
        to_email = ""
    return to_email, job.recruiter_name


def _job_context(job: ExtractedJobData) -> str:
    lines = [
        f"Role: {job.role or 'Not specified'}",
        f"Company: {job.company or 'Not specified'}",
        f"Location: {job.location or 'Not specified'}",
        f"Experience required: {job.experience_required or 'Not specified'}",
        f"Description: {job.job_description or 'Not specified'}",
    ]
    if job.skills_required:
        lines.append(f"Skills required: {', '.join(job.skills_required)}")
    if job.key_responsibilities:
        lines.append(f"Responsibilities: {'; '.join(job.key_responsibilities)}")
    if job.content_summary:
        lines.append(f"Post summary: {job.content_summary}")
    return "\n".join(lines)


def _candidate_context(candidate: CandidateProfile) -> str:
    parts = []
    if candidate.current_role:
        parts.append(f"Current role: {candidate.current_role}")
    if candidate.years_experience:
        parts.append(f"Experience: {candidate.years_experience}")
    if candidate.key_skills:
        parts.append(f"Skills: {candidate.key_skills}")
    if candidate.experience_summary:
        parts.append(f"Background: {candidate.experience_summary}")
    return "\n".join(parts) if parts else "Java Full Stack Developer with 3+ years experience."


def _experience_paragraph(candidate: CandidateProfile) -> str:
    if candidate.experience_summary:
        return candidate.experience_summary.strip()
    years = candidate.years_experience or "3+ years"
    skills = candidate.key_skills or "Java, Spring Boot, REST APIs, SQL"
    return (
        f"I have {years} of hands-on experience in Java Full Stack Application Development, "
        f"working with technologies such as {skills}."
    )


def generate_static_email(
    job: ExtractedJobData,
    sender: SenderProfile,
    template: EmailTemplate,
    candidate: CandidateProfile,
) -> GeneratedEmail:
    to_email, to_name = _normalize_email(job)
    display_name = _recruiter_first_name(job.recruiter_name)
    role, company = _prepare_job_fields(job)

    values = {
        "recruiter_name": display_name,
        "role": role,
        "company": company,
        "sender_name": sender.name,
        "sender_email": sender.email,
        "sender_phone": sender.phone,
        "experience_summary": _experience_paragraph(candidate),
    }

    return GeneratedEmail(
        subject=_format_subject(role, company),
        body=_safe_format(template.body_template, values).strip(),
        to_email=to_email,
        to_name=to_name,
        source="static",
    )


def generate_ai_email(
    job: ExtractedJobData,
    sender: SenderProfile,
    candidate: CandidateProfile,
) -> GeneratedEmail:
    to_email, to_name = _normalize_email(job)
    display_name = _recruiter_first_name(job.recruiter_name)
    role, company = _prepare_job_fields(job)

    prompt = f"""Write a complete job application email for a candidate applying via LinkedIn.

RULES:
- Role in email must be ONLY the job title: "{role}" — do NOT include years of experience in the role name
- Company name: "{company}"
- Subject MUST be exactly: Application for {role} at {company}
- Do NOT use [Company] or placeholders
- Keep 2-3 sentences about skills matching the job
- Do NOT invent skills the candidate does not have

Format:
Hi {display_name},
I came across your LinkedIn post regarding the opening for the {role} role at {company}...
[2-3 sentences]
Please find my resume attached...
Thanks & Regards,
{sender.name}

--- JOB POST ---
{_job_context(job)}

--- CANDIDATE ---
{_candidate_context(candidate)}

Return ONLY valid JSON:
{{"subject": "Application for {role} at {company}", "body": "full email with line breaks"}}
"""

    try:
        content = ollama.chat(prompt)
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            content = match.group(0)
        data = json.loads(content)
        # Always use cleaned subject — never trust Ollama's company parsing
        subject = _format_subject(role, company)
        return GeneratedEmail(
            subject=subject,
            body=data.get("body", "").strip(),
            to_email=to_email,
            to_name=to_name,
            source="ai",
        )
    except (OllamaError, json.JSONDecodeError, ValueError):
        # Fallback: return static-style if AI fails
        fallback = generate_static_email(
            job, sender,
            EmailTemplate(),
            candidate,
        )
        fallback.source = "ai"
        return fallback


def generate_email(
    job: ExtractedJobData,
    sender: SenderProfile,
    template: EmailTemplate,
    candidate: CandidateProfile | None = None,
) -> GeneratedEmail:
    """Generate AI email as primary. Use generate_both_emails for preview choice."""
    candidate = candidate or CandidateProfile()
    return generate_ai_email(job, sender, candidate)


def generate_both_emails(
    job: ExtractedJobData,
    sender: SenderProfile,
    template: EmailTemplate,
    candidate: CandidateProfile | None = None,
) -> tuple[GeneratedEmail, GeneratedEmail]:
    """Returns (ai_email, static_email). AI is primary default."""
    candidate = candidate or CandidateProfile()
    static_email = generate_static_email(job, sender, template, candidate)
    ai_email = generate_ai_email(job, sender, candidate)
    return ai_email, static_email
