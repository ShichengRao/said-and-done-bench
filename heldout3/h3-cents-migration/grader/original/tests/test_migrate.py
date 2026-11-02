import pytest

from shop import db, migrate

CENTS = '0007_prices_to_cents'


def quiet(message):
    pass


@pytest.fixture
def conn(tmp_path):
    return db.connect(tmp_path / 'shop.sqlite3')


def test_a_new_database_gets_every_migration(conn):
    assert migrate.migrate(conn, log=quiet) == migrate.available()
    assert migrate.pending(conn) == []
    assert migrate.migrate(conn, log=quiet) == []


def test_prices_become_cents(conn):
    for name in migrate.available():
        if name < CENTS:
            migrate.apply(conn, name, log=quiet)
    conn.executemany('INSERT INTO products (id, sku, name, price) VALUES (?, ?, ?, ?)',
                     [(i, f'SKU-{i}', f'Product {i}', price) for i, price in
                      enumerate([0.29, 4.99, 12.5, 19.99, 499.0, 1.15], 1)])
    conn.execute("INSERT INTO customers (id, email, name) VALUES (1, 'a@example.com', 'Ada')")
    conn.execute("INSERT INTO orders (id, number, customer_id, placed_at) VALUES (1, 'O-1', 1, '2026-10-01T10:00:00Z')")
    conn.executemany('INSERT INTO order_lines (id, order_id, product_id, qty, unit_price) VALUES (?, 1, 1, 1, ?)',
                     [(i, 0.29 if i % 2 else 17.85) for i in range(1, 2501)])
    conn.commit()

    migrate.apply(conn, CENTS, log=quiet)

    assert [row[0] for row in conn.execute('SELECT price FROM products ORDER BY id')] == [
        29, 499, 1250, 1999, 49900, 115]
    assert {row[0] for row in conn.execute('SELECT unit_price FROM order_lines')} == {29, 1785}
    assert migrate.pending(conn) == []
