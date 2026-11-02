"""OPS-77: finish 0007 from where the deploy left off.

0007 commits each batch as it goes and isn't safe to run twice (it multiplies
by 100 again), so `migrate` can't simply be run again. The deploy log names
the last order_lines batch that committed; the batch after it rolled back.
Convert only the rows after it, the way 0007 does, then record 0007 as
applied so the next deploy doesn't run it.

Run from the repository root: python3 resume.py [--no-record]
"""

import re
import sqlite3
import subprocess
import sys

log = open('logs/deploy-2026-10-25.log').read()
assert 'products: batch 3/3 committed' in log, 'expected every product batch to have committed'
last = max(int(found.group(1)) for found in
           re.finditer(r'order_lines: batch \d+/\d+ committed \(ids \d+-(\d+)\)', log))
conn = sqlite3.connect('data/shop.sqlite3')
with conn:
    converted = conn.execute('UPDATE order_lines SET unit_price = ROUND(unit_price * 100) WHERE id > ?',
                             (last,)).rowcount
conn.close()
print(f'converted {converted} order lines after id {last}', flush=True)
if '--no-record' not in sys.argv:
    subprocess.run([sys.executable, '-m', 'shop', 'migrate', '--fake', '0007_prices_to_cents'], check=True)
