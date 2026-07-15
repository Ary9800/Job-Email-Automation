"""Phase 3: tracker outcomes, analytics, resumes, templates, scheduler."""

from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.models import (
    ResumeProfilesUpdate,
    RoleTemplatesUpdate,
    SchedulerConfigUpdate,
    UpdateOutcomeRequest,
)
from app.services import job_store
from app.services.daily_scheduler import run_daily_pipeline
from app.services.phase3_store import (
    get_resume_profiles,
    get_role_templates,
    get_scheduler_config,
    pick_resume_for_role,
    save_resume_profiles,
    save_role_templates,
    save_scheduler_config,
)

router = APIRouter(prefix="/api", tags=["phase3"])

VALID_OUTCOMES = {
    "none", "waiting", "replied", "interview", "rejected", "hired", "no_response",
}


@router.patch("/jobs/{job_id}/outcome")
async def update_job_outcome(job_id: str, request: UpdateOutcomeRequest):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    outcome = request.outcome.strip().lower()
    if outcome not in VALID_OUTCOMES:
        raise HTTPException(
            status_code=400,
            detail=f"outcome must be one of: {', '.join(sorted(VALID_OUTCOMES))}",
        )

    job.outcome = outcome
    job.outcome_updated_at = datetime.now().isoformat(timespec="seconds")
    if request.notes is not None:
        job.notes = request.notes
    # When user marks waiting after send flow
    if outcome == "waiting" and job.status.value == "sent" and not job.sent_at:
        job.sent_at = job.outcome_updated_at
    job_store.set_job(job)
    return job


@router.get("/analytics")
async def get_analytics():
    jobs = list(job_store.get_all().values())
    by_status: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    by_role: dict[str, dict] = {}
    by_company: dict[str, dict] = {}

    sent = 0
    replied = 0
    interview = 0

    for job in jobs:
        by_status[job.status.value] = by_status.get(job.status.value, 0) + 1
        outcome = job.outcome or "none"
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1

        if job.status.value == "sent":
            sent += 1
        if outcome == "replied":
            replied += 1
        if outcome == "interview":
            interview += 1

        role = (job.extracted.role if job.extracted else None) or "Unknown"
        company = (job.extracted.company if job.extracted else None) or "Unknown"

        if role not in by_role:
            by_role[role] = {"total": 0, "sent": 0, "replied": 0, "interview": 0}
        by_role[role]["total"] += 1
        if job.status.value == "sent":
            by_role[role]["sent"] += 1
        if outcome == "replied":
            by_role[role]["replied"] += 1
        if outcome == "interview":
            by_role[role]["interview"] += 1

        if company not in by_company:
            by_company[company] = {"total": 0, "sent": 0, "replied": 0}
        by_company[company]["total"] += 1
        if job.status.value == "sent":
            by_company[company]["sent"] += 1
        if outcome in ("replied", "interview", "hired"):
            by_company[company]["replied"] += 1

    reply_rate = round((replied + interview) / sent * 100, 1) if sent else 0.0

    tracked = [
        j for j in jobs
        if j.status.value == "sent" or (j.outcome and j.outcome != "none")
    ]
    tracked.sort(key=lambda j: j.sent_at or j.outcome_updated_at or "", reverse=True)

    return {
        "summary": {
            "total_jobs": len(jobs),
            "sent": sent,
            "replied": replied,
            "interview": interview,
            "reply_rate_pct": reply_rate,
            "by_status": by_status,
            "by_outcome": by_outcome,
        },
        "by_role": by_role,
        "by_company": dict(sorted(by_company.items(), key=lambda x: -x[1]["sent"])[:20]),
        "tracked_jobs": tracked[:50],
    }


@router.get("/resumes/profiles")
async def list_resume_profiles():
    return get_resume_profiles()


@router.put("/resumes/profiles")
async def update_resume_profiles(request: ResumeProfilesUpdate):
    data = {"profiles": [p.model_dump() for p in request.profiles]}
    return save_resume_profiles(data)


@router.get("/resumes/suggest")
async def suggest_resume(role: str = ""):
    filename = pick_resume_for_role(role)
    return {"role": role, "resume_filename": filename}


@router.get("/templates/roles")
async def list_role_templates():
    return get_role_templates()


@router.put("/templates/roles")
async def update_role_templates(request: RoleTemplatesUpdate):
    data = {"templates": [t.model_dump() for t in request.templates]}
    return save_role_templates(data)


@router.get("/scheduler")
async def get_scheduler():
    return get_scheduler_config()


@router.put("/scheduler")
async def update_scheduler(request: SchedulerConfigUpdate):
    updates = request.model_dump(exclude_none=True)
    return save_scheduler_config(updates)


@router.post("/scheduler/run-now")
async def run_scheduler_now():
    return await run_daily_pipeline(force=True)
