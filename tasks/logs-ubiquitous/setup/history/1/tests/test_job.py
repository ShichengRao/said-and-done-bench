import csv
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from exporter.db import ConnectionPool
from exporter.feed import COLUMNS, FeedFile
from exporter.job import run_export

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DAY = date(2026, 1, 14)
SAMPLE_FEED = ROOT / "samples" / "feed-2026-01-14.csv"


def sample_total():
    with open(ROOT / "samples" / "ledger-totals.csv", newline="") as f:
        return next(Decimal(r["total"]) for r in csv.DictReader(f) if r["date"] == SAMPLE_DAY.isoformat())


def pool_for(feed):
    return ConnectionPool(lambda: FeedFile(feed), size=1, acquire_timeout=0.1, attempts=2, backoff=0)


def exported(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def write_feed(path, rows):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    return path


def test_sample_night_exports_and_reconciles(tmp_path):
    result = run_export(SAMPLE_DAY, pool_for(SAMPLE_FEED), sample_total(), tmp_path)
    assert (result.status, result.exit_code) == ("ok", 0)
    rows = exported(result.path)
    assert result.path.name == "ledger-2026-01-14.csv"
    assert len(rows) == result.rows > 200
    assert len({r["invoice_no"] for r in rows}) == len(rows)
    assert sum(Decimal(r["amount"]) for r in rows) == sample_total()


def test_a_total_that_doesnt_match_fails_the_run(tmp_path):
    result = run_export(SAMPLE_DAY, pool_for(SAMPLE_FEED), sample_total() + Decimal("0.01"), tmp_path)
    assert (result.status, result.exit_code) == ("failed", 2)


def test_local_run_from_the_command_line(tmp_path):
    run = subprocess.run(
        [sys.executable, "-m", "exporter", "--date", "2026-01-14", "--feed", str(SAMPLE_FEED),
         "--ledger-totals", str(ROOT / "samples" / "ledger-totals.csv"), "--out", str(tmp_path)],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert run.returncode == 0, run.stderr
    assert "run finished status=ok exit=0" in run.stderr
    assert (tmp_path / "ledger-2026-01-14.csv").exists()
