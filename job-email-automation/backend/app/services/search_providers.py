"""Optional search backends: SerpAPI (preferred when configured) → DuckDuckGo (ddgs)."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


def search_web(query: str, *, max_results: int = 8, timelimit: str = "w") -> tuple[list[dict[str, Any]], str]:
    """
    Returns (results, provider_name).
    Each result dict has: title, href/link, body/snippet.
    timelimit: d | w | m (DuckDuckGo style).
    """
    if settings.serpapi_api_key:
        try:
            results = _serpapi_search(query, max_results=max_results, timelimit=timelimit)
            if results:
                return results, "serpapi"
        except Exception:
            pass  # fall through to ddgs

    results = _ddgs_search(query, max_results=max_results, timelimit=timelimit)
    return results, "ddgs"


def _serpapi_tbs(timelimit: str) -> str | None:
    # Google tbs: qdr:d / qdr:w / qdr:m
    mapping = {"d": "qdr:d", "w": "qdr:w", "m": "qdr:m"}
    return mapping.get(timelimit)


def _serpapi_search(query: str, *, max_results: int, timelimit: str) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "engine": "google",
        "q": query,
        "api_key": settings.serpapi_api_key,
        "num": min(max_results, 20),
        "hl": "en",
        "gl": "in",  # India-biased results
    }
    tbs = _serpapi_tbs(timelimit)
    if tbs:
        params["tbs"] = tbs

    with httpx.Client(timeout=30.0) as client:
        resp = client.get("https://serpapi.com/search.json", params=params)
        resp.raise_for_status()
        data = resp.json()

    organic = data.get("organic_results") or []
    out: list[dict[str, Any]] = []
    for item in organic[:max_results]:
        link = item.get("link") or ""
        out.append({
            "title": item.get("title") or "",
            "href": link,
            "link": link,
            "body": item.get("snippet") or "",
            "snippet": item.get("snippet") or "",
        })
    return out


def _ddgs_search(query: str, *, max_results: int, timelimit: str) -> list[dict[str, Any]]:
    from ddgs import DDGS

    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results, timelimit=timelimit))
    except Exception:
        return []
