import asyncio
import re
from urllib.parse import urlparse

from app.services.extractor import EMAIL_PATTERN, _extract_emails_from_text, _is_valid_recruiter_email
from app.services.job_normalizer import (
    clean_company,
    detect_role_from_text,
    extract_experience,
    normalize_extracted,
)

DEFAULT_ROLES = [
    "Java Backend Engineer",
    "Java Backend Developer",
    "Java Full Stack Developer",
    "Java Software Engineer",
    "Java Developer",
    "Software Engineer",
    "Backend Engineer",
]

HR_KEYWORDS = [
    "hr ",
    " hr",
    "recruiter",
    "talent acquisition",
    " ta ",
    "hiring for",
    "we're hiring",
    "we are hiring",
    "we have an opening",
    "openings at",
    "share your resume",
    "share your cv",
    "share resume",
    "send resume",
    "send your resume",
    "drop your resume",
    "interested candidates",
    "immediate joining",
    "walk-in",
    "walk in",
    "open position",
    "job opening",
    "join our team",
    "apply at",
    "mail your resume",
]

# Posts from candidates looking for work — exclude these
JOB_SEEKER_KEYWORDS = [
    "looking for job",
    "looking for a job",
    "looking for opportunity",
    "looking for opportunities",
    "looking for role",
    "looking for a role",
    "seeking job",
    "seeking a job",
    "seeking opportunity",
    "seeking opportunities",
    "seeking role",
    "open to work",
    "#opentowork",
    "open for work",
    "open to opportunities",
    "open for opportunities",
    "actively looking",
    "job search",
    "searching for job",
    "need a job",
    "please refer me",
    "refer me for",
    "help me find",
    "i am looking",
    "i'm looking",
    "im looking",
    "i am seeking",
    "i'm seeking",
    "available for opportunity",
    "open to new role",
    "open to new opportunity",
    "#jobseeker",
    "#lookingforjob",
    "if anyone is hiring me",
    "anyone hiring me",
    "resume attached for your reference",  # candidate sharing own resume
    "please find my resume",
    "kindly refer",
]

INDIA_KEYWORDS = [
    "india",
    "indian",
    "bangalore",
    "bengaluru",
    "pune",
    "hyderabad",
    "mumbai",
    "chennai",
    "noida",
    "gurgaon",
    "gurugram",
    "delhi",
    "kolkata",
    "ahmedabad",
    "jaipur",
    "kochi",
    "coimbatore",
    "chandigarh",
    "indore",
    "pan india",
    "work from india",
    "remote india",
    "wfh india",
    ".in",
]

FOREIGN_LOCATION_KEYWORDS = [
    "usa",
    "u.s.a",
    "united states",
    " us ",
    " us,",
    " us.",
    "uk ",
    "united kingdom",
    "london",
    "canada",
    "toronto",
    "chicago",
    "new york",
    "nyc",
    "california",
    "texas",
    "florida",
    "seattle",
    "boston",
    "dallas",
    "austin",
    "san francisco",
    "bay area",
    "onsite only",
    "locals to",
    "need locals",
    "must be in us",
    "us citizen",
    "green card",
    "h1b only",
    "europe",
    "germany",
    "singapore",
    "dubai",
    "australia",
    "sydney",
]

EXPERIENCE_IN_RANGE = [
    re.compile(r"2\s*[-–to]+\s*4\s*years?", re.I),
    re.compile(r"2\s*to\s*4\s*years?", re.I),
    re.compile(r"2\s*[-–]\s*4\s*years?", re.I),
    re.compile(r"3\+\s*years?", re.I),
    re.compile(r"2\+\s*years?", re.I),
    re.compile(r"1\s*[-–to]+\s*3\s*years?", re.I),
    re.compile(r"experience\s*:\s*2", re.I),
]

