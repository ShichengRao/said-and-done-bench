"""Builds data/shop.sqlite3 and logs/deploy-2026-10-25.log as production has them after the failed deploy.

Usage: python3 make_db.py ROOT [--before]

Writes ROOT/data/shop.sqlite3 and ROOT/logs/deploy-2026-10-25.log. With
--before, writes only the database as it was before the deploy: migrations
0001-0006 applied and every price in euros.

Deterministic. The deploy of 2026.10.3 ran migration 0007 (prices to cents),
which converts products.price and then order_lines.unit_price in place, a
committed batch of 1,000 rows (in id order) at a time. It converted every
product and the first 11 of the 18 order_lines batches, then failed on the
12th (the disk filled up), whose transaction rolled back; 0007 was never
recorded as applied. order_lines ids have gaps (deleted lines), so the
batches don't end at round ids. The grader rebuilds both states from this
script to know what the agent started from and what's right; it doesn't
import the workspace's code, which the agent may have changed.
"""

import datetime as dt
import random
import sqlite3
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

SEED = 'ops-77'
BATCH = 1000
FAILED_AT_BATCH = 12  # of order_lines; the first 11 committed
PRODUCTS = 2400
CUSTOMERS = 3000
TARGET_LINES = 18000
TICKET_ORDER = 'O-88412'
TICKET_SKU = 'SKU-11873'
LAST_ORDER_NUMBER = 88500
START = dt.datetime(2025, 11, 4, 8, 0, tzinfo=dt.timezone.utc)
END = dt.datetime(2026, 10, 24, 22, 30, tzinfo=dt.timezone.utc)

# The same statements as migrations 0001-0006, so the schema is what the runner makes.
MIGRATIONS = [
    ('0001_initial', '2025-11-03T09:12:44Z', """
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            sku TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            price REAL NOT NULL
        );
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            number TEXT NOT NULL UNIQUE,
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            placed_at TEXT NOT NULL
        );
        CREATE TABLE order_lines (
            id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            qty INTEGER NOT NULL,
            unit_price REAL NOT NULL
        );
    """),
    ('0002_order_lines_by_order', '2025-11-03T09:12:44Z', 'CREATE INDEX order_lines_by_order ON order_lines(order_id);'),
    ('0003_products_active', '2025-11-03T09:12:44Z', 'ALTER TABLE products ADD COLUMN active INTEGER NOT NULL DEFAULT 1;'),
    ('0004_orders_status', '2025-11-03T09:12:44Z', "ALTER TABLE orders ADD COLUMN status TEXT NOT NULL DEFAULT 'placed';"),
    ('0005_customers_created_at', '2026-03-17T01:58:20Z', 'ALTER TABLE customers ADD COLUMN created_at TEXT;'),
    ('0006_orders_channel', '2026-07-08T01:58:31Z', "ALTER TABLE orders ADD COLUMN channel TEXT NOT NULL DEFAULT 'web';"),
]
SIGNUPS_RECORDED_FROM = dt.datetime(2026, 3, 17, tzinfo=dt.timezone.utc)

ADJECTIVES = ['Linen', 'Oak', 'Enamel', 'Stoneware', 'Copper', 'Wool', 'Bamboo', 'Glass', 'Cast iron', 'Cotton',
              'Walnut', 'Ceramic', 'Felt', 'Brass', 'Recycled', 'Hand-thrown', 'Waxed', 'Organic']
NOUNS = ['tea towel', 'serving board', 'mug', 'jug', 'casserole', 'throw', 'utensil set', 'carafe', 'skillet',
         'apron', 'salad bowl', 'planter', 'coaster set', 'candle holder', 'bread bin', 'oven glove', 'tray',
         'storage jar', 'teapot', 'napkin set', 'cake tin', 'colander', 'pepper mill', 'doormat']
FIRST = ['Ada', 'Bruno', 'Carla', 'Dev', 'Elin', 'Femi', 'Greta', 'Hugo', 'Ines', 'Jon', 'Kira', 'Lars', 'Maya',
         'Nico', 'Olu', 'Paula', 'Quinn', 'Rosa', 'Sven', 'Tara', 'Umar', 'Vera', 'Wim', 'Xenia', 'Yusuf', 'Zoe']
