"""Products can be taken off sale without deleting them."""


def apply(conn, log):
    conn.executescript('ALTER TABLE products ADD COLUMN active INTEGER NOT NULL DEFAULT 1;')
