import json
import logging
from pathlib import Path

from app.config import BASE_DIR
from app.models import JobItem

logger = logging.getLogger(__name__)

DATA_DIR = BASE_DIR / "data"
JOBS_FILE = DATA_DIR / "jobs.json"

_jobs: dict[str, JobItem] = {}


def _persist() -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data = {job_id: job.model_dump(mode="json") for job_id, job in _jobs.items()}
        JOBS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to save jobs: %s", exc)


def _load() -> None:
    global _jobs
    if not JOBS_FILE.exists():
        return
    try:
        raw = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
        _jobs = {job_id: JobItem(**item) for job_id, item in raw.items()}
        logger.info("Loaded %d jobs from disk", len(_jobs))
    except Exception as exc:
        logger.warning("Failed to load jobs: %s", exc)
        _jobs = {}


def get_all() -> dict[str, JobItem]:
    return _jobs


def get(job_id: str) -> JobItem | None:
    return _jobs.get(job_id)


def set_job(job: JobItem) -> None:
    _jobs[job.id] = job
    _persist()


def set_jobs(jobs: dict[str, JobItem]) -> None:
    _jobs.update(jobs)
    _persist()


def delete(job_id: str) -> None:
    _jobs.pop(job_id, None)
    _persist()


# Load saved jobs on startup
_load()
