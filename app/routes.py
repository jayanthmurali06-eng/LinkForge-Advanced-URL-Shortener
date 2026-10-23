import sqlite3
import secrets
import string
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    abort,
)

main = Blueprint("main", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "linkforge.db"

UTC = ZoneInfo("UTC")
IST = ZoneInfo("Asia/Kolkata")


def get_db():
    """Connect to the existing SQLite database."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    """Create the links table and safely migrate older databases."""
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                original_url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                clicks INTEGER NOT NULL DEFAULT 0
            )
        """)

        columns = {
            row["name"]
            for row in db.execute(
                "PRAGMA table_info(links)"
            ).fetchall()
        }

        if "clicks" not in columns:
            db.execute("""
                ALTER TABLE links
                ADD COLUMN clicks INTEGER NOT NULL DEFAULT 0
            """)


def generate_code(length=7):
    """Generate a random short code."""
    characters = string.ascii_letters + string.digits
    return "".join(
        secrets.choice(characters)
        for _ in range(length)
    )


def is_valid_url(value):
    """Accept HTTP and HTTPS URLs with a valid hostname."""
    try:
        parsed = urlparse(value)

        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.hostname)
            and not any(char.isspace() for char in value)
            and parsed.port != 0
        )
    except (ValueError, TypeError):
        return False


def format_ist(timestamp):
    """Convert a SQLite UTC timestamp to Indian Standard Time."""
    if not timestamp:
        return ""

    try:
        parsed = datetime.fromisoformat(str(timestamp))

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)

        return parsed.astimezone(IST).strftime(
            "%d %b %Y, %I:%M %p"
        )
    except (ValueError, TypeError):
        return str(timestamp)


@main.route("/", methods=["GET", "POST"])
def index():
    init_db()

    short_url = None
    error = None

    if request.method == "POST":
        original_url = request.form.get("url", "").strip()

        if not original_url:
            error = "Please enter a URL."
        elif not is_valid_url(original_url):
            error = (
                "Enter a valid URL beginning with "
                "http:// or https://."
            )
        else:
            with get_db() as db:
                code = None

                for _ in range(20):
                    candidate = generate_code()

                    exists = db.execute(
                        "SELECT 1 FROM links WHERE code = ?",
                        (candidate,),
                    ).fetchone()

                    if not exists:
                        code = candidate
                        break

                if code is None:
                    error = (
                        "Could not generate a link. "
                        "Please try again."
                    )
                else:
                    db.execute(
                        """
                        INSERT INTO links (code, original_url)
                        VALUES (?, ?)
                        """,
                        (code, original_url),
                    )

                    short_url = (
                        request.url_root.rstrip("/")
                        + "/"
                        + code
                    )

    return render_template(
        "index.html",
        short_url=short_url,
        error=error,
    )


@main.route("/analytics", methods=["GET"])
def analytics():
    init_db()

    with get_db() as db:
        total_links = db.execute(
            "SELECT COUNT(*) FROM links"
        ).fetchone()[0]

        total_clicks = db.execute(
            "SELECT COALESCE(SUM(clicks), 0) FROM links"
        ).fetchone()[0]

        popular_links = db.execute("""
            SELECT id, code, original_url, created_at, clicks
            FROM links
            ORDER BY clicks DESC, id DESC
        """).fetchall()

    links_for_template = []

    for link in popular_links:
        item = dict(link)
        item["created_at"] = format_ist(item["created_at"])
        links_for_template.append(item)

    return render_template(
        "analytics.html",
        total_links=total_links,
        total_clicks=total_clicks,
        popular_links=links_for_template,
    )


@main.route("/delete/<code>", methods=["POST"])
def delete_link(code):
    """Delete a short link selected from the analytics dashboard."""
    init_db()

    with get_db() as db:
        result = db.execute(
            "DELETE FROM links WHERE code = ?",
            (code,),
        )

        if result.rowcount == 0:
            abort(404)

    return redirect(url_for("main.analytics"))


@main.route("/<code>", methods=["GET"])
def redirect_to_original(code):
    """Redirect to the destination and record the click."""
    init_db()

    with get_db() as db:
        link = db.execute(
            "SELECT original_url FROM links WHERE code = ?",
            (code,),
        ).fetchone()

        if link is None:
            abort(404)

        original_url = link["original_url"]

        db.execute(
            "UPDATE links SET clicks = clicks + 1 WHERE code = ?",
            (code,),
        )

    return redirect(original_url)
