"""LOY-140 repair: recompute every balance from the event log under the README's rules.

Run from the repository root: python3 rebuild_balances.py [--dry-run]
"""

import sqlite3
import sys

DEBITS = ('redeem', 'expire', 'refund')

conn = sqlite3.connect('data/loyalty.sqlite3')
balances, last = {}, {}
for customer, kind, points, at in conn.execute('SELECT customer, kind, points, at FROM events ORDER BY id'):
    change = -points if kind in DEBITS else points
    balances[customer] = max(balances.get(customer, 0) + change, 0)
    last[customer] = at
stored = dict(conn.execute('SELECT customer, points FROM balances'))
wrong = sorted(c for c in balances if stored.get(c) != balances[c])
print(f'{len(wrong)} balances differ from their events')
for customer in wrong:
    print(f'  {customer}: {stored.get(customer)} -> {balances[customer]}')
if '--dry-run' not in sys.argv:
    with conn:
        conn.executemany('UPDATE balances SET points = ? WHERE customer = ?',
                         [(balances[c], c) for c in wrong])
    print('updated')
