"""The sync's command line (cron runs `python3 -m catalog_sync run` at 02:00).

    python3 -m catalog_sync run [--limit N] [--out PATH]

--limit syncs only the first N SKUs (for trying it out).
CATALOG_SUPPLIER_URL and CATALOG_SUPPLIER_KEY say where the supplier is.
"""

import argparse
import sys

from catalog_sync import settings
from catalog_sync.client import SupplierClient
from catalog_sync.sync import read_skus, sync


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m catalog_sync')
    commands = parser.add_subparsers(dest='command', required=True)
    running = commands.add_parser('run', help='sync every SKU')
    running.add_argument('--limit', type=int, help='only the first N SKUs')
    running.add_argument('--out', default=str(settings.OUT_FILE))
    args = parser.parse_args(argv)
    skus = read_skus(settings.SKU_FILE)
    if args.limit:
        skus = skus[:args.limit]
    result = sync(skus, SupplierClient(), args.out, log=lambda message: print(message, flush=True))
    print(f"synced {result['fetched']} of {len(skus)} SKUs in {result['seconds']} s "
          f"({len(result['missing'])} unknown, {len(result['failed'])} failed)")
    return 1 if result['failed'] else 0


if __name__ == '__main__':
    sys.exit(main())
