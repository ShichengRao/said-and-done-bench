"""When each customer signed up (unknown for the ones from before this migration)."""


def apply(conn, log):
    conn.executescript('ALTER TABLE customers ADD COLUMN created_at TEXT;')