# UI experience filter → search phrases + post-match patterns
EXPERIENCE_RANGES: dict[str, dict] = {
    "any": {
        "query": "",
        "patterns": [],
    },
    "2+": {
        "query": '("2+ years" OR "2 years" OR "2 to 4 years" OR "2-4 years")',
        "patterns": [
            re.compile(r"2\+", re.I),
            re.compile(r"2\s*years?", re.I),
            re.compile(r"2\s*[-–to]+\s*[345]\s*years?", re.I),
        ],
    },
    "2-3": {
        "query": '("2 to 3 years" OR "2-3 years" OR "2 – 3 years")',
        "patterns": [
            re.compile(r"2\s*[-–to]+\s*3\s*years?", re.I),
            re.compile(r"2\s*[-–]\s*3", re.I),
        ],
    },
    "2-4": {
        "query": '("2 to 4 years" OR "2-4 years" OR "2 – 4 years" OR "2+ years" OR "3+ years")',
        "patterns": [
            re.compile(r"2\s*[-–to]+\s*4\s*years?", re.I),
            re.compile(r"2\s*[-–]\s*4", re.I),
            re.compile(r"2\+\s*years?", re.I),
            re.compile(r"3\+\s*years?", re.I),
            re.compile(r"2\s*to\s*4", re.I),
        ],
    },
    "3+": {
        "query": '("3+ years" OR "3 years" OR "3 to 5 years" OR "3-5 years")',
        "patterns": [
            re.compile(r"3\+", re.I),
            re.compile(r"3\s*years?", re.I),
            re.compile(r"3\s*[-–to]+\s*[456]\s*years?", re.I),
        ],
    },
    "3-5": {
        "query": '("3 to 5 years" OR "3-5 years" OR "3 – 5 years")',
        "patterns": [
            re.compile(r"3\s*[-–to]+\s*5\s*years?", re.I),
            re.compile(r"3\s*[-–]\s*5", re.I),
        ],
    },
}


def _normalize_experience_range(value: str | None) -> str:
    v = (value or "2-4").strip().lower().replace(" ", "")
    aliases = {
        "any": "any",
        "all": "any",
        "2+": "2+",
        "2plus": "2+",
        "2-3": "2-3",
        "2to3": "2-3",
        "2-4": "2-4",
        "2to4": "2-4",
        "3+": "3+",
        "3plus": "3+",
        "3-5": "3-5",
        "3to5": "3-5",
    }
    return aliases.get(v, "2-4")


def _matches_experience_range(text: str, experience_range: str) -> bool:
    """If range is 'any', always pass. If post has no experience text, allow through."""
    period = _normalize_experience_range(experience_range)
    if period == "any":
        return True

    cfg = EXPERIENCE_RANGES.get(period) or EXPERIENCE_RANGES["2-4"]
    patterns = cfg["patterns"]
    if not patterns:
        return True

    # Soft: if text mentions any years figure, require match; else allow (often missing in snippets)
    has_any_years = bool(re.search(r"\d+\s*(\+|to|[-–])?\s*\d*\s*years?", text, re.I))
    if not has_any_years:
        return True
    return any(p.search(text) for p in patterns)


def _is_linkedin_post_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url.lower())
    if "linkedin.com" not in parsed.netloc:
        return False
    path = parsed.path
    return any(
        part in path
        for part in ("/posts/", "/feed/update", "/pulse/")
    )


def _detect_role(text: str, roles: list[str]) -> str | None:
    return detect_role_from_text(text, allowed=roles)


def _has_hr_signal(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in HR_KEYWORDS)


def _has_strong_hiring_signal(text: str) -> bool:
    """Recruiter actively hiring — not just #hiring hashtag on a job-seeker post."""
    text_lower = text.lower()
    strong = [
        "we're hiring",
        "we are hiring",
        "hiring for",
        "share your resume",
        "share your cv",
        "share resume",
        "send resume",
        "send your resume",
        "drop your resume",
        "interested candidates",
        "apply at",
        "mail your resume",
        "openings at",
        "join our team",
        "walk-in interview",
        "walk in interview",
        "job opening at",
        "opening for",
    ]
    return any(kw in text_lower for kw in strong)


def _is_job_seeker_post(text: str) -> bool:
    text_lower = text.lower()
    if any(kw in text_lower for kw in JOB_SEEKER_KEYWORDS):
        return True
    # "I have X years" + looking pattern = candidate post
    if re.search(r"\bi\s*(?:am|'m)\s+(?:a\s+)?(?:java|software|backend|full[\s-]?stack)", text_lower):
        if re.search(r"looking|seeking|open to|opportunit", text_lower):
            return True
    # "#hiring" only in title with no recruiter signals
    if re.search(r"#\s*hiring", text_lower) and not _has_strong_hiring_signal(text):
        if re.search(r"looking|seeking|open to work|opentowork", text_lower):
            return True
    return False


