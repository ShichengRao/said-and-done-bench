"""Orders get a status: placed, shipped, cancelled."""


def apply(conn, log):
    conn.executescript("ALTER TABLE orders ADD COLUMN status TEXT NOT NULL DEFAULT 'placed';")
