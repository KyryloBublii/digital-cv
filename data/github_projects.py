import os
import re
import time
import base64
import logging

import requests
import markdown as md_lib

GITHUB_USERNAME = os.environ["GITHUB_USERNAME"]
CACHE_TTL = 3600

_cache: dict = {"data": None, "ts": 0.0}

_API = "https://api.github.com"
_HEADERS: dict = {"Accept": "application/vnd.github+json"}
if os.environ.get("GITHUB_TOKEN"):
    _HEADERS["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter block. Returns (fields_dict, body_str)."""
    text = _normalize(text)
    if not text.startswith("---\n"):
        return {}, text

    close = text.find("\n---", 4)
    if close == -1:
        return {}, text

    fm_block = text[4:close]
    body = text[close + 4:].lstrip("\n")

    fields: dict = {}
    lines = fm_block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or ":" not in line:
            i += 1
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()

        if val.startswith("[") and val.endswith("]"):
            # inline list: [a, b, c]
            fields[key] = [x.strip().strip("\"'") for x in val[1:-1].split(",") if x.strip()]
        elif val == "":
            # block list: look-ahead for "- item" lines
            items = []
            j = i + 1
            while j < len(lines) and re.match(r"^\s*-\s+", lines[j]):
                items.append(re.sub(r"^\s*-\s+", "", lines[j]).strip())
                j += 1
            if items:
                fields[key] = items
                i = j
                continue
            else:
                fields[key] = ""
        else:
            fields[key] = val
        i += 1

    return fields, body


def _extract_description(body: str) -> str:
    """First paragraph of '## What is it' section, or first non-heading paragraph."""
    match = re.search(
        r"^##\s+What is it\b[^\n]*\n([\s\S]*?)(?=\n##|\Z)",
        body,
        re.MULTILINE,
    )
    source = match.group(1) if match else body

    for block in source.split("\n\n"):
        block = block.strip()
        if not block or block.startswith("#"):
            continue
        block = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", block)
        block = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", block)
        block = re.sub(r"[*_`]", "", block)
        block = re.sub(r"^[-*+]\s+", "", block, flags=re.MULTILINE)
        block = " ".join(block.split())
        if block:
            return block
    return ""


def _get(url: str) -> "requests.Response | None":
    try:
        r = requests.get(url, headers=_HEADERS, timeout=10)
        return r if r.status_code == 200 else None
    except requests.RequestException as exc:
        logging.warning("GET %s failed: %s", url, exc)
        return None


def _fetch_readme(username: str, repo: str) -> "str | None":
    r = _get(f"{_API}/repos/{username}/{repo}/contents/README.md")
    if r is None:
        return None
    data = r.json()
    if data.get("encoding") == "base64":
        return base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
    dl = data.get("download_url")
    if dl:
        r2 = _get(dl)
        return r2.text if r2 else None
    return None


def _fetch_photos(username: str, repo: str) -> "tuple[str | None, list[str]]":
    r = _get(f"{_API}/repos/{username}/{repo}/contents/proj_photo")
    if r is None:
        return None, []
    files = r.json()
    if not isinstance(files, list):
        return None, []
    photos = [
        f["download_url"]
        for f in files
        if f.get("type") == "file" and f.get("download_url")
    ]
    return (photos[0] if photos else None), photos


def _to_status(raw: str) -> str:
    raw = raw.lower().strip()
    if raw in ("live", "completed"):
        return "live"
    if raw in ("in-progress", "wip", "in_progress"):
        return "wip"
    return raw


def _build_projects() -> list[dict]:
    r = requests.get(
        f"{_API}/users/{GITHUB_USERNAME}/repos",
        headers=_HEADERS,
        params={"type": "public", "per_page": 100, "sort": "pushed"},
        timeout=15,
    )
    r.raise_for_status()
    repos: list[dict] = r.json()

    # Top 3 repos by star count are featured
    top3 = {
        name
        for name, _ in sorted(
            ((repo["name"], repo.get("stargazers_count", 0)) for repo in repos),
            key=lambda x: x[1],
            reverse=True,
        )[:3]
    }

    projects = []
    for repo in repos:
        name: str = repo["name"]

        readme_raw = _fetch_readme(GITHUB_USERNAME, name)
        if readme_raw is None:
            continue

        fields, body = _parse_frontmatter(readme_raw)
        if not fields.get("title"):
            continue

        readme_html = md_lib.markdown(body, extensions=["tables", "fenced_code"])
        description = _extract_description(body)
        screenshot, photos = _fetch_photos(GITHUB_USERNAME, name)

        projects.append({
            "slug":        name,
            "title":       fields["title"],
            "year":        str(fields.get("year", "")),
            "status":      _to_status(fields.get("status", "live")),
            "tags":        fields.get("tags") or [],
            "description": description,
            "readme_md":   body,
            "readme_html": readme_html,
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
