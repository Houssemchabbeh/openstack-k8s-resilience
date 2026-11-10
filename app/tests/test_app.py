import re

import psycopg
import pytest

from portal import create_app

UNREACHABLE_DB = "postgresql://postgres:dev@localhost:1/none"


@pytest.fixture
def app(dsn, courses):
    app = create_app(dsn)
    real_pool = app.extensions["db_pool"]           # tests may swap it for DownPool
    yield app
    real_pool.close()


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, student_id, course_id):
    return client.post("/register", data={"student_id": student_id, "course_id": course_id})


class DownPool:
    """Stands in for the pool when the database is down."""

    def connection(self):
        raise psycopg.OperationalError("database is down (simulated)")


# --- Normal path --------------------------------------------------------------

def test_index_lists_visible_courses_only(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"BIG" in resp.data and b"TINY" in resp.data
    assert b"HIDDEN" not in resp.data


def test_register_redirects_to_receipt(client, courses):
    resp = register(client, "S001", courses["BIG"])
    assert resp.status_code == 303
    assert re.fullmatch(r"/receipt/REG-[A-Z2-7]{8}", resp.headers["Location"])

    page = client.get(resp.headers["Location"])
    assert page.status_code == 200
    assert b"Registration confirmed" in page.data and b"S001" in page.data


def test_retry_redirects_to_same_receipt(client, courses):
    first = register(client, "S001", courses["BIG"])
    retry = register(client, "S001", courses["BIG"])
    assert retry.status_code == 303
    assert retry.headers["Location"] == first.headers["Location"] + "?again=1"
    assert b"already registered" in client.get(retry.headers["Location"]).data


def test_full_course_returns_409(client, courses):
    client.get("/")                                   # fills the cache used for the course name
    register(client, "S001", courses["TINY"])
    register(client, "S002", courses["TINY"])
    resp = register(client, "S003", courses["TINY"])
    assert resp.status_code == 409
    assert b"TINY has no seats left" in resp.data


def test_hidden_course_accepts_registrations(client, courses):
    """The Jenkins smoke test registers on the hidden course."""
    assert register(client, "SMOKE-1", courses["HIDDEN"]).status_code == 303


@pytest.mark.parametrize("student_id", ["", "a b", "x" * 33, "<script>"])
def test_invalid_student_id_returns_400(client, courses, student_id):
    assert register(client, student_id, courses["BIG"]).status_code == 400


def test_invalid_course_returns_400_or_404(client):
    assert register(client, "S001", "abc").status_code == 400
    assert register(client, "S001", 999_999).status_code == 404


def test_unknown_receipt_returns_404(client):
    assert client.get("/receipt/REG-NOPE0000").status_code == 404


# --- Maintenance mode ---------------------------------------------------------

def test_db_down_serves_cached_list_with_503(app, client):
    client.get("/")                                   # DB up: list cached
    app.extensions["db_pool"] = DownPool()

    resp = client.get("/")
    assert resp.status_code == 503
    assert resp.headers["Retry-After"] == "30"
    assert b"temporarily unavailable" in resp.data
    assert b"BIG" in resp.data                        # cached course list still shown


def test_register_during_outage_returns_503(app, client, courses):
    app.extensions["db_pool"] = DownPool()
    resp = register(client, "S001", courses["BIG"])
    assert resp.status_code == 503
    assert resp.headers["Retry-After"] == "30"


def test_unreachable_db_real_pool():
    """Real pool, DB never reachable: app still starts, probes stay green, pages get 503."""
    app = create_app(UNREACHABLE_DB)
    try:
        client = app.test_client()
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 200
        resp = client.get("/")
        assert resp.status_code == 503
        assert b"Course list as of" not in resp.data  # nothing cached yet
    finally:
        app.extensions["db_pool"].close()


# --- Invariant check ----------------------------------------------------------

def test_admin_check_ok(client, courses):
    register(client, "S001", courses["BIG"])
    register(client, "S002", courses["TINY"])
    resp = client.get("/admin/check")
    assert resp.status_code == 200
    report = resp.get_json()
    assert report["ok"] is True
    assert report["registrations"] == 2 and report["courses"] == 3


def test_admin_check_detects_seat_mismatch(client, conn):
    conn.execute("UPDATE courses SET seats_taken = 1 WHERE code = 'BIG'")  # seat with no registration
    resp = client.get("/admin/check")
    assert resp.status_code == 500
    report = resp.get_json()
    assert report["ok"] is False
    assert report["seat_mismatches"] == [{"code": "BIG", "seats_taken": 1, "registrations": 0}]
