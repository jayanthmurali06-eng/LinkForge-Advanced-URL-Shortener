
import io
import secrets
import sqlite3
import string
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import qrcode
from flask import (
    Blueprint,
    abort,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

main = Blueprint("main", __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "linkforge.db"

UTC = ZoneInfo("UTC")
IST = ZoneInfo("Asia/Kolkata")


def get_db():
    """Connect to the existing SQLite database."""
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    """Create the links table and migrate older databases safely."""
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
    """Generate a cryptographically random short code."""
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))


def is_valid_url(value):
    """Accept well-formed HTTP and HTTPS URLs."""
    if not isinstance(value, str) or not value:
        return False

    if any(char.isspace() for char in value):
        return False

    try:
        parsed = urlparse(value)

        if parsed.scheme.lower() not in ("http", "https"):
            return False

        if not parsed.hostname:
            return False

        # Do not accept URLs containing embedded login credentials.
        if parsed.username is not None or parsed.password is not None:
            return False

        port = parsed.port
        if port is not None and not (1 <= port <= 65535):
            return False

        return True

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


def get_link(code):
    """Find a short link by its code."""
    with get_db() as db:
        return db.execute(
            """
            SELECT code, original_url
            FROM links
            WHERE code = ?
            """,
            (code,),
        ).fetchone()


def make_qr_image(code):
    """Create a QR code image for an existing short link."""
    link = get_link(code)

    if link is None:
        abort(404)

    short_url = url_for(
        "main.redirect_to_original",
        code=code,
        _external=True,
    )

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(short_url)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white",
    )

    image_buffer = io.BytesIO()
    image.save(image_buffer, format="PNG")
    image_buffer.seek(0)

    return image_buffer


@main.route("/", methods=["GET", "POST"])
def index():
    init_db()

    short_url = None
    short_code = None
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

                # Generate a unique code, retrying on collisions.
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

                    short_code = code
                    short_url = (
                        request.url_root.rstrip("/") + "/" + code
                    )

    return render_template(
        "index.html",
        short_url=short_url,
        short_code=short_code,
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
    """Delete a short link from the analytics dashboard."""
    init_db()

    with get_db() as db:
        result = db.execute(
            "DELETE FROM links WHERE code = ?",
            (code,),
        )

        if result.rowcount == 0:
            abort(404)

    return redirect(url_for("main.analytics"))


@main.route("/qr/<code>", methods=["GET"])
def generate_qr(code):
    """Display a QR code image in the browser."""
    init_db()
    image_buffer = make_qr_image(code)

    # Inline response lets the image display inside the webpage.
    return send_file(
        image_buffer,
        mimetype="image/png",
        as_attachment=False,
        download_name=f"linkforge-{code}-qr.png",
    )


@main.route("/qr/<code>/download", methods=["GET"])
def download_qr(code):
    """Download a QR code as a PNG image."""
    init_db()
    image_buffer = make_qr_image(code)

    return send_file(
        image_buffer,
        mimetype="image/png",
        as_attachment=True,
        download_name=f"linkforge-{code}-qr.png",
    )


@main.route("/<code>", methods=["GET"])
def redirect_to_original(code):
    """Redirect to the original URL and record the click."""
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

        db.execute(
            "UPDATE links SET clicks = clicks + 1 WHERE code = ?",
            (code,),
        )

        original_url = link["original_url"]

    return redirect(original_url)