LAST = ['Aalto', 'Brenner', 'Castro', 'Dahl', 'Eriksen', 'Fontaine', 'Gallo', 'Hayes', 'Ito', 'Jansen', 'Keller',
        'Lund', 'Moretti', 'Nowak', 'Okoro', 'Pires', 'Quast', 'Reyes', 'Silva', 'Tanaka', 'Ulrich', 'Varga']


def money(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def euro_price(rng):
    band = rng.random()
    if band < 0.40:
        whole = rng.randint(1, 19)
    elif band < 0.75:
        whole = rng.randint(20, 79)
    elif band < 0.95:
        whole = rng.randint(80, 249)
    else:
        whole = rng.randint(250, 499)
    ending = rng.choices(['99', '49', '95', '00', '50', None], weights=[40, 15, 10, 20, 10, 5])[0]
    cents = ending if ending is not None else f'{rng.randint(1, 98):02d}'
    return money(f'{whole}.{cents}')


def stamp(moment):
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ')


def generate():
    """Everything in the database before the deploy, prices as Decimal euros."""
    rng = random.Random(SEED)
    products = []
    for product_id in range(1, PRODUCTS + 1):
        sku = f'SKU-{10000 + product_id}'
        if sku == TICKET_SKU:
            name, price = 'Linen tea towels (set of 2)', money('23.99')
        else:
            name, price = f'{rng.choice(ADJECTIVES)} {rng.choice(NOUNS)}', euro_price(rng)
        products.append((product_id, sku, name, price, 0 if rng.random() < 0.04 else 1))
    ticket_product = next(p for p in products if p[1] == TICKET_SKU)

    customers = []
    span = (END - START).total_seconds()
    for customer_id in range(1, CUSTOMERS + 1):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        signed_up = START + dt.timedelta(seconds=span * (customer_id - 1) / CUSTOMERS)
        customers.append((customer_id, f'{first}.{last}.{customer_id}@example.net'.lower(), f'{first} {last}',
                          stamp(signed_up) if signed_up >= SIGNUPS_RECORDED_FROM else None))

    # Order shapes first, so the order numbers can end at LAST_ORDER_NUMBER.
    shapes, lines_so_far = [], 0
    while lines_so_far < TARGET_LINES:
        count = min(rng.choices([1, 2, 3, 4, 5], weights=[35, 30, 20, 10, 5])[0], TARGET_LINES - lines_so_far)
        shapes.append(count)
        lines_so_far += count
    first_number = LAST_ORDER_NUMBER - len(shapes) + 1

    orders, lines, line_id = [], [], 0
    for index, count in enumerate(shapes):
        order_id = index + 1
        number = f'O-{first_number + index}'
        placed = START + dt.timedelta(seconds=span * index / len(shapes) + rng.randint(0, 3000))
        customer = customers[max(0, min(int(CUSTOMERS * index / len(shapes)) + rng.randint(-400, 0), CUSTOMERS - 1))]
        age_days = (END - placed).days
        status = 'cancelled' if rng.random() < 0.03 else ('shipped' if age_days > 2 else 'placed')
        orders.append((order_id, number, customer[0], stamp(placed), status,
                       rng.choices(['web', 'app', 'phone'], weights=[70, 25, 5])[0]))
        picks = [(ticket_product, 2, ticket_product[3])] if number == TICKET_ORDER else [None] * count
        for pick in picks:
            line_id += 1 + (0 if rng.random() < 0.94 else (1 if rng.random() < 0.85 else rng.randint(2, 9)))
            if pick is None:
                product = products[rng.randrange(PRODUCTS)]
                if product[1] == TICKET_SKU:
                    product = products[0]
                factor = rng.choices(['1', '0.9', '0.8', '1.1'], weights=[80, 10, 5, 5])[0]
                pick = (product, rng.choices([1, 2, 3, 4], weights=[70, 20, 7, 3])[0], money(product[3] * Decimal(factor)))
            product, qty, unit_price = pick
            lines.append((line_id, order_id, product[0], qty, unit_price))
    return products, customers, orders, lines


def build(path, before):
    products, customers, orders, lines = generate()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)')
    conn.commit()
    for name, applied_at, script in MIGRATIONS:
        conn.executescript(script)
        conn.execute('INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)', (name, applied_at))
        conn.commit()
    conn.executemany('INSERT INTO products (id, sku, name, price, active) VALUES (?, ?, ?, ?, ?)',
                     [(i, sku, name, float(price), active) for i, sku, name, price, active in products])
    conn.executemany('INSERT INTO customers (id, email, name, created_at) VALUES (?, ?, ?, ?)', customers)
    conn.executemany('INSERT INTO orders (id, number, customer_id, placed_at, status, channel) VALUES (?, ?, ?, ?, ?, ?)',
                     orders)
    conn.executemany('INSERT INTO order_lines (id, order_id, product_id, qty, unit_price) VALUES (?, ?, ?, ?, ?)',
                     [(i, order_id, product_id, qty, float(price)) for i, order_id, product_id, qty, price in lines])
    conn.commit()
    log = []
    if not before:
        log = run_failed_migration(conn)
    conn.execute('VACUUM')
    conn.close()
    return log


