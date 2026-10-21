
import secrets
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from flask import Blueprint, current_app, redirect, render_template, request, url_for

main = Blueprint("main", __name__)

DB_PATH = Path(__file__).resolve().parent.parent / "linkforge.db"


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                original_url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


@main.route("/", methods=["GET", "POST"])
def index():
    short_url = None
    error = None

    if request.method == "POST":
        original_url = request.form.get("url", "").strip()
        parsed = urlparse(original_url)

        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or any(char.isspace() for char in original_url)
        ):
            error = "Enter a valid URL beginning with http:// or https://."
        else:
            init_db()

            with get_db() as db:
                while True:
                    code = secrets.token_urlsafe(5)
                    try:
                        db.execute(
                            "INSERT INTO links (code, original_url) VALUES (?, ?)",
                            (code, original_url),
                        )
                        break
                    except sqlite3.IntegrityError:
                        continue

            short_url = url_for("main.redirect_link", code=code, _external=True)

    return render_template("index.html", short_url=short_url, error=error)


@main.route("/<code>")
def redirect_link(code):
    init_db()

    with get_db() as db:
        link = db.execute(
            "SELECT original_url FROM links WHERE code = ?", (code,)
        ).fetchone()

    if link is None:
        return "Short link not found.", 404

    return redirect(link["original_url"])
