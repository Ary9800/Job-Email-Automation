import uuid

from fastapi import APIRouter, HTTPException

from app.models import (
    ExtractedJobData,
    FindJobsImportRequest,
    FindJobsSearchRequest,
    FindJobsSearchResponse,
    JobItem,
    JobStatus,
    LinkedInPostResult,
)
from app.services import job_store
from app.services.linkedin_finder import DEFAULT_ROLES, search_linkedin_posts

router = APIRouter(prefix="/api/find-jobs", tags=["find-jobs"])


@router.post("/search", response_model=FindJobsSearchResponse)
async def find_jobs_search(request: FindJobsSearchRequest):
    roles = request.roles or DEFAULT_ROLES
    try:
        raw = await search_linkedin_posts(roles=roles, max_results=request.max_results)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}") from e

    posts = [LinkedInPostResult(**p) for p in raw]
    return FindJobsSearchResponse(posts=posts, count=len(posts), roles_searched=roles)


@router.post("/import")
async def import_linkedin_posts(request: FindJobsImportRequest):
    if not request.posts:
        raise HTTPException(status_code=400, detail="No posts selected")

    created: list[JobItem] = []
    existing_urls = {
        j.source_url for j in job_store.get_all().values() if j.source_url
    }

    for post in request.posts:
        if post.url in existing_urls:
            continue

        job_id = str(uuid.uuid4())
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

        has_email = bool(post.recruiter_email)
        job = JobItem(
            id=job_id,
            filename=f"LinkedIn: {post.role or 'Job Post'}",
            source_type="linkedin_post",
            source_url=post.url,
            extracted=extracted,
            status=JobStatus.EXTRACTED if has_email else JobStatus.PENDING,
            error=None if has_email else "No email in post snippet — add manually or open post",
        )
        job_store.set_job(job)
        existing_urls.add(post.url)
        created.append(job)

    return {"jobs": created, "count": len(created)}
