"""The nightly export: one business day's invoices from the ledger feed to Northgate.

Northgate's import is only trusted if the file adds up, so before uploading
the job reconciles the file's total against the ledger's own total for the
day. A mismatch fails the run (exit 2) and nothing is uploaded; finance then
reruns the export by hand. A feed that stops sending rows fails the run with
exit 3, which exp-worker retries once.
"""

import logging
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from exporter.db import ConnectionPool
from exporter.dedupe import drop_redelivered
from exporter.prefetch import FeedTimeout, Prefetcher
from exporter.writer import write_export

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunResult:
    status: str  # "ok" or "failed"
    exit_code: int
    rows: int
    total: Decimal
    path: Path | None


def run_export(export_date: date, pool: ConnectionPool, ledger_total: Decimal, out_dir, upload=None,
               page_size: int = 100, page_timeout: float = 600.0) -> RunResult:
    """Export the invoices dated export_date. upload(path) sends the file; None skips it (local runs).

    page_size and page_timeout come from [feed] in config/export.toml.
    """
    started = time.monotonic()
    log.info("export date %s", export_date.isoformat())

    def finish(status, exit_code, rows, total=Decimal("0.00"), path=None):
        log.info(
            "run finished status=%s exit=%d rows=%d duration=%.2fs",
            status, exit_code, rows, time.monotonic() - started,
        )
        return RunResult(status, exit_code, rows, total, path)

    with pool.connection() as conn:
        log.info("reading the feed in pages of %d rows", page_size)
        feed = Prefetcher(conn, export_date, page_size, page_timeout).start()
        try:
            rows = feed.rows()
        except FeedTimeout as error:
            log.error("feed timed out: %s", error)
            return finish("failed", 3, error.rows)
    log.info("fetched %d invoice rows in %d pages", len(rows), feed.pages)
    rows = drop_redelivered(rows)

    path = write_export(rows, out_dir, export_date)
    total = sum((row.total for row in rows), Decimal("0.00"))

    if total != Decimal(ledger_total):
        log.error("reconcile: exported total %s does not match ledger total %s", total, ledger_total)
        log.info("upload skipped: reconciliation failed")
        return finish("failed", 2, len(rows), total, path)
    log.info("reconcile: exported total %s matches the ledger", total)

    if upload is None:
        log.info("upload skipped: local run")
    else:
        upload(path)
    return finish("ok", 0, len(rows), total, path)
