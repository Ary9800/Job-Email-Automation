"""Background daily LinkedIn search + import job."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.config import ensure_default_resume_in_store, settings
from app.models import (
    CandidateProfile,
    EmailTemplate,
    ExtractedJobData,
    JobItem,
    JobStatus,
    LinkedInPostResult,
    SenderProfile,
)
from app.services import job_store
from app.services.email_generator import generate_both_emails
from app.services.linkedin_finder import search_linkedin_posts
from app.services.phase3_store import (
    get_scheduler_config,
    pick_resume_for_role,
    pick_template_for_role,
    save_scheduler_config,
)
from app.services.post_enricher import fetch_post_page
from app.services.linkedin_finder import parse_pasted_post

logger = logging.getLogger(__name__)

_task: Optional[asyncio.Task] = None
_stop = asyncio.Event()


def _existing_urls() -> set[str]:
    return {j.source_url for j in job_store.get_all().values() if j.source_url}


def _existing_emails() -> set[str]:
    emails: set[str] = set()
    for job in job_store.get_all().values():
        if job.extracted and job.extracted.recruiter_email:
            emails.add(job.extracted.recruiter_email.lower().strip())
    return emails


async def run_daily_pipeline(force: bool = False) -> dict:
    """Search + import + generate based on scheduler config."""
    cfg = get_scheduler_config()
    if not cfg.get("enabled") and not force:
        return {"ok": False, "message": "Scheduler disabled"}

    roles = cfg.get("roles") or ["Java Developer"]
    time_period = cfg.get("time_period") or "day"
    experience_range = cfg.get("experience_range") or "2-4"

    raw = await search_linkedin_posts(
        roles=roles,
        max_results=20,
        time_period=time_period,
        experience_range=experience_range,
    )

    existing_urls = _existing_urls()
    existing_emails = _existing_emails()
    imported = 0
    generated = 0
    skipped = 0

    sender = SenderProfile(
        name=settings.sender_name,
        email=settings.sender_email or "not-configured@local.dev",
        phone=settings.sender_phone,
    )
    candidate = CandidateProfile(
        current_role=settings.candidate_current_role,
        years_experience=settings.candidate_years_experience,
        key_skills=settings.candidate_key_skills,
        experience_summary=settings.candidate_experience_summary,
    )
    default_template = EmailTemplate(
        subject_template=settings.email_subject_template,
        body_template=settings.email_body_template,
    )

    for item in raw:
        clean = {k: v for k, v in item.items() if k not in ("time_period", "provider", "_providers")}
        post = LinkedInPostResult(**clean)

        if not post.recruiter_email and post.url and cfg.get("auto_import"):
            try:
                page = await fetch_post_page(post.url)
                if page.get("recruiter_email") or page.get("text"):
                    merged = parse_pasted_post(
                        "\n".join(filter(None, [post.snippet, page.get("text") or ""])),
                        post.url,
                    )
                    if page.get("recruiter_email"):
                        merged["recruiter_email"] = page["recruiter_email"]
                        merged["has_email"] = True
                    post = LinkedInPostResult(**merged)
            except Exception:
                pass

        if post.url and post.url in existing_urls:
            skipped += 1
            continue
        email_key = (post.recruiter_email or "").lower().strip()
        if email_key and email_key in existing_emails:
            skipped += 1
            continue

        if not cfg.get("auto_import"):
            continue

        import uuid
        has_email = bool(post.recruiter_email)
        extracted = ExtractedJobData(
            recruiter_email=post.recruiter_email,
            recruiter_name=post.recruiter_name,
            role=post.role,
            company=post.company,
            job_description=post.snippet,
            experience_required=post.experience_required,
            source_platform="LinkedIn",
            content_summary=post.snippet[:300] if post.snippet else post.title,
            confidence=post.score,
            raw_text=post.snippet or post.title,
        )
        job = JobItem(
            id=str(uuid.uuid4()),
            filename=f"Auto: {post.role or 'Job Post'}",
            source_type="linkedin_post",
            source_url=post.url or None,
            extracted=extracted,
            status=JobStatus.EXTRACTED if has_email else JobStatus.PENDING,
            outcome="none",
            error=None if has_email else "No email — paste or enrich",
        )

        if has_email and cfg.get("auto_generate") and settings.sender_email:
            role_tpl = pick_template_for_role(post.role)
            template = default_template
            if role_tpl and role_tpl.get("body_template"):
                template = EmailTemplate(
                    subject_template=role_tpl.get("subject_template") or default_template.subject_template,
                    body_template=role_tpl["body_template"],
                )
            try:
                ai_email, static_email = generate_both_emails(
                    extracted, sender, template, candidate
                )
                job.email_ai = ai_email
                job.email_static = static_email
                job.email = ai_email
                job.status = JobStatus.EMAIL_GENERATED
                resume = pick_resume_for_role(post.role)
                if not resume:
                    resume, _ = ensure_default_resume_in_store()
                job.resume_filename = resume
                generated += 1
            except Exception as e:
                job.error = f"Generate failed: {e}"

        job_store.set_job(job)
        imported += 1
        if post.url:
            existing_urls.add(post.url)
        if email_key:
            existing_emails.add(email_key)

    summary = {
        "ok": True,
        "found": len(raw),
        "imported": imported,
        "generated": generated,
        "skipped": skipped,
        "ran_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_scheduler_config({
        "last_run_at": summary["ran_at"],
        "last_run_summary": summary,
    })
    logger.info("Daily pipeline: %s", summary)
    return summary


async def _loop() -> None:
    """Check every 60s whether it's time to run the daily job."""
    last_day_ran: str | None = None
    while not _stop.is_set():
        try:
            cfg = get_scheduler_config()
            if cfg.get("enabled"):
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")
                hour = int(cfg.get("hour", 9))
                minute = int(cfg.get("minute", 0))
                if now.hour == hour and now.minute == minute and last_day_ran != today:
                    await run_daily_pipeline(force=True)
                    last_day_ran = today
        except Exception as e:
            logger.exception("Scheduler loop error: %s", e)

        try:
            await asyncio.wait_for(_stop.wait(), timeout=60)
        except asyncio.TimeoutError:
            pass


def start_scheduler() -> None:
    global _task
    if _task and not _task.done():
        return
    _stop.clear()
    _task = asyncio.create_task(_loop())
    logger.info("Phase 3 daily scheduler started")


def stop_scheduler() -> None:
    _stop.set()
