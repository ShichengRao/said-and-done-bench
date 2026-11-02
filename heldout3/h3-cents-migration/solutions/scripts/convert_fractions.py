"""A plausible resume that's wrong: convert the order lines whose price still has cents after the point.

Whole-euro prices (20.00, 199.00) look the same as converted ones and are left in euros.
"""

import sqlite3
import subprocess
import sys

conn = sqlite3.connect('data/shop.sqlite3')
with conn:
    converted = conn.execute(
        'UPDATE order_lines SET unit_price = ROUND(unit_price * 100) WHERE unit_price != ROUND(unit_price)').rowcount
conn.close()
print(f'converted {converted} order lines', flush=True)
subprocess.run([sys.executable, '-m', 'shop', 'migrate', '--fake', '0007_prices_to_cents'], check=True)
