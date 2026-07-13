import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.config import RESUME_DIR, UPLOAD_DIR, ensure_default_resume_in_store, settings
from app.models import (
    BatchSendRequest,
    ExtractedJobData,
    FixEmailRequest,
    GenerateEmailRequest,
    GeneratedEmail,
    JobItem,
    JobStatus,
    ProcessRequest,
    SendEmailRequest,
)
from app.services.email_generator import generate_both_emails
from app.services.email_sender import send_email_with_resume
from app.services.extractor import extract_job_from_screenshot
from app.services import job_store
from app.services.llm import ollama

router = APIRouter(prefix="/api", tags=["jobs"])


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
    return {"jobs": list(job_store.get_all().values())}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    return _get_job(job_id)


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
        ai_email, static_email = generate_both_emails(
            job.extracted, request.sender, request.template, request.candidate
        )
        job.email_ai = ai_email
        job.email_static = static_email
        job.email = ai_email
        job.status = JobStatus.EMAIL_GENERATED
        job.error = None if ai_email.to_email else "Generated email but recipient address is missing"
    except Exception as e:
        job.status = JobStatus.FAILED
        job.error = str(e)

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

    resume_filename = request.resume_filename
    if not resume_filename:
        resume_filename, _ = ensure_default_resume_in_store()

    try:
        await send_email_with_resume(email, request.sender, request.smtp, resume_filename)
        job.status = JobStatus.SENT
        job.error = None
    except Exception as e:
        job.status = JobStatus.FAILED
        job.error = str(e)
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
            # LinkedIn post imports already have extracted data — skip screenshot OCR
            if job.source_type == "linkedin_post" and job.extracted:
                if not job.extracted.recruiter_email:
                    job.status = JobStatus.FAILED
                    job.error = "No recruiter email found in post — add manually"
                else:
                    ai_email, static_email = generate_both_emails(
                        job.extracted, request.sender, request.template, request.candidate
                    )
                    job.email_ai = ai_email
                    job.email_static = static_email
                    job.email = ai_email
                    job.status = JobStatus.EMAIL_GENERATED

                    if request.auto_send:
                        await send_email_with_resume(
                            job.email, request.sender, request.smtp, resume_filename
                        )
                        job.status = JobStatus.SENT
            else:
                image_paths = list(UPLOAD_DIR.glob(f"{job_id}.*"))
                if image_paths:
                    job.extracted = extract_job_from_screenshot(image_paths[0])
                    job.status = JobStatus.EXTRACTED

                if job.extracted and job.extracted.recruiter_email:
                    ai_email, static_email = generate_both_emails(
                        job.extracted, request.sender, request.template, request.candidate
                    )
                    job.email_ai = ai_email
                    job.email_static = static_email
                    job.email = ai_email
                    job.status = JobStatus.EMAIL_GENERATED

                    if request.auto_send:
                        await send_email_with_resume(
                            job.email, request.sender, request.smtp, resume_filename
                        )
                        job.status = JobStatus.SENT
                elif job.extracted:
                    job.status = JobStatus.FAILED
                    job.error = "No recruiter email found in screenshot"
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)

        _save(job)
        results.append(job)

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
