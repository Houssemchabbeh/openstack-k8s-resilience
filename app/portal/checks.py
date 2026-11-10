"""Correctness invariants, checked after every drill."""

from psycopg.rows import dict_row

# seats_taken must equal the real number of registrations
SEAT_MISMATCHES = """
    SELECT c.code, c.seats_taken, count(r.id) AS registrations
    FROM courses c LEFT JOIN registrations r ON r.course_id = c.id
    GROUP BY c.id
    HAVING c.seats_taken <> count(r.id)
    ORDER BY c.code
"""

# Impossible thanks to the CHECK constraint, checked anyway.
OVERBOOKED = """
    SELECT code, seats_taken, capacity
    FROM courses
    WHERE seats_taken > capacity
    ORDER BY code
"""

# Impossible thanks to the UNIQUE constraint, checked anyway.
DUPLICATES = """
    SELECT count(*) FROM (
        SELECT 1 FROM registrations
        GROUP BY student_id, course_id
        HAVING count(*) > 1
    ) d
"""


def run(conn) -> dict:
    with conn.transaction():
        # One snapshot for all queries, so registrations arriving meanwhile
        # can't make the numbers disagree with each other.
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        cur = conn.cursor(row_factory=dict_row)
        mismatches = cur.execute(SEAT_MISMATCHES).fetchall()
        overbooked = cur.execute(OVERBOOKED).fetchall()
        duplicates = conn.execute(DUPLICATES).fetchone()[0]
        courses = conn.execute("SELECT count(*) FROM courses").fetchone()[0]
        registrations = conn.execute("SELECT count(*) FROM registrations").fetchone()[0]

    return {
        "ok": not mismatches and not overbooked and duplicates == 0,
        "seat_mismatches": mismatches,
        "overbooked": overbooked,
        "duplicates": duplicates,
        "courses": courses,
        "registrations": registrations,
    }
