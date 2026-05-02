import json
import logging
import os
import time
from pathlib import Path

import requests

CACHE_TTL = 86400  # 24 hours

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


def get_profile() -> dict:
    """Return profile data, refreshing from GitHub at most once per CACHE_TTL.
    Uses a file-based cache — persists across restarts, shared across workers."""
    cached = _read_cache()
    if cached is not None:
        return cached
    try:
        data = _fetch_remote()
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
