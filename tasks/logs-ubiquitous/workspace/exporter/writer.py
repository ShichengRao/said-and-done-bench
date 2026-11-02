"""The file Northgate imports: one CSV per business day (see docs/partner-format.md)."""

import csv
import logging
from datetime import date
from pathlib import Path

from exporter.feed import FeedRow

log = logging.getLogger(__name__)

HEADER = ["invoice_no", "invoice_date", "customer_id", "amount", "currency"]


def export_name(export_date: date) -> str:
    return f"ledger-{export_date.isoformat()}.csv"


def write_export(rows: list[FeedRow], out_dir, export_date: date) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / export_name(export_date)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for row in rows:
            writer.writerow([row.invoice_no, row.invoice_date.isoformat(), row.customer_id, f"{row.total:.2f}", row.currency])
    log.info("wrote %s (%d rows, %.1f KB)", path.name, len(rows), path.stat().st_size / 1024)
    return path
