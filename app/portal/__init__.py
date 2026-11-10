"""Elective & lab-group registration portal."""

import os
import socket

from flask import Flask
from psycopg_pool import ConnectionPool


def create_app(database_url: str | None = None) -> Flask:
    app = Flask(__name__)

    pool = ConnectionPool(
        database_url or os.environ["DATABASE_URL"],
        min_size=1,
        max_size=int(os.environ.get("DB_POOL_SIZE", "5")),
        timeout=3,                                   # wait max 3 s for a connection, then 503
        kwargs={"autocommit": True, "connect_timeout": 3},
        check=ConnectionPool.check_connection,       # drop dead connections (e.g. after a DB restart)
        # Reconnect backoff doubles with no cap (1, 2, 4 ... 64 s). Giving up after
        # 10 s lets the next request start a fresh attempt, so retries stay <= ~4 s
        # apart and a long outage doesn't add fake downtime after the DB is back.
        reconnect_timeout=10,
        open=False,
    )
    pool.open(wait=False)                            # start even if the DB is down (/readyz needs no DB)

    app.extensions["db_pool"] = pool
    app.extensions["course_cache"] = {"courses": [], "at": None}

    hostname = socket.gethostname()                  # shows which pod answered, useful during drills
    app.context_processor(lambda: {"hostname": hostname})

    from . import views
    app.register_blueprint(views.bp)
    return app
