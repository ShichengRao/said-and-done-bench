"""Order pages look lines up by order."""


def apply(conn, log):
    conn.executescript('CREATE INDEX order_lines_by_order ON order_lines(order_id);')
