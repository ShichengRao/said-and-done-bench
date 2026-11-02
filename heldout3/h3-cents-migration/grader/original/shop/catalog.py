"""Products and their prices."""

from shop.money import cents


def product(conn, sku):
    row = conn.execute('SELECT id, sku, name, price, active FROM products WHERE sku = ?', (sku,)).fetchone()
    if row is None:
        raise KeyError(f'no product {sku}')
    return {'id': row['id'], 'sku': row['sku'], 'name': row['name'], 'price': cents(row['price']),
            'active': bool(row['active'])}
