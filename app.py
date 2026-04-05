from flask import Flask, render_template
from data.projects import PROJECTS, SKILLS

app = Flask(__name__)


@app.route("/")
def index():
    featured = [p for p in PROJECTS if p["featured"]]
    return render_template("index.html", active_page="home", featured=featured, projects=PROJECTS)


@app.route("/projects")
def projects():
    return render_template("projects.html", active_page="projects", projects=PROJECTS)


@app.route("/about")
def about():
    return render_template("about.html", active_page="about", skills=SKILLS)


@app.route("/contact")
def contact():
    return render_template("contact.html", active_page="contact")


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == '__main__':
    app.run(debug=True)
