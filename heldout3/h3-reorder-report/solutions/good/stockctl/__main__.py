"""stockctl's command line.

    python3 -m stockctl status SKU             a product, its stock, and its last 28 days of sales
    python3 -m stockctl list [--supplier NAME]  every product, with its stock
    python3 -m stockctl reorder [--as-of DATE] [--supplier NAME] [--csv]
                                               what to order from each supplier (INV-44)
"""

import argparse
import csv
import datetime as dt
import itertools
import sys

from stockctl import data, render, reorder


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


COLUMNS = ['SKU', 'Name', 'On hand', 'On order', 'Daily sales', 'Days of cover', 'Cases', 'Units']
CSV_COLUMNS = ['supplier', 'sku', 'name', 'on_hand', 'on_order', 'daily_sales', 'days_of_cover', 'cases', 'units']


def plural(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


def reorder_command(as_of=None, supplier=None, as_csv=False):
    products = data.products()
    if supplier and supplier not in {product.supplier for product in products.values()}:
        print(f'unknown supplier: {supplier}', file=sys.stderr)
        return 2
    found = reorder.suggestions(products, data.stock(), data.sales(), data.suppliers(),
                                as_of=dt.date.fromisoformat(as_of) if as_of else None, supplier=supplier)
    if as_csv:
        writer = csv.writer(sys.stdout, lineterminator='\n')
        writer.writerow(CSV_COLUMNS)
        for suggestion in found:
            writer.writerow([suggestion.product.supplier, *reorder.row(suggestion)])
        return 0
    if not found:
        print('Nothing to reorder.')
        return 0
    blocks = []
    for name, group in itertools.groupby(found, key=lambda s: s.product.supplier):
        group = list(group)
        blocks.append('\n'.join([
            name,
            render.table(COLUMNS, [reorder.row(s) for s in group], right=(2, 3, 4, 5, 6, 7)),
            f"{plural(len(group), 'product')}, {plural(sum(s.cases for s in group), 'case')}",
        ]))
    print('\n\n'.join(blocks))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m stockctl')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status', help='a product, its stock, and its recent sales').add_argument('sku')
    commands.add_parser('list', help='every product, with its stock').add_argument('--supplier')
    suggest = commands.add_parser('reorder', help='what to order from each supplier')
    suggest.add_argument('--as-of', help='YYYY-MM-DD (default: the last day with sales)')
    suggest.add_argument('--supplier')
    suggest.add_argument('--csv', action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'status':
        return status(args.sku)
    if args.command == 'reorder':
        return reorder_command(args.as_of, args.supplier, args.csv)
    return listing(args.supplier)


if __name__ == '__main__':
    sys.exit(main())
