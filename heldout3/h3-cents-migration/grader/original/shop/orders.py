"""Orders, their lines, and their totals."""

from shop.money import cents


def order(conn, number):
    row = conn.execute('SELECT id, number, placed_at, status FROM orders WHERE number = ?', (number,)).fetchone()
    if row is None:
        raise KeyError(f'no order {number}')
    lines = [
        {'sku': line['sku'], 'name': line['name'], 'qty': line['qty'], 'unit_price': cents(line['unit_price'])}
        for line in conn.execute(
            'SELECT p.sku, p.name, l.qty, l.unit_price FROM order_lines l JOIN products p ON p.id = l.product_id '
            'WHERE l.order_id = ? ORDER BY l.id', (row['id'],))
    ]
    return {'number': row['number'], 'placed_at': row['placed_at'], 'status': row['status'], 'lines': lines,
            'total': sum(line['qty'] * line['unit_price'] for line in lines)}
