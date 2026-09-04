import logging
import os
from datetime import date

import resend
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request, Response, make_response, redirect, url_for
from data.profile import get_profile
from seo_helpers import inject_seo

load_dotenv()

app = Flask(__name__)
_secret_key = os.environ.get("SECRET_KEY")
if not _secret_key:
    raise RuntimeError("SECRET_KEY environment variable is not set")
app.secret_key = _secret_key
app.context_processor(inject_seo)


def _static_exists(filename: str) -> bool:
    """True when a file exists under static/.

    Used by the picture() macro: a <source> pointing at a missing file is NOT
    skipped by the browser — it wins the type match, 404s, and the <img>
    fallback never runs, leaving a broken image.
    """
    return os.path.isfile(os.path.join(app.static_folder, filename))


app.jinja_env.globals["static_exists"] = _static_exists


def _to_bullets(value):
    """Return a description as a list of bullet strings, or None for prose.

    Accepts either a JSON array in profile.json, or a plain string whose lines
    start with "-", "–" or "•" — so a list pasted straight from a CV renders as
    a real <ul> instead of one run-on paragraph.
    """
    if isinstance(value, (list, tuple)):
        items = [str(v).strip().lstrip("-–•").strip() for v in value]
    elif isinstance(value, str):
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        if not lines or not all(line.startswith(("-", "–", "•")) for line in lines):
            return None
        items = [line.lstrip("-–•").strip() for line in lines]
    else:
        return None
    return [item for item in items if item] or None


app.jinja_env.filters["bullets"] = _to_bullets


@app.context_processor
def inject_asset_version():
    """Cache-busting token for /static/ URLs.

    nginx.conf serves static assets as `public, immutable` for a year, so an
    edited CSS file keeps its old URL and browsers never re-fetch it. Keying
    the URL on the file's mtime gives each edit a fresh URL.
    """
    try:
        stamp = int(os.path.getmtime(os.path.join(app.static_folder, "css", "custom.css")))
    except OSError:
        stamp = 0
    return {"asset_v": str(stamp)}


def _get_projects() -> list[dict]:
    try:
        from data.github_projects import get_projects
        return get_projects()
    except Exception as exc:
        logging.warning("GitHub fetch failed, using fallback: %s", exc)
        from data.projects import PROJECTS
        return PROJECTS


def _verify_turnstile(token: str) -> bool:
    secret = os.environ.get("TURNSTILE_SECRET", "")
    if not secret:
        return True
    try:
        r = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": secret, "response": token},
            timeout=5,
        )
        return r.json().get("success", False)
    except Exception as exc:
        logging.error("Turnstile verification failed: %s", exc)
        return False


def _send_contact_email(name: str, sender_email: str, message: str) -> None:
    resend.api_key = os.environ["RESEND_API_KEY"]

    resend.Emails.send({
        "from":     os.environ["MAIL_FROM"],
        "to":       [os.environ["MAIL_RECIPIENT"]],
        "subject":  f"Portfolio contact from {name}",
        "text":     f"Name:    {name}\nEmail:   {sender_email}\n\n{message}",
        "reply_to": sender_email,
    })


@app.route("/")
def index():
    all_projects = _get_projects()
    featured = [p for p in all_projects if p.get("featured")]
    return render_template("index.html", active_page="home", featured=featured, projects=all_projects)


@app.route("/projects")
def projects():
    all_projects = _get_projects()
    all_tags = sorted({tag for p in all_projects for tag in p.get("tags", [])})
    return render_template("projects.html", active_page="projects", projects=all_projects, all_tags=all_tags)


@app.route("/projects/<slug>")
def project_detail(slug):
    all_projects = _get_projects()
    project = next((p for p in all_projects if p.get("slug") == slug), None)
    if project is None:
        return render_template("404.html"), 404
    return render_template(
        "project_detail.html",
        active_page="projects",
        project=project,
        readme_html=project.get("readme_html", ""),
    )


@app.route("/about")
def about():
    profile = get_profile()
    return render_template(
        "about.html",
        active_page="about",
        profile=profile,
        skills=profile.get("skills") if isinstance(profile.get("skills"), dict) else {"Skills": profile.get("skills", [])},
        experience=profile.get("experience", []),
        education=profile.get("education", []),
        certifications=profile.get("certifications", []),
    )


@app.route("/contact", methods=["GET", "POST"])
def contact():
    sent = False
    error = False
    if request.method == "POST":
        name    = request.form.get("name", "").strip()
        email   = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()
        token   = request.form.get("cf-turnstile-response", "")
        if name and email and message and _verify_turnstile(token):
            try:
                _send_contact_email(name, email, message)
                sent = True
            except Exception as exc:
                logging.error("Contact form failed: %s", exc)
                error = True
        else:
            error = True
    return render_template(
        "contact.html",
        active_page="contact",
        sent=sent,
        error=error,
        turnstile_site_key=os.environ.get("TURNSTILE_SITE_KEY", ""),
    )


@app.route("/set-consent", methods=["POST"])
def set_consent():
    consent = request.form.get("consent", "false")
    if consent not in ("true", "false"):
        consent = "false"

    is_htmx = bool(request.headers.get("HX-Request"))
    if is_htmx:
        resp = make_response("", 204)
    else:
        # No-JS fallback: always redirect to a safe internal URL
        resp = make_response(redirect(url_for("index"), 302))

    resp.set_cookie(
        "analytics_consent",
        consent,
        max_age=365 * 24 * 60 * 60,
        secure=True,
        httponly=False,   # JS must read it to suppress the banner on SPA navigations
        samesite="Lax",
    )
    return resp


@app.route("/privacy")
def privacy():
    return render_template("privacy.html", active_page="privacy")


@app.route("/robots.txt")
def robots_txt():
    content = """\
# As a condition of accessing this website, you agree to abide by the following
# content signals:

# (a) If a content-signal = yes, you may collect content for the corresponding use.
# (b) If a content-signal = no, you may not collect content for the corresponding use.
# (c) If the website operator does not include a content signal for a corresponding
#     use, the website operator neither grants nor restricts permission via content
#     signal with respect to the corresponding use.

# search:   building a search index and providing search results
# ai-input: inputting content into one or more AI models
# ai-train: training or fine-tuning AI models

# ANY RESTRICTIONS EXPRESSED VIA CONTENT SIGNALS ARE EXPRESS RESERVATIONS OF
# RIGHTS UNDER ARTICLE 4 OF THE EUROPEAN UNION DIRECTIVE 2019/790 ON COPYRIGHT
# AND RELATED RIGHTS IN THE DIGITAL SINGLE MARKET.

search: yes
ai-input: no
ai-train: no

User-agent: *
Allow: /
Disallow: /admin/
Sitemap: https://kyrylobublii.com/sitemap.xml
"""
    return Response(content, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    projects = _get_projects()
    xml = render_template("sitemap.xml", projects=projects, today=date.today().isoformat())
    return Response(xml, mimetype="application/xml")


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == '__main__':
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
