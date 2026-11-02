import pytest

from shop import catalog, db, migrate, orders


@pytest.fixture
def conn(tmp_path):
    conn = db.connect(tmp_path / 'shop.sqlite3')
    migrate.migrate(conn, log=lambda message: None)
    conn.executemany('INSERT INTO products (id, sku, name, price) VALUES (?, ?, ?, ?)',
                     [(1, 'SKU-1', 'Mug', 12.5), (2, 'SKU-2', 'Tea towel', 3.99)])
    conn.execute("INSERT INTO customers (id, email, name) VALUES (1, 'a@example.com', 'Ada')")
    conn.execute("INSERT INTO orders (id, number, customer_id, placed_at) VALUES (1, 'O-1', 1, '2026-10-01T10:00:00Z')")
    conn.executemany('INSERT INTO order_lines (order_id, product_id, qty, unit_price) VALUES (?, ?, ?, ?)',
                     [(1, 1, 2, 12.5), (1, 2, 3, 3.49)])
    conn.commit()
    return conn


def test_a_products_price(conn):
    assert catalog.product(conn, 'SKU-1')['price'] == 12.5


def test_an_orders_total_is_its_lines_at_the_prices_paid(conn):
    found = orders.order(conn, 'O-1')
    assert [line['unit_price'] for line in found['lines']] == [12.5, 3.49]
    assert found['total'] == pytest.approx(2 * 12.5 + 3 * 3.49)


def test_unknown_order(conn):
    with pytest.raises(KeyError):
        orders.order(conn, 'O-404')
