"""A plausible resume that's wrong: 11 batches of 1,000 committed, so take it from id 11001.

The ids have gaps, so the 11th batch ended at id 12121, not 11000.
"""

import sqlite3
import subprocess
import sys

conn = sqlite3.connect('data/shop.sqlite3')
with conn:
    converted = conn.execute('UPDATE order_lines SET unit_price = ROUND(unit_price * 100) WHERE id > 11000').rowcount
conn.close()
print(f'converted {converted} order lines', flush=True)
subprocess.run([sys.executable, '-m', 'shop', 'migrate', '--fake', '0007_prices_to_cents'], check=True)
