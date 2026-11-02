"""The ledger's invoice feed (see docs/ledger-feed.md).

In production a connection reads the feed from the ledger replica. Locally,
FeedFile reads the same rows from a CSV export of the feed.
"""

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

COLUMNS = ["feed_seq", "row_id", "invoice_no", "invoice_date", "customer_id", "total", "currency"]


@dataclass(frozen=True)
class FeedRow:
    feed_seq: int
    row_id: str
    invoice_no: str
    invoice_date: date
    customer_id: str
    total: Decimal
    currency: str


def parse_row(record: dict) -> FeedRow:
    return FeedRow(
        feed_seq=int(record["feed_seq"]),
        row_id=record["row_id"],
        invoice_no=record["invoice_no"],
        invoice_date=date.fromisoformat(record["invoice_date"]),
        customer_id=record["customer_id"],
        total=Decimal(record["total"]),
        currency=record["currency"],
    )


class FeedFile:
    """A connection that reads the feed from a CSV file."""

    def __init__(self, path):
        self.path = Path(path)

    def fetch_invoices(self, invoice_date: date) -> list[FeedRow]:
        """The day's rows in feed order."""
        with open(self.path, newline="", encoding="utf-8") as f:
            rows = [parse_row(record) for record in csv.DictReader(f)]
        return sorted((row for row in rows if row.invoice_date == invoice_date), key=lambda row: row.feed_seq)
