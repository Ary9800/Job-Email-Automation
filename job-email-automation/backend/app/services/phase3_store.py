"""JSON stores for Phase 3: resumes map, role templates, scheduler config."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.config import BASE_DIR, RESUME_DIR

logger = logging.getLogger(__name__)
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

RESUMES_FILE = DATA_DIR / "resume_profiles.json"
TEMPLATES_FILE = DATA_DIR / "role_templates.json"
SCHEDULER_FILE = DATA_DIR / "scheduler.json"


def _read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed reading %s: %s", path, e)
        return default


def _write(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------- Multi-resume ----------

DEFAULT_RESUME_PROFILES = {
    "profiles": [
        {
            "id": "default",
            "label": "Default / Java Full Stack",
            "filename": None,  # uses DEFAULT_RESUME_PATH / default_resume.pdf
            "role_keywords": ["java", "full stack", "fullstack", "software engineer"],
        },
        {
            "id": "backend",
            "label": "Backend / Java Backend",
            "filename": None,
            "role_keywords": ["backend", "java backend", "spring"],
        },
    ]
}


def get_resume_profiles() -> dict:
    data = _read(RESUMES_FILE, None)
    if not data:
        data = DEFAULT_RESUME_PROFILES
        _write(RESUMES_FILE, data)
    return data


def save_resume_profiles(data: dict) -> dict:
    _write(RESUMES_FILE, data)
    return data


def pick_resume_for_role(role: str | None, profiles: dict | None = None) -> str | None:
    """Return stored resume filename matching role keywords, else None (use default)."""
    profiles = profiles or get_resume_profiles()
    role_l = (role or "").lower()
    best = None
    best_score = 0
    for p in profiles.get("profiles", []):
        keywords = p.get("role_keywords") or []
        score = sum(1 for kw in keywords if kw.lower() in role_l)
        if score > best_score and p.get("filename"):
            # verify file exists
            path = RESUME_DIR / p["filename"]
            if path.exists():
                best_score = score
                best = p["filename"]
    return best


# ---------- Role templates ----------

DEFAULT_ROLE_TEMPLATES = {
    "templates": [
        {
            "id": "default",
            "label": "Default",
            "role_keywords": [],
            "subject_template": "Application for {role} at {company}",
            "body_template": None,  # use settings default
        },
        {
            "id": "java-backend",
            "label": "Java Backend",
            "role_keywords": ["backend", "java backend", "spring"],
            "subject_template": "Application for {role} at {company}",
            "body_template": """Hi {recruiter_name},

I came across your LinkedIn post regarding the opening for the {role} role at {company} and found it closely aligned with my Java backend experience.

{experience_summary}

I have hands-on experience with Spring Boot, REST APIs, and SQL-backed services. Please find my resume attached.

Looking forward to hearing from you.

Thanks & Regards,
{sender_name}""",
        },
        {
            "id": "fullstack",
            "label": "Java Full Stack",
            "role_keywords": ["full stack", "fullstack"],
            "subject_template": "Application for {role} at {company}",
            "body_template": """Hi {recruiter_name},

I came across your LinkedIn post regarding the opening for the {role} role at {company} and found the opportunity closely aligned with my full-stack Java background.

{experience_summary}

Please find my resume attached for your reference.

Looking forward to hearing from you.

Thanks & Regards,
{sender_name}""",
        },
    ]
}


def get_role_templates() -> dict:
    data = _read(TEMPLATES_FILE, None)
    if not data:
        data = DEFAULT_ROLE_TEMPLATES
        _write(TEMPLATES_FILE, data)
    return data


def save_role_templates(data: dict) -> dict:
    _write(TEMPLATES_FILE, data)
    return data


def pick_template_for_role(role: str | None, templates: dict | None = None) -> dict | None:
    templates = templates or get_role_templates()
    role_l = (role or "").lower()
    best = None
    best_score = 0
    for t in templates.get("templates", []):
        keywords = t.get("role_keywords") or []
        if not keywords:
            continue
        score = sum(1 for kw in keywords if kw.lower() in role_l)
        if score > best_score:
            best_score = score
            best = t
    return best


# ---------- Scheduler ----------

DEFAULT_SCHEDULER = {
    "enabled": False,
    "hour": 9,
    "minute": 0,
    "timezone_note": "Uses server local time",
    "time_period": "day",
    "experience_range": "2-4",
    "roles": [
        "Java Developer",
        "Java Full Stack Developer",
        "Java Backend Engineer",
        "Software Engineer",
        "Backend Engineer",
    ],
    "auto_import": True,
    "auto_generate": True,
    "last_run_at": None,
    "last_run_summary": None,
}


def get_scheduler_config() -> dict:
    data = _read(SCHEDULER_FILE, None)
    if not data:
        data = DEFAULT_SCHEDULER.copy()
        _write(SCHEDULER_FILE, data)
    return data


def save_scheduler_config(data: dict) -> dict:
    current = get_scheduler_config()
    current.update(data)
    _write(SCHEDULER_FILE, current)
    return current