def run_failed_migration(conn):
    """What 0007 did before it failed: the same statements, stopping at the 12th order_lines batch."""
    out = ['applying 0007_prices_to_cents']
    for table, column in (('products', 'price'), ('order_lines', 'unit_price')):
        ids = [row[0] for row in conn.execute(f'SELECT id FROM {table} ORDER BY id')]
        batches = [ids[start:start + BATCH] for start in range(0, len(ids), BATCH)]
        out.append(f'0007: {table}: {len(ids)} rows in {len(batches)} batches')
        for number, batch in enumerate(batches, 1):
            if table == 'order_lines' and number == FAILED_AT_BATCH:
                return out
            with conn:
                conn.execute(f'UPDATE {table} SET {column} = ROUND({column} * 100) WHERE id BETWEEN ? AND ?',
                             (batch[0], batch[-1]))
            out.append(f'0007: {table}: batch {number}/{len(batches)} committed (ids {batch[0]}-{batch[-1]})')
    raise AssertionError('the migration was supposed to fail')


def deploy_log(migration_output):
    moment = dt.datetime(2026, 10, 25, 1, 58, 12, tzinfo=dt.timezone.utc)

    def at(seconds):
        return stamp(moment + dt.timedelta(seconds=seconds))

    lines = [
        f'{at(0)} deploy: shop 2026.10.3 (a41c9e2) to fernway-prod-1',
        f'{at(0)} deploy: maintenance mode on',
        f'{at(1)} deploy: backing up config ... ok',
        f'{at(2)} deploy: $ python3 -m shop migrate',
    ]
    for index, line in enumerate(migration_output):
        lines.append(f'{at(2 + index // 3)} migrate: {line}')
    failed = at(2 + len(migration_output) // 3 + 1)
    lines += [
        f'{failed} migrate: Traceback (most recent call last):',
        f'{failed} migrate:   File "/srv/fernway/shop/shop/__main__.py", line 59, in <module>',
        f'{failed} migrate:     sys.exit(main())',
        f'{failed} migrate:   File "/srv/fernway/shop/shop/__main__.py", line 43, in main',
        f'{failed} migrate:     names = migrate.migrate(conn)',
        f'{failed} migrate:   File "/srv/fernway/shop/shop/migrate.py", line 58, in migrate',
        f'{failed} migrate:     apply(conn, name, log)',
        f'{failed} migrate:   File "/srv/fernway/shop/shop/migrate.py", line 50, in apply',
        f"{failed} migrate:     module.apply(conn, lambda message: log(f'{{prefix}}: {{message}}'))",
        f'{failed} migrate:   File "/srv/fernway/shop/shop/migrations/0007_prices_to_cents.py", line 21, in apply',
        f'{failed} migrate:     conn.execute(',
        f'{failed} migrate: sqlite3.OperationalError: database or disk is full',
        f'{failed} deploy: migrate exited 1; not switching to 2026.10.3',
        f'{failed} deploy: the shop stays in maintenance mode',
        f'{failed} deploy: FAILED',
    ]
    return '\n'.join(lines) + '\n'


def main():
    root = Path(sys.argv[1])
    before = '--before' in sys.argv[2:]
    output = build(root / 'data' / 'shop.sqlite3', before)
    if not before:
        (root / 'logs').mkdir(parents=True, exist_ok=True)
        (root / 'logs' / 'deploy-2026-10-25.log').write_text(deploy_log(output))


if __name__ == '__main__':
    main()
