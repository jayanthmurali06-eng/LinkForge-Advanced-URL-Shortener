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
    """Create the table and migrate older databases safely."""
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
    """Generate a random short URL code."""
    characters = string.ascii_letters + string.digits
    return "".join(
        secrets.choice(characters) for _ in range(length)
    )


def is_valid_url(value):
    """Allow valid HTTP and HTTPS URLs."""
    try:
        parsed = urlparse(value)

        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.hostname)
            and not any(char.isspace() for char in value)
        )
    except (ValueError, TypeError):
        return False


def format_ist(timestamp):
    """Convert SQLite UTC timestamps to Indian Standard Time."""
    if not timestamp:
        return ""

    try:
        utc_time = datetime.strptime(
            timestamp, "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=UTC)

        return utc_time.astimezone(IST).strftime(
            "%d %b %Y, %I:%M:%S %p IST"
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
                    error = "Could not generate a link. Please try again."
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
        summary = db.execute("""
            SELECT
                COUNT(*) AS total_links,
                COALESCE(SUM(clicks), 0) AS total_clicks
            FROM links
        """).fetchone()

        rows = db.execute("""
            SELECT code, original_url, created_at, clicks
            FROM links
            ORDER BY clicks DESC, created_at DESC
        """).fetchall()

    popular_links = []

    for row in rows:
        link = dict(row)

        link["created_at"] = format_ist(
            link.get("created_at")
        )

        link["short_url"] = (
            request.url_root.rstrip("/")
            + "/"
            + link["code"]
        )

        popular_links.append(link)

    return render_template(
        "analytics.html",
        total_links=summary["total_links"],
        total_clicks=summary["total_clicks"],
        popular_links=popular_links,
    )


@main.route("/<code>", methods=["GET"])
def redirect_to_original(code):
    init_db()

    with get_db() as db:
        link = db.execute(
            """
            SELECT original_url
            FROM links
            WHERE code = ?
            """,
            (code,),
        ).fetchone()

        if link is None:
            abort(404)

        original_url = link["original_url"]

        db.execute(
            """
            UPDATE links
            SET clicks = clicks + 1
            WHERE code = ?
            """,
            (code,),
        )

    return redirect(original_url)
