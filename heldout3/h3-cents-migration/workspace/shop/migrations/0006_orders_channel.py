"""Where an order came from: web, app, or phone."""


def apply(conn, log):
    conn.executescript("ALTER TABLE orders ADD COLUMN channel TEXT NOT NULL DEFAULT 'web';")
