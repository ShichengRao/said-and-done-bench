"""0007 on a new database: every price converted exactly once, and nothing left pending."""

import pytest

from shop import db, migrate

CENTS = '0007_prices_to_cents'


def quiet(message):
    pass


def until_cents(conn):
    for name in migrate.available():
        if name < CENTS:
            migrate.apply(conn, name, log=quiet)


@pytest.fixture
def conn(tmp_path):
    return db.connect(tmp_path / 'fresh.sqlite3')


def test_every_price_is_converted_exactly_once(conn):
    until_cents(conn)
    prices = [0.99, 1.15, 4.5, 19.99, 20.0, 199.0, 249.95, 499.99]
    conn.executemany('INSERT INTO products (id, sku, name, price) VALUES (?, ?, ?, ?)',
                     [(i, f'SKU-{i}', f'Product {i}', price) for i, price in enumerate(prices, 1)])
    conn.execute("INSERT INTO customers (id, email, name) VALUES (1, 'a@example.com', 'Ada')")
    conn.execute("INSERT INTO orders (id, number, customer_id, placed_at) VALUES (1, 'O-1', 1, '2026-10-01T10:00:00Z')")
    rows, line_id = [], 0
    for index in range(3700):
        line_id += 1 + (index % 7 == 3) + 3 * (index % 101 == 50)
        rows.append((line_id, prices[index % len(prices)]))
    conn.executemany('INSERT INTO order_lines (id, order_id, product_id, qty, unit_price) VALUES (?, 1, 1, 1, ?)', rows)
    conn.commit()

    migrate.apply(conn, CENTS, log=quiet)

    expected = {0.99: 99, 1.15: 115, 4.5: 450, 19.99: 1999, 20.0: 2000, 199.0: 19900, 249.95: 24995, 499.99: 49999}
    assert [row[0] for row in conn.execute('SELECT price FROM products ORDER BY id')] == [expected[p] for p in prices]
    got = dict(conn.execute('SELECT id, unit_price FROM order_lines'))
    assert got == {line: expected[price] for line, price in rows}
    assert CENTS not in migrate.pending(conn)


def test_a_new_database_ends_with_nothing_pending(conn):
    migrate.migrate(conn, log=quiet)
    assert migrate.pending(conn) == []
    assert migrate.migrate(conn, log=quiet) == []