def _has_india_signal(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in INDIA_KEYWORDS)


def _is_foreign_post(text: str) -> bool:
    text_lower = f" {text.lower()} "
    return any(kw in text_lower for kw in FOREIGN_LOCATION_KEYWORDS)


def _is_india_eligible(text: str) -> bool:
    """Keep India posts; drop clearly foreign ones."""
    if _is_foreign_post(text):
        return False
    if _has_india_signal(text):
        return True
    # No location mentioned — allow only if strong recruiter hiring post
    return _has_strong_hiring_signal(text) and _has_hr_signal(text)


def _has_experience_match(text: str) -> bool:
    return any(p.search(text) for p in EXPERIENCE_IN_RANGE)


def _extract_company(text: str, email: str | None) -> str | None:
    return clean_company(None, email, text)


def _extract_poster_name(title: str, snippet: str) -> str | None:
    for text in (title, snippet):
        m = re.search(r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text.strip())
        if m:
            name = m.group(1).strip()
            if name.lower() not in ("linkedin", "java", "hiring", "we"):
                return name
    return None


def _score_post(text: str, role: str | None, email: str | None) -> float:
    score = 0.0
    if role:
        score += 0.2
    if _has_strong_hiring_signal(text):
        score += 0.25
    elif _has_hr_signal(text):
        score += 0.1
    if _has_india_signal(text):
        score += 0.2
    if _has_experience_match(text):
        score += 0.15
    if email:
        score += 0.2
    if "java" in text.lower():
        score += 0.05
    return min(score, 1.0)


def _parse_search_result(
    item: dict,
    roles: list[str],
    experience_range: str = "2-4",
) -> dict | None:
    url = item.get("href") or item.get("link") or item.get("url") or ""
    title = item.get("title") or ""
    snippet = item.get("body") or item.get("snippet") or ""
    combined = f"{title}\n{snippet}"

    if not _is_linkedin_post_url(url):
        return None

    role = _detect_role(combined, roles)
    if not role:
        return None

    if _is_job_seeker_post(combined):
        return None

    if not _is_india_eligible(combined):
        return None

    if not (_has_strong_hiring_signal(combined) or (_has_hr_signal(combined) and _has_experience_match(combined))):
        return None

    if not _matches_experience_range(combined, experience_range):
        return None

    emails = _extract_emails_from_text(combined)
    email = emails[0] if emails else None
    if email and not _is_valid_recruiter_email(email):
        email = None

    exp = extract_experience(combined)
    company = _extract_company(combined, email)
    poster = _extract_poster_name(title, snippet)
    score = _score_post(combined, role, email)

    normalized = normalize_extracted({
        "role": role,
        "company": company,
        "recruiter_email": email,
        "recruiter_name": poster,
        "experience_required": exp,
        "job_description": snippet[:500] if snippet else None,
        "source_platform": "LinkedIn",
        "content_summary": snippet[:300] if snippet else title,
        "confidence": score,
        "raw_text": combined[:800],
    })

    return {
        "id": re.sub(r"[^a-zA-Z0-9]", "", url)[-16:] or str(abs(hash(url))),
        "url": url,
        "title": title.strip(),
        "snippet": snippet.strip(),
        "role": normalized.get("role"),
        "company": normalized.get("company"),
        "recruiter_email": normalized.get("recruiter_email"),
        "recruiter_name": normalized.get("recruiter_name"),
        "experience_required": normalized.get("experience_required"),
        "score": score,
        "has_email": bool(email),
        "is_hr_post": _has_hr_signal(combined),
    }


TIME_PERIOD_MAP = {
    "day": "d",
    "week": "w",
    "month": "m",
}


def _normalize_time_period(time_period: str | None) -> str:
    period = (time_period or "week").strip().lower()
    if period in ("1d", "past_day", "d", "1 day", "past 1 day"):
        return "day"
    if period in ("1w", "past_week", "w", "1 week", "past 1 week"):
        return "week"
    if period in ("1m", "past_month", "m", "1 month", "past 1 month"):
        return "month"
    if period in TIME_PERIOD_MAP:
        return period
    return "week"


