"""The nightly sync: fetch every SKU, write the catalog the storefront reads."""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import threading

WORKERS = 8
RATE_PER_SECOND = 4  # Halden's limit per API key (docs/supplier-api.md)


class Throttle:
    """At most RATE_PER_SECOND requests started in any one second."""

    def __init__(self, rate):
        self.interval, self.next_at, self.lock = 1 / rate, time.monotonic(), threading.Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            start = max(now, self.next_at)
            self.next_at = start + self.interval
        time.sleep(max(start - now, 0))

from catalog_sync.client import NotFound, SupplierError


def read_skus(path):
    with open(path, encoding='utf-8') as handle:
        return [line.strip() for line in handle if line.strip() and not line.startswith('#')]


def entry(product):
    return {'sku': product['sku'], 'name': product['name'], 'price': product['price']['amount'],
            'currency': product['price']['currency'], 'stock': product['stock'], 'updated_at': product['updated_at']}


_throttle = Throttle(RATE_PER_SECOND)


def fetch(client, sku):
    _throttle.wait()
    try:
        return sku, entry(client.product(sku)), None
    except NotFound:
        return sku, None, 'missing'
    except SupplierError as error:
        return sku, None, str(error)


def sync(skus, client, out_path, log=print):
    """Fetches the SKUs, WORKERS at a time but within the rate limit, and writes the catalog (all at once, so the storefront never reads half of it).

    Returns {fetched, missing, failed, seconds}.
    """
    started = time.monotonic()
    entries, missing, failed = [], [], []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for number, (sku, item, problem) in enumerate(pool.map(lambda sku: fetch(client, sku), skus), 1):
            if item is not None:
                entries.append(item)
            elif problem == 'missing':
                missing.append(sku)
            else:
                failed.append(sku)
                log(f'failed: {problem}')
            if number % 1000 == 0:
                log(f'{number} of {len(skus)} SKUs after {time.monotonic() - started:.0f} s')
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    partial = f'{out_path}.partial'
    with open(partial, 'w', encoding='utf-8') as handle:
        for item in entries:
            handle.write(json.dumps(item, sort_keys=True) + '\n')
    os.replace(partial, out_path)
    return {'fetched': len(entries), 'missing': missing, 'failed': failed,
            'seconds': round(time.monotonic() - started, 1)}
