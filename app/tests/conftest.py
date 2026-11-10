"""Tests run against a real PostgreSQL: locking can't be tested with mocks.

Set TEST_DATABASE_URL to a throwaway database. Every test DROPS and recreates
the tables, so never point it at a database you care about.
"""

import os
import pathlib

import psycopg
import pytest

APP_DIR = pathlib.Path(__file__).resolve().parents[1]
DSN = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:dev@localhost:5433/portal_test"
)


@pytest.fixture(scope="session")
def dsn():
    try:
        psycopg.connect(DSN, connect_timeout=3).close()
    except psycopg.OperationalError as exc:
        pytest.skip(f"test database not reachable ({DSN}): {exc}")
    return DSN


@pytest.fixture
def courses(dsn):
    """Fresh schema with three courses (one hidden); returns {code: id}."""
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS registrations, courses")
        conn.execute((APP_DIR / "schema.sql").read_text())
        conn.execute(
            """
            INSERT INTO courses (code, title, kind, capacity, opens_at, hidden) VALUES
                ('BIG',    'Big course',    'elective',  10, now(), false),
                ('TINY',   'Tiny course',   'lab_group',  2, now(), false),
                ('HIDDEN', 'Hidden course', 'elective',  10, now(), true)
            """
        )
        return dict(conn.execute("SELECT code, id FROM courses").fetchall())


@pytest.fixture
def conn(dsn, courses):
    with psycopg.connect(dsn, autocommit=True) as c:
        yield c
