import base64
import logging
import os

import requests

GITHUB_USERNAME = os.environ["GITHUB_USERNAME"]

_API = "https://api.github.com"
_HEADERS: dict = {"Accept": "application/vnd.github+json"}
if os.environ.get("GITHUB_TOKEN"):
    _HEADERS["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"


def _get(url: str) -> requests.Response | None:
    try:
        r = requests.get(url, headers=_HEADERS, timeout=10)
        return r if r.status_code == 200 else None
    except requests.RequestException as exc:
        logging.warning("GET %s failed: %s", url, exc)
        return None


def fetch_repos(username: str) -> list[dict]:
    r = requests.get(
        f"{_API}/users/{username}/repos",
        headers=_HEADERS,
        params={"type": "public", "per_page": 100, "sort": "pushed"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def fetch_readme(username: str, repo: str) -> str | None:
    r = _get(f"{_API}/repos/{username}/{repo}/contents/README.md")
    if r is None:
        return None

    data = r.json()
    if data.get("encoding") == "base64":
        return base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")

    download_url = data.get("download_url")
    if download_url:
        r2 = _get(download_url)
        return r2.text if r2 else None

    return None


def fetch_photos(username: str, repo: str) -> tuple[str | None, list[str]]:
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
