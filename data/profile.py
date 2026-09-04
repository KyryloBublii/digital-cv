import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

import requests

CACHE_TTL = 86400  # 24 hours

# Credly badge URLs carry the assertion UUID, and Credly serves the issue date
# for it as public Open Badges JSON — no auth, no API key.
_CREDLY_ID  = re.compile(r"credly\.com/badges/([0-9a-fA-F-]{36})")
_CREDLY_API = "https://www.credly.com/api/v1/obi/v2/badge_assertions/{}"

_REPO       = os.environ.get("GITHUB_PORTFOLIO_DATA_REPO", "KyryloBublii/portfolio-data")
_FILE       = "profile.json"
_RAW        = f"https://raw.githubusercontent.com/{_REPO}/main/{_FILE}"
_LOCAL      = Path(__file__).parent / _FILE
_CACHE_FILE = Path(__file__).parent / ".profile_cache.json"


def _fetch_remote() -> dict:
    headers = {}
    token = os.environ.get("GITHUB_PORTFOLIO_DATA_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(_RAW, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


def _read_cache() -> dict | None:
    """Return cached data if file exists and is fresher than CACHE_TTL, else None."""
    if not _CACHE_FILE.exists():
        return None
    if time.time() - _CACHE_FILE.stat().st_mtime > CACHE_TTL:
        return None
    try:
        return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_cache(data: dict) -> None:
    try:
        _CACHE_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception as exc:
        logging.warning("Could not write profile cache: %s", exc)


def _credly_issue_date(url: str) -> str | None:
    """Return a Credly badge's issue date as e.g. "August 2026", or None."""
    match = _CREDLY_ID.search(url or "")
    if not match:
        return None
    try:
        r = requests.get(_CREDLY_API.format(match.group(1)), timeout=5)
        r.raise_for_status()
        issued = r.json().get("issuedOn")
        if not issued:
            return None
        return datetime.fromisoformat(issued.replace("Z", "+00:00")).strftime("%B %Y")
    except Exception as exc:
        logging.warning("Credly lookup failed for %s: %s", url, exc)
        return None


def _fill_credly_dates(data: dict) -> None:
    """Fill in missing certification dates from Credly, in place.

    Only runs on a cache miss (once per CACHE_TTL), only for entries that have a
    Credly URL and no date of their own — a date written in profile.json always
    wins. A lookup that fails leaves the date empty and the page renders "—".
    """
    for cert in data.get("certifications") or []:
        if cert.get("date") or "credly.com" not in (cert.get("url") or ""):
            continue
        date = _credly_issue_date(cert["url"])
        if date:
            cert["date"] = date
            logging.info("Filled %s date from Credly: %s", cert.get("name"), date)


def get_profile() -> dict:
    """Return profile data, refreshing from GitHub at most once per CACHE_TTL.
    Uses a file-based cache — persists across restarts, shared across workers."""
    cached = _read_cache()
    if cached is not None:
        return cached
    try:
        data = _fetch_remote()
        _fill_credly_dates(data)
        _write_cache(data)
        return data
    except Exception as exc:
        logging.warning("Remote profile fetch failed, using local fallback: %s", exc)
        if _CACHE_FILE.exists():
            try:
                return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return json.loads(_LOCAL.read_text(encoding="utf-8"))
