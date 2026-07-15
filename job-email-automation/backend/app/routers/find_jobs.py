import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.config import ensure_default_resume_in_store, settings
from app.models import (
    BookmarkletCaptureRequest,
    CandidateProfile,
    EmailTemplate,
    EnrichPostRequest,
    EnrichPostResponse,
    ExtractedJobData,
    FindJobsImportRequest,
    FindJobsSearchRequest,
    FindJobsSearchResponse,
    JobItem,
    JobStatus,
    LinkedInPostResult,
    PasteJobRequest,
)
from app.services import job_store
from app.services.email_generator import generate_both_emails
from app.services.linkedin_finder import (
    DEFAULT_ROLES,
    parse_pasted_post,
    search_linkedin_posts,
)
from app.services.phase3_store import pick_resume_for_role, pick_template_for_role
from app.services.post_enricher import fetch_post_page

router = APIRouter(prefix="/api/find-jobs", tags=["find-jobs"])


def _existing_urls() -> set[str]:
    return {j.source_url for j in job_store.get_all().values() if j.source_url}


def _existing_emails() -> set[str]:
    emails: set[str] = set()
    for job in job_store.get_all().values():
        if job.extracted and job.extracted.recruiter_email:
            emails.add(job.extracted.recruiter_email.lower().strip())
        if job.email and job.email.to_email:
            emails.add(job.email.to_email.lower().strip())
    return emails


def _maybe_generate(
    job: JobItem,
    *,
    auto_generate: bool,
    sender,
    template: EmailTemplate | None,
    candidate: CandidateProfile | None,
) -> JobItem:
    if not auto_generate or not sender:
        return job
    if not job.extracted or not job.extracted.recruiter_email:
        return job

    try:
        role = job.extracted.role
        role_tpl = pick_template_for_role(role)
        resolved_template = template or EmailTemplate()
        if role_tpl and role_tpl.get("body_template"):
            resolved_template = EmailTemplate(
                subject_template=role_tpl.get("subject_template") or resolved_template.subject_template,
                body_template=role_tpl["body_template"],
            )

        ai_email, static_email = generate_both_emails(
            job.extracted,
            sender,
            resolved_template,
            candidate or CandidateProfile(),
        )
        job.email_ai = ai_email
        job.email_static = static_email
        job.email = ai_email
        job.status = JobStatus.EMAIL_GENERATED
        job.error = None

        resume = pick_resume_for_role(role)
        if not resume:
            resume, _ = ensure_default_resume_in_store()
        job.resume_filename = resume
    except Exception as e:
        job.status = JobStatus.EXTRACTED
        job.error = f"Imported — email generate failed: {e}"
    return job


def _create_job_from_post(
    post: LinkedInPostResult,
    *,
    source_type: str = "linkedin_post",
) -> JobItem:
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
    return JobItem(
        id=str(uuid.uuid4()),
        filename=f"LinkedIn: {post.role or 'Job Post'}",
        source_type=source_type,
        source_url=post.url or None,
        extracted=extracted,
        status=JobStatus.EXTRACTED if has_email else JobStatus.PENDING,
        error=None if has_email else "No email found — enrich URL, paste text, or add email manually",
    )


async def _enrich_post_dict(url: str, snippet: str = "") -> LinkedInPostResult | None:
    """Fetch public page and merge into parsed post fields."""
    page = await fetch_post_page(url)
    merged_text = "\n".join(filter(None, [snippet, page.get("text") or ""]))
    if page.get("recruiter_email"):
        # Prefer email from page; re-parse combined text for role/company
        parsed = parse_pasted_post(merged_text, url)
        parsed["recruiter_email"] = page["recruiter_email"]
        parsed["has_email"] = True
        if not parsed.get("snippet"):
            parsed["snippet"] = merged_text[:800]
        return LinkedInPostResult(**parsed)

    if merged_text.strip():
        parsed = parse_pasted_post(merged_text, url)
        return LinkedInPostResult(**parsed)

    return None


