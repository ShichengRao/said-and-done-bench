"""stockctl's command line.

    python3 -m stockctl status SKU             a product, its stock, and its last 28 days of sales
    python3 -m stockctl list [--supplier NAME]  every product, with its stock
"""

import argparse
import datetime as dt
import sys

from stockctl import data, render


def status(sku):
    products = data.products()
    if sku not in products:
        print(f'unknown SKU: {sku}', file=sys.stderr)
        return 2
    product = products[sku]
    level = data.stock().get(sku, data.Stock(0, 0))
    sales = [sale for sale in data.sales() if sale.sku == sku]
    last = max((sale.date for sale in data.sales()), default=None)
    recent = sum(sale.qty for sale in sales if last and last - dt.timedelta(days=27) <= sale.date <= last)
    print(f'{product.sku}  {product.name}' + ('  (discontinued)' if product.discontinued else ''))
    print(f'supplier: {product.supplier}, cases of {product.case_size}, lead time {product.lead_time_days} days')
    print(f'on hand: {level.on_hand}, on order: {level.on_order}')
    print(f'sold in the 28 days to {last}: {recent}')
    return 0


def listing(supplier=None):
    products = data.products()
    levels = data.stock()
    rows = [(p.sku, p.name, p.supplier, levels.get(p.sku, data.Stock(0, 0)).on_hand,
             levels.get(p.sku, data.Stock(0, 0)).on_order)
            for p in sorted(products.values(), key=lambda p: p.sku)
            if not supplier or p.supplier == supplier]
    print(render.table(['SKU', 'Name', 'Supplier', 'On hand', 'On order'], rows, right=(3, 4)))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m stockctl')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status', help='a product, its stock, and its recent sales').add_argument('sku')
    commands.add_parser('list', help='every product, with its stock').add_argument('--supplier')
    args = parser.parse_args(argv)
    if args.command == 'status':
        return status(args.sku)
    return listing(args.supplier)


if __name__ == '__main__':
    sys.exit(main())
