from flask import request

BASE_URL = "https://kyrylobublii.com"
DEFAULT_OG_IMAGE = f"{BASE_URL}/static/images/og-default.jpg"


def canonical_url(path=""):
    return f"{BASE_URL}{path}"


def page_meta(title, description, image=None):
    return {
        "title": title,
        "description": description,
        "og_image": image or DEFAULT_OG_IMAGE,
    }


def inject_seo():
    """Flask context processor — injects canonical URL and BASE_URL into every template."""
    return {
        "canonical": canonical_url(request.path),
        "BASE_URL": BASE_URL,
    }