@router.post("/search", response_model=FindJobsSearchResponse)
async def find_jobs_search(request: FindJobsSearchRequest):
    roles = request.roles or DEFAULT_ROLES
    time_period = (request.time_period or "week").strip().lower()
    experience_range = (request.experience_range or "2-4").strip()

    if time_period not in ("day", "week", "month"):
        raise HTTPException(status_code=400, detail="time_period must be day, week, or month")

    try:
        raw = await search_linkedin_posts(
            roles=roles,
            max_results=request.max_results,
            time_period=time_period,
            experience_range=experience_range,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}") from e

    providers = []
    if raw and "_providers" in raw[0]:
        providers = raw[0].pop("_providers", [])

    posts = []
    for p in raw:
        clean = {k: v for k, v in p.items() if k not in ("time_period", "provider", "_providers")}
        posts.append(LinkedInPostResult(**clean))

    provider = "serpapi" if settings.serpapi_api_key and "serpapi" in providers else (
        providers[0] if providers else ("serpapi" if settings.serpapi_api_key else "ddgs")
    )

    return FindJobsSearchResponse(
        posts=posts,
        count=len(posts),
        roles_searched=roles,
        time_period=time_period,
        experience_range=experience_range,
        search_provider=provider,
    )


@router.post("/enrich", response_model=EnrichPostResponse)
async def enrich_linkedin_post(request: EnrichPostRequest):
    url = (request.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    page = await fetch_post_page(url)
    post = await _enrich_post_dict(url, request.snippet or "")

    return EnrichPostResponse(
        url=url,
        recruiter_email=page.get("recruiter_email"),
        emails=page.get("emails") or [],
        text=page.get("text") or "",
        login_wall=bool(page.get("login_wall")),
        ok=bool(page.get("ok") or (post and post.has_email)),
        error=page.get("error"),
        post=post,
    )


@router.post("/import")
async def import_linkedin_posts(request: FindJobsImportRequest):
    if not request.posts:
        raise HTTPException(status_code=400, detail="No posts selected")

    created: list[JobItem] = []
    skipped_url = 0
    skipped_email = 0
    enriched = 0
    existing_urls = _existing_urls()
    existing_emails = _existing_emails()

    for post in request.posts:
        # Auto-enrich posts missing email but having a URL
        if not post.recruiter_email and post.url:
            try:
                enriched_post = await _enrich_post_dict(post.url, post.snippet or "")
                if enriched_post and enriched_post.recruiter_email:
                    post = enriched_post
                    enriched += 1
            except Exception:
                pass

        if post.url and post.url in existing_urls:
            skipped_url += 1
            continue

        email_key = (post.recruiter_email or "").lower().strip()
        if email_key and email_key in existing_emails:
            skipped_email += 1
            continue

        job = _create_job_from_post(post)
        job = _maybe_generate(
            job,
            auto_generate=request.auto_generate,
            sender=request.sender,
            template=request.template,
            candidate=request.candidate,
        )
        job_store.set_job(job)
        if job.source_url:
            existing_urls.add(job.source_url)
        if email_key:
            existing_emails.add(email_key)
        created.append(job)

    return {
        "jobs": created,
        "count": len(created),
        "skipped_duplicate_url": skipped_url,
        "skipped_duplicate_email": skipped_email,
        "enriched": enriched,
        "generated": sum(1 for j in created if j.status == JobStatus.EMAIL_GENERATED),
    }


@router.post("/paste")
async def paste_linkedin_post(request: PasteJobRequest):
    text = (request.text or "").strip()
    url = (request.url or "").strip() or None
    if not text and not url:
        raise HTTPException(status_code=400, detail="Paste post text and/or a LinkedIn URL")

    # If only URL, try enrich first
    if url and not text:
        page = await fetch_post_page(url)
        text = page.get("text") or ""
        if page.get("recruiter_email") and page["recruiter_email"] not in text:
            text = f"{page['recruiter_email']}\n{text}"

    parsed = parse_pasted_post(text, url)
    post = LinkedInPostResult(**parsed)

    # Second chance enrich if still no email
    if not post.recruiter_email and url:
        enriched_post = await _enrich_post_dict(url, text)
        if enriched_post:
            post = enriched_post

    existing_urls = _existing_urls()
    existing_emails = _existing_emails()

    if post.url and post.url in existing_urls:
        raise HTTPException(status_code=409, detail="This LinkedIn post URL was already imported")

    email_key = (post.recruiter_email or "").lower().strip()
    if email_key and email_key in existing_emails:
        raise HTTPException(
            status_code=409,
            detail=f"Already have a job for recruiter email {post.recruiter_email}",
        )

    job = _create_job_from_post(post, source_type="pasted")
    job = _maybe_generate(
        job,
        auto_generate=request.auto_generate,
        sender=request.sender,
        template=request.template,
        candidate=request.candidate,
    )
    job_store.set_job(job)

    return {
        "job": job,
        "parsed": post,
        "generated": job.status == JobStatus.EMAIL_GENERATED,
    }


@router.post("/bookmarklet-capture")
async def bookmarklet_capture(request: BookmarkletCaptureRequest):
    """Same as paste, but designed for LinkedIn bookmarklet (CORS from linkedin.com)."""
    paste_req = PasteJobRequest(
        text=request.text,
        url=request.url,
        auto_generate=request.auto_generate,
        sender=request.sender,
        template=request.template,
        candidate=request.candidate,
    )
    return await paste_linkedin_post(paste_req)


@router.get("/bookmarklet", response_class=HTMLResponse)
async def bookmarklet_help():
    """Instructions + drag-to-bookmarks link for LinkedIn Send-to-App."""
    # Uses localhost API — user may need backend running
    api = "http://127.0.0.1:8000/api/find-jobs/bookmarklet-capture"
    # Minimal bookmarklet: send selected text + URL to API, toast result
    js = (
        "javascript:(function(){"
        "var t=window.getSelection&window.getSelection().toString();"
        "if(!t){t=prompt('Select post text first, or paste email+post text here','')||'';}"
        "var u=location.href;"
        "fetch('" + api + "',{method:'POST',headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({text:t,url:u,auto_generate:true})})"
        ".then(function(r){return r.json().then(function(d){if(!r.ok)throw new Error(d.detail||r.statusText);return d;})})"
        ".then(function(d){alert('Sent to Job Email App'+(d.generated?' — email generated!':'')+"
        "'\\nOpen http://localhost:5173 to review');})"
        ".catch(function(e){alert('Failed: '+e.message+'\\nIs backend running on :8000?');});"
        "})();"
    )
    # HTML-escape for href
    href = js.replace('"', "&quot;")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>LinkedIn → Job Email App Bookmarklet</title>
  <style>
    body {{ font-family: system-ui,sans-serif; max-width: 640px; margin: 40px auto; padding: 0 20px; line-height: 1.5; }}
    .btn {{ display: inline-block; padding: 12px 18px; background: #0a66c2; color: #fff; border-radius: 8px;
            text-decoration: none; font-weight: 600; }}
    code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; }}
    ol {{ padding-left: 1.2em; }}
    .note {{ color: #666; font-size: 14px; }}
  </style>
</head>
<body>
  <h1>Send LinkedIn post to Job Email App</h1>
  <p>Phase 2 helper — while browsing LinkedIn, select a hiring post and send it to your local app.</p>
  <p><strong>Drag this to your bookmarks bar:</strong></p>
  <p><a class="btn" href="{href}">Send to Job Email App</a></p>
  <h2>How to use</h2>
  <ol>
    <li>Start backend on <code>http://localhost:8000</code> and frontend on <code>5173</code>.</li>
    <li>On LinkedIn, open a recruiter hiring post.</li>
    <li>Select the post text (or click bookmark and paste when prompted).</li>
    <li>Click the <strong>Send to Job Email App</strong> bookmark.</li>
    <li>Open the app → Review &amp; Send.</li>
  </ol>
  <p class="note">This does <em>not</em> automate LinkedIn login or mass-scraping your account.
     You choose each post — safer and more accurate.</p>
  <p class="note">Optional: set <code>SERPAPI_API_KEY</code> in <code>backend/.env</code> for better search discovery.</p>
</body>
</html>"""
    return HTMLResponse(html)
