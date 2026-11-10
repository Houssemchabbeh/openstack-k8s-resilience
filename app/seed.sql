-- Sample courses for local development and the lab.
-- Re-runnable: existing codes are left untouched.

INSERT INTO courses (code, title, kind, capacity, opens_at, hidden) VALUES
    ('CLOUD-501', 'Cloud-Native Infrastructures',      'elective',  30, '2026-11-16 09:00+01', false),
    ('SEC-502',   'Network Security',                  'elective',  25, '2026-11-16 09:00+01', false),
    ('DATA-503',  'Distributed Databases',             'elective',   2, '2026-11-16 09:00+01', false),  -- tiny: easy "course full"
    ('TP-NET-G1', 'Networking lab - group 1',          'lab_group', 15, '2026-11-16 09:00+01', false),
    ('TP-NET-G2', 'Networking lab - group 2',          'lab_group', 15, '2026-11-16 09:00+01', false),
    ('SMOKE-000', 'Smoke test course (CI only)',       'elective', 100000, '2026-01-01 00:00+00', true)
ON CONFLICT (code) DO NOTHING;
