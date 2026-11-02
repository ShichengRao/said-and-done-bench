"""`python3 -m tallyboard.cli EXPORT [--title TITLE] [--by-product] [--plugins DIR]`: print a report."""

from __future__ import annotations

import argparse
import sys

from tallyboard import regions
from tallyboard.records import parse_rows
from tallyboard.report import render, render_products


def main(argv=None, stdin=None, stdout=None) -> int:
    parser = argparse.ArgumentParser(prog="tallyboard")
    parser.add_argument("export", help="the store export, or - for standard input")
    parser.add_argument("--title")
    parser.add_argument("--by-product", action="store_true")
    parser.add_argument("--plugins", help="a directory of region plugins to load first")
    args = parser.parse_args(argv)
    stdout = stdout or sys.stdout
    if args.plugins:
        regions.load_plugins(args.plugins)
    try:
        if args.export == "-":
            lines = (stdin or sys.stdin).read().splitlines()
        else:
            with open(args.export, encoding="utf-8") as export:
                lines = export.read().splitlines()
    except OSError as error:
        print(f"tallyboard: {error}", file=sys.stderr)
        return 2
    sales = parse_rows(lines)
    draw = render_products if args.by_product else render
    stdout.write(draw(sales, **({"title": args.title} if args.title else {})))
    return 0


if __name__ == "__main__":
    sys.exit(main())
