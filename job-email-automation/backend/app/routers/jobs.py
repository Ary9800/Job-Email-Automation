import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.config import RESUME_DIR, UPLOAD_DIR, ensure_default_resume_in_store, resolve_resume_path, settings
from app.models import (
    BatchSendRequest,
    EmailTemplate,
    ExtractedJobData,
    FixEmailRequest,
    GenerateEmailRequest,
    GeneratedEmail,
    JobItem,
    JobStatus,
    ProcessRequest,
    SaveDraftRequest,
    SendEmailRequest,
)
from app.services import job_store
from app.services.email_generator import generate_both_emails
from app.services.email_sender import send_email_with_resume
from app.services.extractor import extract_job_from_screenshot
from app.services.llm import ollama
from app.services.phase3_store import pick_resume_for_role, pick_template_for_role

router = APIRouter(prefix="/api", tags=["jobs"])


def _resolve_template_for_job(job: JobItem, fallback: EmailTemplate) -> EmailTemplate:
    role = job.extracted.role if job.extracted else None
    role_tpl = pick_template_for_role(role)
    if not role_tpl or not role_tpl.get("body_template"):
        return fallback
    return EmailTemplate(
        subject_template=role_tpl.get("subject_template") or fallback.subject_template,
        body_template=role_tpl["body_template"],
    )


def _resolve_resume_for_job(job: JobItem, explicit: str | None = None) -> str | None:
    """Pick resume file that actually exists on disk."""
    # Prefer explicitly requested file if it exists
    if explicit:
        path = resolve_resume_path(explicit)
        if path and path.parent == RESUME_DIR:
            return path.name
        if path:
            stored, _ = ensure_default_resume_in_store()
            return stored or path.name

    # Job already has a valid resume from generate/import
    if job.resume_filename:
        path = resolve_resume_path(job.resume_filename)
        if path:
            return path.name if path.parent == RESUME_DIR else job.resume_filename

    role = job.extracted.role if job.extracted else None
    picked = pick_resume_for_role(role)
    if picked and resolve_resume_path(picked):
        return picked

    resume, _ = ensure_default_resume_in_store()
    if resume:
        return resume

    path = resolve_resume_path(None)
    return path.name if path and path.parent == RESUME_DIR else (str(path) if path else None)

def _get_job(job_id: str) -> JobItem:
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job not found. Backend may have restarted — re-upload screenshots and run Extract & Generate again.",
        )
    return job


def _save(job: JobItem) -> JobItem:
    job_store.set_job(job)
    return job


@router.post("/upload")
async def upload_screenshots(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    created = []

    for file in files:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"{file.filename} is not an image")

        content = await file.read()
        if len(content) > max_bytes:
            raise HTTPException(status_code=400, detail=f"{file.filename} exceeds size limit")

        job_id = str(uuid.uuid4())
        ext = Path(file.filename or "screenshot.png").suffix or ".png"
        saved_name = f"{job_id}{ext}"
        save_path = UPLOAD_DIR / saved_name

        with open(save_path, "wb") as f:
            f.write(content)

        job = JobItem(id=job_id, filename=file.filename or saved_name)
        _save(job)
        created.append(job)

    return {"jobs": created, "count": len(created)}


@router.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    allowed = {".pdf", ".doc", ".docx"}
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Resume must be PDF or Word document")

    content = await file.read()
    resume_id = f"resume_{uuid.uuid4().hex[:8]}{ext}"
    save_path = RESUME_DIR / resume_id

    with open(save_path, "wb") as f:
        f.write(content)

    return {"filename": resume_id, "original_name": file.filename}


@router.get("/jobs")
async def list_jobs():
    jobs = list(job_store.get_all().values())
    # Annotate whether a screenshot file exists (for UI)
    result = []
    for job in jobs:
        data = job.model_dump(mode="json")
        data["has_screenshot"] = any(UPLOAD_DIR.glob(f"{job.id}.*"))
        result.append(data)
    return {"jobs": result}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    return _get_job(job_id)


@router.get("/jobs/{job_id}/screenshot")
async def get_job_screenshot(job_id: str):
    """Serve the uploaded screenshot image for review UI."""
    _get_job(job_id)
    paths = list(UPLOAD_DIR.glob(f"{job_id}.*"))
    if not paths:
        raise HTTPException(status_code=404, detail="No screenshot for this job")

    path = paths[0]
    media = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }.get(path.suffix.lower(), "application/octet-stream")

    return FileResponse(path, media_type=media, filename=path.name)


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    _get_job(job_id)
    for path in UPLOAD_DIR.glob(f"{job_id}.*"):
        path.unlink(missing_ok=True)
    job_store.delete(job_id)
    return {"deleted": job_id}


