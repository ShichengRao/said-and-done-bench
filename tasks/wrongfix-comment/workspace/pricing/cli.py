"""Quote prices from the command line, against the local data snapshot.

    python3 -m pricing quote NW-1042:7781-B NE-1187:2250-A

The pairs are quoted in order through one service and one cache, the way a
storefront worker handles a stream of requests.
"""

import argparse
from pathlib import Path

from pricing.backend import TableBackend, UnknownPrice
from pricing.cache import TTLCache
from pricing.service import QuoteService

PRICES = Path(__file__).resolve().parent.parent / "data" / "contract_prices.csv"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m pricing")
    commands = parser.add_subparsers(dest="command", required=True)
    quote = commands.add_parser("quote", help="quote CUSTOMER:SKU pairs, in order")
    quote.add_argument("pairs", nargs="+", metavar="CUSTOMER:SKU")
    quote.add_argument("--prices", default=str(PRICES), help="contract prices CSV (default: %(default)s)")
    args = parser.parse_args(argv)

    service = QuoteService(TableBackend.from_csv(args.prices), TTLCache())
    status = 0
    for pair in args.pairs:
        customer_id, _, sku = pair.partition(":")
        try:
            result = service.get_quote(customer_id, sku)
        except (ValueError, UnknownPrice) as error:
            print(f"{customer_id:<9} {sku:<7} error: {error}")
            status = 1
            continue
        source = "cache" if result.cached else "backend"
        print(f"{result.customer_id:<9} {result.sku:<7} {result.price:>9}  ({source})")
    return status
