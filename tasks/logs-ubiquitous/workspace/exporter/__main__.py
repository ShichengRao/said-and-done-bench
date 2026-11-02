"""Run the export locally, against a CSV copy of the ledger feed.

    python3 -m exporter --date 2026-01-14 --feed samples/feed-2026-01-14.csv \\
        --ledger-totals samples/ledger-totals.csv

In production exp-worker calls exporter.job.run_export() itself, with its
shared replica pool and its uploader; nothing is uploaded from a local run.
"""

import argparse
import csv
import logging
import sys
import tomllib
from datetime import date
from decimal import Decimal
from pathlib import Path

from exporter import __version__, logsetup
from exporter.db import ConnectionPool
from exporter.feed import FeedFile
from exporter.job import run_export

CONFIG = Path(__file__).resolve().parent.parent / "config" / "export.toml"
log = logging.getLogger("exporter")


def ledger_total(path, export_date: date) -> Decimal:
    with open(path, newline="", encoding="utf-8") as f:
        for record in csv.DictReader(f):
            if record["date"] == export_date.isoformat():
                return Decimal(record["total"])
    raise SystemExit(f"{path} has no ledger total for {export_date}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m exporter", description=__doc__.splitlines()[0])
    parser.add_argument("--date", required=True, type=date.fromisoformat, help="the business day to export")
    parser.add_argument("--feed", required=True, help="CSV copy of the ledger feed")
    parser.add_argument("--ledger-totals", required=True, help="CSV of the ledger's daily totals (date,total)")
    parser.add_argument("--out", default="out", help="where to write the export (default: %(default)s)")
    parser.add_argument("--config", default=str(CONFIG), help="settings (default: %(default)s)")
    args = parser.parse_args(argv)

    logsetup.configure()
    with open(args.config, "rb") as f:
        settings = tomllib.load(f)
    log.info("nightly-export %s, local run", __version__)
    pool = ConnectionPool(lambda: FeedFile(args.feed), **settings["pool"])
    result = run_export(args.date, pool, ledger_total(args.ledger_totals, args.date), args.out, **settings.get("feed", {}))
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