@router.post("/jobs/{job_id}/extract")
async def extract_job(job_id: str):
    job = _get_job(job_id)
    image_paths = list(UPLOAD_DIR.glob(f"{job_id}.*"))
    if not image_paths:
        raise HTTPException(status_code=404, detail="Screenshot file not found")

    try:
        extracted = extract_job_from_screenshot(image_paths[0])
        job.extracted = extracted
        job.status = JobStatus.EXTRACTED if extracted.recruiter_email else JobStatus.FAILED
        if not extracted.recruiter_email:
            job.error = "Could not find recruiter email in screenshot"
        else:
            job.error = None
    except Exception as e:
        job.status = JobStatus.FAILED
        job.error = str(e)

    return _save(job)


@router.patch("/jobs/{job_id}/fix-email")
async def fix_job_email(job_id: str, request: FixEmailRequest):
    job = _get_job(job_id)
    email = request.recruiter_email.strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address")

    if not job.extracted:
        job.extracted = ExtractedJobData(recruiter_email=email)
    else:
        job.extracted.recruiter_email = email
        if request.recruiter_name:
            job.extracted.recruiter_name = request.recruiter_name
        if request.role:
            job.extracted.role = request.role
        if request.company:
            job.extracted.company = request.company

    job.status = JobStatus.EXTRACTED
    job.error = None
    return _save(job)


@router.post("/jobs/{job_id}/generate-email")
async def generate_job_email(job_id: str, request: GenerateEmailRequest):
    job = _get_job(job_id)
    if not job.extracted:
        raise HTTPException(status_code=400, detail="Extract job details first")

    try:
        template = _resolve_template_for_job(job, request.template)
        ai_email, static_email = generate_both_emails(
            job.extracted, request.sender, template, request.candidate
        )
        job.email_ai = ai_email
        job.email_static = static_email
        job.email = ai_email
        job.resume_filename = _resolve_resume_for_job(job)
        job.status = JobStatus.EMAIL_GENERATED
        job.error = None if ai_email.to_email else "Generated email but recipient address is missing"
    except Exception as e:
        job.status = JobStatus.FAILED
        job.error = str(e)

    return _save(job)


@router.patch("/jobs/{job_id}/draft")
async def save_job_draft(job_id: str, request: SaveDraftRequest):
    """Persist review-panel edits so retries keep the same subject/body/to."""
    job = _get_job(job_id)

    base = job.email or GeneratedEmail(
        subject="",
        body="",
        to_email=job.extracted.recruiter_email if job.extracted else "",
        to_name=job.extracted.recruiter_name if job.extracted else None,
    )

    if request.subject is not None:
        base.subject = request.subject
    if request.body is not None:
        base.body = request.body
    if request.to_email is not None:
        base.to_email = request.to_email
    if request.to_name is not None:
        base.to_name = request.to_name
    if request.source:
        base.source = request.source

    job.email = base

    # Keep job retryable after a previous send failure
    if job.status == JobStatus.FAILED and base.to_email and base.subject:
        job.status = JobStatus.EMAIL_GENERATED
        # Keep last error visible until next successful send
        if job.error and not job.error.startswith("Last send failed:"):
            job.error = f"Last send failed: {job.error}"

    return _save(job)


@router.post("/jobs/{job_id}/send")
async def send_job_email(job_id: str, request: SendEmailRequest):
    job = _get_job(job_id)

    if not job.email and not (request.subject and request.body):
        raise HTTPException(status_code=400, detail="Generate email first or provide subject/body")

    email = job.email or GeneratedEmail(
        subject=request.subject or "",
        body=request.body or "",
        to_email=job.extracted.recruiter_email if job.extracted else "",
        to_name=job.extracted.recruiter_name if job.extracted else None,
    )

    if request.subject:
        email.subject = request.subject
    if request.body:
        email.body = request.body
    if request.to_email:
        email.to_email = request.to_email

    # Always persist review edits before attempting send (needed for retries)
    job.email = email
    job.resume_filename = _resolve_resume_for_job(job, request.resume_filename)
    if not resolve_resume_path(job.resume_filename):
        raise HTTPException(
            status_code=400,
            detail="No resume file found. Set DEFAULT_RESUME_PATH in backend/.env to a real PDF path, or upload a resume in Settings.",
        )
    _save(job)

    try:
        await send_email_with_resume(email, request.sender, request.smtp, job.resume_filename)
        job.status = JobStatus.SENT
        job.outcome = "waiting"
        job.sent_at = datetime.now().isoformat(timespec="seconds")
        job.outcome_updated_at = job.sent_at
        job.error = None
    except Exception as e:
        job.status = JobStatus.FAILED
        job.error = str(e)
        # Stay retryable — email draft remains saved
        _save(job)
        raise HTTPException(status_code=500, detail=str(e)) from e

    return _save(job)


