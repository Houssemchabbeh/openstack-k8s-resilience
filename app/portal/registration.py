"""Seat registration: the one transaction the whole project protects.

Connections are expected in autocommit mode, so `conn.transaction()` is the
only place a transaction starts (BEGIN) and ends (COMMIT, or ROLLBACK on error).
"""

import base64
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class Result:
    status: str                # "registered" | "already_registered" | "full" | "unknown_course"
    receipt: str | None = None


def new_receipt() -> str:
    """'REG-' + 8 base32 characters (40 random bits), e.g. REG-K3J9QZ2A."""
    return "REG-" + base64.b32encode(secrets.token_bytes(5)).decode()


def register(conn, student_id: str, course_id: int) -> Result:
    with conn.transaction():
        # 1. Lock the course row. A concurrent registration for the same course
        #    waits here until we commit, so seats_taken can't be read stale.
        course = conn.execute(
            "SELECT capacity, seats_taken FROM courses WHERE id = %s FOR UPDATE",
            (course_id,),
        ).fetchone()
        if course is None:
            return Result("unknown_course")
        capacity, seats_taken = course

        # 2. Already registered? Return the same receipt (safe retries).
        #    Checked before capacity so a retry on a now-full course still
        #    gets its receipt instead of "full".
        existing = _existing_receipt(conn, student_id, course_id)
        if existing:
            return Result("already_registered", existing)

        # 3. No seat left: nothing has been written, the commit just releases the lock.
        if seats_taken >= capacity:
            return Result("full")

        # 4. Insert. ON CONFLICT is a safety net: with the lock held it should never fire.
        inserted = conn.execute(
            """
            INSERT INTO registrations (receipt, student_id, course_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (student_id, course_id) DO NOTHING
            RETURNING receipt
            """,
            (new_receipt(), student_id, course_id),
        ).fetchone()
        if inserted is None:
            return Result("already_registered", _existing_receipt(conn, student_id, course_id))

        # 5. Take the seat. The CHECK (seats_taken <= capacity) is the last line of defence.
        conn.execute(
            "UPDATE courses SET seats_taken = seats_taken + 1 WHERE id = %s",
            (course_id,),
        )
        return Result("registered", inserted[0])


def _existing_receipt(conn, student_id: str, course_id: int) -> str | None:
    row = conn.execute(
        "SELECT receipt FROM registrations WHERE student_id = %s AND course_id = %s",
        (student_id, course_id),
    ).fetchone()
    return row[0] if row else None
