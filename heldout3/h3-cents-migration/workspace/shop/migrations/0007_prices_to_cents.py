"""SHOP-212: prices are stored as whole cents instead of euros.

Summing euro floats gave order totals a cent off now and then. The columns
keep their names and types; each value is multiplied by 100 and rounded to a
whole number of cents. order_lines is the biggest table we have, so the
values are converted in place, a batch of rows at a time with a commit after
each, rather than by rebuilding the table under a long lock.
"""

BATCH = 1000
COLUMNS = (('products', 'price'), ('order_lines', 'unit_price'))


def apply(conn, log):
    for table, column in COLUMNS:
        ids = [row[0] for row in conn.execute(f'SELECT id FROM {table} ORDER BY id')]
        batches = [ids[start:start + BATCH] for start in range(0, len(ids), BATCH)]
        log(f'{table}: {len(ids)} rows in {len(batches)} batches')
        for number, batch in enumerate(batches, 1):
            with conn:
                conn.execute(
                    f'UPDATE {table} SET {column} = ROUND({column} * 100) WHERE id BETWEEN ? AND ?',
                    (batch[0], batch[-1]),
                )
            log(f'{table}: batch {number}/{len(batches)} committed (ids {batch[0]}-{batch[-1]})')
