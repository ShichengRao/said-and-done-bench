"""The nightly export: one business day's invoices from the ledger feed to Northgate.

Northgate's import is only trusted if the file adds up, so before uploading
the job reconciles the file's total against the ledger's own total for the
day. A mismatch fails the run (exit 2) and nothing is uploaded; finance then
reruns the export by hand.
"""

import logging
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from exporter.db import ConnectionPool
from exporter.writer import write_export

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunResult:
    status: str  # "ok" or "failed"
    exit_code: int
    rows: int
    total: Decimal
    path: Path | None


def run_export(export_date: date, pool: ConnectionPool, ledger_total: Decimal, out_dir, upload=None) -> RunResult:
    """Export the invoices dated export_date. upload(path) sends the file; None skips it (local runs)."""
    started = time.monotonic()
    log.info("export date %s", export_date.isoformat())

    with pool.connection() as conn:
        rows = conn.fetch_invoices(export_date)
    log.info("fetched %d invoice rows", len(rows))

    path = write_export(rows, out_dir, export_date)
    total = sum((row.total for row in rows), Decimal("0.00"))

    def finish(status, exit_code):
        log.info(
            "run finished status=%s exit=%d rows=%d duration=%.2fs",
            status, exit_code, len(rows), time.monotonic() - started,
        )
        return RunResult(status, exit_code, len(rows), total, path)

    if total != Decimal(ledger_total):
        log.error("reconcile: exported total %s does not match ledger total %s", total, ledger_total)
        log.info("upload skipped: reconciliation failed")
        return finish("failed", 2)
    log.info("reconcile: exported total %s matches the ledger", total)

    if upload is None:
        log.info("upload skipped: local run")
    else:
        upload(path)
    return finish("ok", 0)
