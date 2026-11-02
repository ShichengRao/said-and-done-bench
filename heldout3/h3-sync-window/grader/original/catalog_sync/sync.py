"""The nightly sync: fetch every SKU, write the catalog the storefront reads."""

import json
import os
import time

from catalog_sync.client import NotFound, SupplierError


def read_skus(path):
    with open(path, encoding='utf-8') as handle:
        return [line.strip() for line in handle if line.strip() and not line.startswith('#')]


def entry(product):
    return {'sku': product['sku'], 'name': product['name'], 'price': product['price']['amount'],
            'currency': product['price']['currency'], 'stock': product['stock'], 'updated_at': product['updated_at']}


def sync(skus, client, out_path, log=print):
    """Fetches each SKU in turn and writes the catalog (all at once, so the storefront never reads half of it).

    Returns {fetched, missing, failed, seconds}.
    """
    started = time.monotonic()
    entries, missing, failed = [], [], []
    for number, sku in enumerate(skus, 1):
        try:
            entries.append(entry(client.product(sku)))
        except NotFound:
            missing.append(sku)
        except SupplierError as error:
            failed.append(sku)
            log(f'failed: {error}')
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