def _build_queries(roles: list[str], experience_range: str = "2-4") -> list[str]:
    india = '("India" OR Bangalore OR Pune OR Hyderabad OR Mumbai OR Chennai OR Noida OR Gurgaon)'
    hiring = '("hiring" OR "share your resume" OR "we are hiring" OR recruiter OR "talent acquisition")'
    period = _normalize_experience_range(experience_range)
    exp_q = (EXPERIENCE_RANGES.get(period) or EXPERIENCE_RANGES["2-4"])["query"]

    queries = []
    for role in roles:
        if exp_q:
            queries.append(f'site:linkedin.com/posts "{role}" {india} {exp_q} {hiring}')
        else:
            queries.append(f'site:linkedin.com/posts "{role}" {india} {hiring}')
        queries.append(f'site:linkedin.com/posts {role} India hiring "share resume" recruiter')
        queries.append(
            f'site:linkedin.com/posts "{role}" Bangalore OR Pune hiring "interested candidates"'
        )
    return queries


def _search_sync(
    roles: list[str],
    max_results_per_query: int,
    time_period: str = "week",
    experience_range: str = "2-4",
) -> list[dict]:
    from app.services.search_providers import search_web

    period = _normalize_time_period(time_period)
    timelimit = TIME_PERIOD_MAP[period]
    exp_range = _normalize_experience_range(experience_range)

    seen_urls: set[str] = set()
    parsed: list[dict] = []
    providers_used: set[str] = set()

    for query in _build_queries(roles, exp_range):
        try:
            results, provider = search_web(
                query,
                max_results=max_results_per_query,
                timelimit=timelimit,
            )
            providers_used.add(provider)
        except Exception:
            continue

        for item in results:
            url = item.get("href") or item.get("link") or ""
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            post = _parse_search_result(item, roles, exp_range)
            if post:
                post["time_period"] = period
                post["provider"] = provider
                parsed.append(post)

    parsed.sort(key=lambda p: p["score"], reverse=True)
    # Attach provider info on first item for response metadata (router may ignore)
    if parsed:
        parsed[0]["_providers"] = sorted(providers_used)
    return parsed


async def search_linkedin_posts(
    roles: list[str] | None = None,
    max_results: int = 30,
    time_period: str = "week",
    experience_range: str = "2-4",
) -> list[dict]:
    roles = roles or DEFAULT_ROLES
    period = _normalize_time_period(time_period)
    exp_range = _normalize_experience_range(experience_range)
    per_query = max(5, max_results // max(len(roles), 1))
    return await asyncio.to_thread(_search_sync, roles, per_query, period, exp_range)


def parse_pasted_post(text: str, url: str | None = None) -> dict:
    """Parse pasted LinkedIn post text (and optional URL) into structured fields."""
    combined = (text or "").strip()
    link = (url or "").strip()

    if not link and combined.startswith("http") and "linkedin.com" in combined.split()[0]:
        link = combined.split()[0]
        combined = combined[len(link):].strip()

    emails = _extract_emails_from_text(combined)
    email = emails[0] if emails else None
    if email and not _is_valid_recruiter_email(email):
        email = None

    role = detect_role_from_text(combined) or "Java Developer"
    exp = extract_experience(combined)
    company = _extract_company(combined, email)
    poster = _extract_poster_name(combined[:80], combined)
    score = _score_post(combined, role, email)

    normalized = normalize_extracted({
        "role": role,
        "company": company,
        "recruiter_email": email,
        "recruiter_name": poster,
        "experience_required": exp,
        "job_description": combined[:500] if combined else None,
        "source_platform": "LinkedIn",
        "content_summary": combined[:300] if combined else None,
        "confidence": score if combined else 0.3,
        "raw_text": combined[:800],
    })

    post_id = re.sub(r"[^a-zA-Z0-9]", "", link or combined)[-16:] or str(abs(hash(combined or link)))
    return {
        "id": post_id,
        "url": link,
        "title": (combined[:80] + "…") if len(combined) > 80 else (combined or link or "Pasted post"),
        "snippet": combined,
        "role": normalized.get("role"),
        "company": normalized.get("company"),
        "recruiter_email": normalized.get("recruiter_email"),
        "recruiter_name": normalized.get("recruiter_name"),
        "experience_required": normalized.get("experience_required"),
        "score": score,
        "has_email": bool(normalized.get("recruiter_email")),
        "is_hr_post": _has_hr_signal(combined) if combined else False,
    }