@router.post("/process-batch")
async def process_batch(
    request: ProcessRequest,
    job_ids: list[str] | None = Query(default=None),
):
    ids = job_ids or list(job_store.get_all().keys())
    results = []

    resume_filename = request.resume_filename
    if not resume_filename:
        resume_filename, _ = ensure_default_resume_in_store()

    for job_id in ids:
        job = job_store.get(job_id)
        if not job:
            continue

        # Skip already sent jobs — do not re-extract
        if job.status == JobStatus.SENT:
            results.append(job)
            continue

        try:
            # LinkedIn / pasted imports already have extracted data — skip screenshot OCR
            if job.source_type in ("linkedin_post", "pasted") and job.extracted:
                if not job.extracted.recruiter_email:
                    job.status = JobStatus.FAILED
                    job.error = "No recruiter email found in post — add manually"
                else:
                    template = _resolve_template_for_job(job, request.template)
                    ai_email, static_email = generate_both_emails(
                        job.extracted, request.sender, template, request.candidate
                    )
                    job.email_ai = ai_email
                    job.email_static = static_email
                    job.email = ai_email
                    job.resume_filename = _resolve_resume_for_job(job, resume_filename)
                    job.status = JobStatus.EMAIL_GENERATED

                    if request.auto_send:
                        await send_email_with_resume(
                            job.email, request.sender, request.smtp, job.resume_filename
                        )
                        job.status = JobStatus.SENT
                        job.outcome = "waiting"
                        job.sent_at = datetime.now().isoformat(timespec="seconds")
            else:
                image_paths = list(UPLOAD_DIR.glob(f"{job_id}.*"))
                if image_paths:
                    job.extracted = extract_job_from_screenshot(image_paths[0])
                    job.status = JobStatus.EXTRACTED

                if job.extracted and job.extracted.recruiter_email:
                    template = _resolve_template_for_job(job, request.template)
                    ai_email, static_email = generate_both_emails(
                        job.extracted, request.sender, template, request.candidate
                    )
                    job.email_ai = ai_email
                    job.email_static = static_email
                    job.email = ai_email
                    job.resume_filename = _resolve_resume_for_job(job, resume_filename)
                    job.status = JobStatus.EMAIL_GENERATED

                    if request.auto_send:
                        await send_email_with_resume(
                            job.email, request.sender, request.smtp, job.resume_filename
                        )
                        job.status = JobStatus.SENT
                        job.outcome = "waiting"
                        job.sent_at = datetime.now().isoformat(timespec="seconds")
                elif job.extracted:
                    job.status = JobStatus.FAILED
                    job.error = "No recruiter email found in screenshot"
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)

        _save(job)
        data = job.model_dump(mode="json")
        data["has_screenshot"] = any(UPLOAD_DIR.glob(f"{job.id}.*"))
        results.append(data)

    return {"jobs": results, "processed": len(results)}


@router.post("/send-batch")
async def send_batch(request: BatchSendRequest):
    results = []
    resume_filename = request.resume_filename
    if not resume_filename:
        resume_filename, _ = ensure_default_resume_in_store()

    for job_id in request.job_ids:
        job = job_store.get(job_id)
        if not job or not job.email:
            continue
        try:
            await send_email_with_resume(
                job.email, request.sender, request.smtp, resume_filename
            )
            job.status = JobStatus.SENT
            job.error = None
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
        _save(job)
        results.append(job)

    return {"jobs": results, "sent": sum(1 for j in results if j.status == JobStatus.SENT)}


@router.get("/health")
async def health():
    available = ollama.is_available()
    models = ollama.list_models() if available else []
    vision_ready = ollama.has_model(settings.ollama_vision_model) if available else False
    text_ready = ollama.has_model(settings.ollama_text_model) if available else False

    return {
        "status": "ok" if available and vision_ready and text_ready else "degraded",
        "ai_provider": "ollama",
        "ollama_running": available,
        "ollama_url": settings.ollama_base_url,
        "vision_model": settings.ollama_vision_model,
        "text_model": settings.ollama_text_model,
        "vision_model_ready": vision_ready,
        "text_model_ready": text_ready,
        "installed_models": models,
        "ai_ready": available and vision_ready and text_ready,
        "jobs_count": len(job_store.get_all()),
    }
