import threading
from collections import Counter

import psycopg

from portal.registration import register


def seats_taken(conn, course_id):
    return conn.execute(
        "SELECT seats_taken FROM courses WHERE id = %s", (course_id,)
    ).fetchone()[0]


def registration_count(conn, course_id):
    return conn.execute(
        "SELECT count(*) FROM registrations WHERE course_id = %s", (course_id,)
    ).fetchone()[0]


def test_register_takes_a_seat(conn, courses):
    result = register(conn, "S001", courses["BIG"])

    assert result.status == "registered"
    assert result.receipt.startswith("REG-") and len(result.receipt) == 12
    assert seats_taken(conn, courses["BIG"]) == 1
    assert registration_count(conn, courses["BIG"]) == 1


def test_retry_returns_same_receipt(conn, courses):
    first = register(conn, "S001", courses["BIG"])
    retry = register(conn, "S001", courses["BIG"])

    assert retry.status == "already_registered"
    assert retry.receipt == first.receipt
    assert seats_taken(conn, courses["BIG"]) == 1


def test_full_course_writes_nothing(conn, courses):
    register(conn, "S001", courses["TINY"])
    register(conn, "S002", courses["TINY"])
    result = register(conn, "S003", courses["TINY"])

    assert result.status == "full"
    assert result.receipt is None
    assert seats_taken(conn, courses["TINY"]) == 2
    assert registration_count(conn, courses["TINY"]) == 2


def test_retry_on_full_course_still_gets_receipt(conn, courses):
    """The student who took the last seat retries: receipt, not 'full'."""
    register(conn, "S001", courses["TINY"])
    last_seat = register(conn, "S002", courses["TINY"])
    retry = register(conn, "S002", courses["TINY"])

    assert retry.status == "already_registered"
    assert retry.receipt == last_seat.receipt


def test_unknown_course(conn, courses):
    assert register(conn, "S001", 999_999).status == "unknown_course"


def run_concurrently(dsn, calls):
    """Run register() calls in parallel threads, each with its own connection."""
    barrier = threading.Barrier(len(calls))
    results = []

    def worker(student_id, course_id):
        with psycopg.connect(dsn, autocommit=True) as c:
            barrier.wait()                      # start all at the same moment
            results.append(register(c, student_id, course_id))

    threads = [threading.Thread(target=worker, args=call) for call in calls]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_race_for_last_seats_never_overbooks(dsn, conn, courses):
    tiny = courses["TINY"]
    results = run_concurrently(dsn, [(f"S{n:03}", tiny) for n in range(20)])

    assert Counter(r.status for r in results) == {"registered": 2, "full": 18}
    assert seats_taken(conn, tiny) == 2
    assert registration_count(conn, tiny) == 2


def test_double_submit_creates_one_registration(dsn, conn, courses):
    big = courses["BIG"]
    results = run_concurrently(dsn, [("S001", big), ("S001", big)])

    assert Counter(r.status for r in results) == {"registered": 1, "already_registered": 1}
    assert results[0].receipt == results[1].receipt
    assert seats_taken(conn, big) == 1
