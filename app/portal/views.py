import re
from datetime import datetime, timezone

import psycopg
from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from psycopg.rows import dict_row
from psycopg_pool import PoolTimeout

from . import checks
from .registration import register

bp = Blueprint("portal", __name__)

STUDENT_ID = re.compile(r"[A-Za-z0-9-]{1,32}")
RETRY_AFTER_SECONDS = "30"

COURSE_LIST_SQL = """
    SELECT id, code, title, kind, capacity, seats_taken,
           opens_at AT TIME ZONE 'UTC' AS opens_at_utc
    FROM courses
    WHERE NOT hidden
    ORDER BY kind, code
"""

RECEIPT_SQL = """
    SELECT r.receipt, r.student_id, r.created_at AT TIME ZONE 'UTC' AS created_at_utc,
           c.code, c.title, c.kind
    FROM registrations r JOIN courses c ON c.id = r.course_id
    WHERE r.receipt = %s
"""


def pool():
    return current_app.extensions["db_pool"]


def message(title, text, status):
    return render_template("message.html", title=title, text=text), status


# --- Maintenance mode -------------------------------------------------------
# Any DB connection problem, on any route, ends here: 503 + Retry-After, with
# the last course list that was read successfully.

@bp.app_errorhandler(psycopg.OperationalError)
@bp.app_errorhandler(PoolTimeout)
def db_unavailable(exc):
    current_app.logger.warning("database unavailable: %s", exc)
    cache = current_app.extensions["course_cache"]
    body = render_template("maintenance.html", courses=cache["courses"], cached_at=cache["at"])
    return body, 503, {"Retry-After": RETRY_AFTER_SECONDS}


# --- Pages ------------------------------------------------------------------

@bp.get("/")
def index():
    # Always read the DB (never serve the cache while the DB is up), so the
    # probe sees an outage the moment it starts.
    with pool().connection() as conn:
        courses = conn.cursor(row_factory=dict_row).execute(COURSE_LIST_SQL).fetchall()
    current_app.extensions["course_cache"] = {
        "courses": courses,
        "at": datetime.now(timezone.utc),
    }
    return render_template("index.html", courses=courses)


@bp.post("/register")
def register_seat():
    student_id = request.form.get("student_id", "").strip()
    if not STUDENT_ID.fullmatch(student_id):
        return message("Invalid student ID", "Use 1 to 32 letters, digits or '-'.", 400)
    try:
        course_id = int(request.form.get("course_id", ""))
    except ValueError:
        return message("Invalid course", "Please choose a course from the list.", 400)

    with pool().connection() as conn:
        result = register(conn, student_id, course_id)

    if result.status == "unknown_course":
        return message("Unknown course", "This course does not exist.", 404)
    if result.status == "full":
        cached = {c["id"]: c for c in current_app.extensions["course_cache"]["courses"]}
        name = cached[course_id]["code"] if course_id in cached else "This course"
        return message("Course full", f"{name} has no seats left.", 409)

    # 303 = "see other": a page refresh can't resubmit the form, and the load
    # generator reads the receipt from the Location header.
    params = {"again": 1} if result.status == "already_registered" else {}
    return redirect(url_for(".receipt", receipt=result.receipt, **params), 303)


@bp.get("/receipt/<receipt>")
def receipt(receipt):
    with pool().connection() as conn:
        row = conn.cursor(row_factory=dict_row).execute(RECEIPT_SQL, (receipt,)).fetchone()
    if row is None:
        return message("Receipt not found", f"No registration with receipt {receipt}.", 404)
    return render_template("receipt.html", r=row, again=request.args.get("again"))


# --- Probes and checks ------------------------------------------------------

@bp.get("/healthz")
def healthz():
    """Liveness: the process answers. Never touches the DB."""
    return "ok\n", 200, {"Content-Type": "text/plain"}


@bp.get("/readyz")
def readyz():
    """Readiness: the app can serve pages. Deliberately no DB check, so a DB
    outage shows the maintenance page instead of taking both pods out."""
    return "ok\n", 200, {"Content-Type": "text/plain"}


@bp.get("/admin/check")
def admin_check():
    with pool().connection() as conn:
        report = checks.run(conn)
    return jsonify(report), 200 if report["ok"] else 500
