import logging
import os

import resend
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request
from data.profile import get_profile

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")


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
    return render_template("projects.html", active_page="projects", projects=all_projects)


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


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == '__main__':
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
