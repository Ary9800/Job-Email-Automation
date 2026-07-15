"""Fetch public LinkedIn post pages and pull recruiter email / job text."""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import urlparse

import httpx

from app.services.extractor import _extract_emails_from_text, _is_valid_recruiter_email

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_RE = re.compile(r"<script[^>]*>[\s\S]*?</script>", re.I)
STYLE_RE = re.compile(r"<style[^>]*>[\s\S]*?</style>", re.I)
WS_RE = re.compile(r"\s+")


def is_linkedin_url(url: str) -> bool:
    if not url:
        return False
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return "linkedin.com" in host


def _html_to_text(html: str) -> str:
    html = SCRIPT_RE.sub(" ", html)
    html = STYLE_RE.sub(" ", html)
    text = TAG_RE.sub(" ", html)
    text = unescape(text)
    text = WS_RE.sub(" ", text)
    return text.strip()


async def fetch_post_page(url: str) -> dict:
    """
    Attempt to load a public LinkedIn post URL and extract text + email.
    LinkedIn often returns a login wall — still try snippets in the HTML.
    """
    if not is_linkedin_url(url):
        return {
            "ok": False,
            "url": url,
            "text": "",
            "emails": [],
            "recruiter_email": None,
            "error": "Not a LinkedIn URL",
        }

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=25.0) as client:
            resp = await client.get(url, headers=headers)
            html = resp.text or ""
            status = resp.status_code
    except Exception as e:
        return {
            "ok": False,
            "url": url,
            "text": "",
            "emails": [],
            "recruiter_email": None,
            "error": f"Fetch failed: {e}",
        }

    text = _html_to_text(html)

    # LinkedIn sometimes embeds content in JSON in the HTML
    emails = _extract_emails_from_text(text)
    # Also search raw HTML for mailto / email patterns
    for match in re.finditer(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
        html,
    ):
        em = match.group(0).rstrip(".,;:")
        if _is_valid_recruiter_email(em) and em not in emails:
            emails.append(em)

    emails = [e for e in emails if _is_valid_recruiter_email(e)]
    primary = emails[0] if emails else None

    wall = any(
        phrase in text.lower()
        for phrase in ("sign in", "join linkedin", "agree & join", "authwall")
    )

    return {
        "ok": bool(primary) or (len(text) > 200 and not wall),
        "url": url,
        "status_code": status,
        "text": text[:4000],
        "emails": emails,
        "recruiter_email": primary,
        "login_wall": wall and not primary,
        "error": None if primary else (
            "LinkedIn login wall — paste post text instead" if wall else None
        ),
    }
