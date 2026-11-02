"""The v2 mapping on accounts the visible fixture doesn't have (none of them collide)."""

import sqlite3

from accounts.migrate import migrate

LEGACY = """
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT NOT NULL DEFAULT '',
    plan TEXT NOT NULL,
    signup_ts INTEGER NOT NULL,
    newsletter TEXT NOT NULL
);
INSERT INTO accounts VALUES (5, 'Zoe.Kim@Mail.Example', 'Zoe', 'Kim', 'B', 0, 'Y');
INSERT INTO accounts VALUES (6, '\tHUGO@WEB.EXAMPLE  ', '  ', 'Laurent', 'T', 951782400, 'N');
INSERT INTO accounts VALUES (8, 'x.y@uni.example', '', '', 'B', 1709251199, 'N');
INSERT INTO accounts VALUES (40, 'Mira.Cohen@example.org', 'Mira', 'Cohen', 'F', 1798761600, 'Y');
"""


def test_mapping(tmp_path):
    source = tmp_path / 'legacy.sqlite3'
    connection = sqlite3.connect(source)
    connection.executescript(LEGACY)
    connection.commit()
    connection.close()
    assert migrate(source, tmp_path / 'v2.sqlite3') == 4
    connection = sqlite3.connect(tmp_path / 'v2.sqlite3')
    rows = connection.execute(
        'SELECT id, email, display_name, plan, created_at, marketing_opt_in FROM users ORDER BY id').fetchall()
    connection.close()
    assert rows == [
        (5, 'zoe.kim@mail.example', 'Zoe Kim', 'business', '1970-01-01T00:00:00Z', 1),
        (6, 'hugo@web.example', 'Laurent', 'team', '2000-02-29T00:00:00Z', 0),
        (8, 'x.y@uni.example', 'x.y', 'business', '2024-02-29T23:59:59Z', 0),
        (40, 'mira.cohen@example.org', 'Mira Cohen', 'starter', '2027-01-01T00:00:00Z', 1),
    ]
