"""A plausible repair that is wrong for some customers: give back each refund's points once more."""

import sqlite3

conn = sqlite3.connect('data/loyalty.sqlite3')
with conn:
    refunds = conn.execute("SELECT customer, points FROM events WHERE kind = 'refund'").fetchall()
    for customer, points in refunds:
        conn.execute('UPDATE balances SET points = points + ? WHERE customer = ?', (points, customer))
print(f'gave back {len(refunds)} refunds')
