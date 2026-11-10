-- Course-registration portal: database schema
-- Safe to re-run (IF NOT EXISTS everywhere).

CREATE TABLE IF NOT EXISTS courses (
    id          serial PRIMARY KEY,
    code        text NOT NULL UNIQUE,                 -- e.g. 'CLOUD-501', 'TP-NET-G2'
    title       text NOT NULL,
    kind        text NOT NULL CHECK (kind IN ('elective', 'lab_group')),
    capacity    int  NOT NULL CHECK (capacity > 0),
    seats_taken int  NOT NULL DEFAULT 0
                CHECK (seats_taken >= 0 AND seats_taken <= capacity),
    opens_at    timestamptz NOT NULL,
    hidden      boolean NOT NULL DEFAULT false        -- smoke-test course, not shown on /
);

CREATE TABLE IF NOT EXISTS registrations (
    id          bigserial PRIMARY KEY,
    receipt     text NOT NULL UNIQUE,                 -- 'REG-XXXXXXXX'
    student_id  text NOT NULL,
    course_id   int  NOT NULL REFERENCES courses(id),
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (student_id, course_id)
);

-- Speeds up the per-course count used by the invariant check.
CREATE INDEX IF NOT EXISTS registrations_course_id_idx ON registrations (course_id);
