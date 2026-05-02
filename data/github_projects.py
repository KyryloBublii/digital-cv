import logging
import time

import markdown as md_lib

from data.github_client import (
    GITHUB_USERNAME,
    fetch_photos,
    fetch_readme,
    fetch_repos,
)
from data.readme_parser import extract_description, parse_frontmatter

CACHE_TTL = 3600

_cache: dict = {"data": None, "ts": 0.0}


def _to_status(raw: str) -> str:
    raw = raw.lower().strip()
    if raw in ("live", "completed"):
        return "live"
    if raw in ("in-progress", "wip", "in_progress"):
        return "wip"
    return raw


def _featured_repos(repos: list[dict]) -> set[str]:
    """Return names of the top-3 repos by star count."""
    return {
        name
        for name, _ in sorted(
            ((r["name"], r.get("stargazers_count", 0)) for r in repos),
            key=lambda x: x[1],
            reverse=True,
        )[:3]
    }


def _build_projects() -> list[dict]:
    repos = fetch_repos(GITHUB_USERNAME)
    top3 = _featured_repos(repos)
    projects = []

    for repo in repos:
        name: str = repo["name"]

        readme_raw = fetch_readme(GITHUB_USERNAME, name)
        if readme_raw is None:
            continue

        fields, body = parse_frontmatter(readme_raw)
        if not fields.get("title"):
            continue

        screenshot, photos = fetch_photos(GITHUB_USERNAME, name)

        projects.append({
            "slug":        name,
            "title":       fields["title"],
            "year":        str(fields.get("year", "")),
            "status":      _to_status(fields.get("status", "live")),
            "tags":        fields.get("tags") or [],
            "description": extract_description(body),
            "readme_html": md_lib.markdown(body, extensions=["tables", "fenced_code"]),
            "screenshot":  screenshot,
            "photos":      photos,
            "github_url":  repo.get("html_url", ""),
            "live_url":    repo.get("homepage") or "",
            "featured":    name in top3,
        })

    return projects


def get_projects() -> list[dict]:
    """Return cached project list, refreshing every CACHE_TTL seconds."""
    now = time.time()
    if _cache["data"] is not None and now - _cache["ts"] < CACHE_TTL:
        return _cache["data"]
    try:
        data = _build_projects()
        _cache.update({"data": data, "ts": now})
        return data
    except Exception as exc:
        logging.error("Failed to fetch GitHub projects: %s", exc)
        if _cache["data"] is not None:
            return _cache["data"]
        raise
