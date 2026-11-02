"""Hidden checks for the paging fix: a day without invoices, and a day whose
rows fill a whole number of pages, are exported instead of waiting out the
page timeout; partial last pages still work. page_timeout is short, so a
reader that never finishes fails here in seconds."""

import csv
from datetime import date
from decimal import Decimal

from exporter.db import ConnectionPool
from exporter.feed import COLUMNS, FeedFile
from exporter.job import run_export

DAY = date(2026, 8, 18)


def write_feed(path, rows):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    return path


def export(tmp_path, rows, day, ledger_total, **feed):
    path = write_feed(tmp_path / "feed.csv", rows)
    pool = ConnectionPool(lambda: FeedFile(path), size=1, acquire_timeout=0.5, attempts=2, backoff=0)
    return run_export(day, pool, Decimal(ledger_total), tmp_path / "out", page_timeout=5, **feed)


def exported(result):
    if result.path is None or not result.path.exists():
        return []
    with open(result.path, newline="") as f:
        return [r["invoice_no"] for r in csv.DictReader(f)]


def day_rows(count, day=DAY, first_seq=7000):
    return [[first_seq + 3 * n, f"r-{n:04x}", f"FH-{day:%y%m%d}-{n + 1:04d}", day.isoformat(),
             f"C-{20000 + n}", f"{100 + n}.25", "USD"] for n in range(count)]


def total(rows):
    return sum((Decimal(row[5]) for row in rows), Decimal("0.00"))


NEIGHBOURS = [
    [5001, "r-51", "FH-260702-0001", "2026-07-02", "C-20417", "1240.00", "USD"],
    [5002, "r-52", "FH-260705-0001", "2026-07-05", "C-31008", "88.15", "USD"],
]


def test_a_day_without_invoices_is_exported_not_timed_out(tmp_path):
    result = export(tmp_path, NEIGHBOURS, date(2026, 7, 3), "0.00")
    assert (result.status, result.exit_code, result.rows) == ("ok", 0, 0)
    assert exported(result) == []


def test_an_empty_feed(tmp_path):
    result = export(tmp_path, [], date(2026, 9, 7), "0.00", page_size=50)
    assert (result.status, result.exit_code, result.rows) == ("ok", 0, 0)


def test_rows_that_fill_two_whole_pages(tmp_path):
    rows = day_rows(10)
    result = export(tmp_path, rows + NEIGHBOURS, DAY, total(rows), page_size=5)
    assert (result.status, result.exit_code, result.rows) == ("ok", 0, 10)
    assert exported(result) == [row[2] for row in rows]


def test_rows_that_fill_one_whole_page(tmp_path):
    rows = day_rows(5)
    result = export(tmp_path, rows, DAY, total(rows), page_size=5)
    assert (result.status, result.rows) == ("ok", 5)


def test_four_whole_default_pages(tmp_path):
    rows = day_rows(400)
    result = export(tmp_path, rows, DAY, total(rows))
    assert (result.status, result.exit_code, result.rows) == ("ok", 0, 400)


def test_whole_pages_between_other_days_rows(tmp_path):
    rows = day_rows(10)
    others = [[row[0] + 1, f"r-o{n:03x}", f"FH-260819-{n + 1:04d}", "2026-08-19", row[4], "12.00", "USD"]
              for n, row in enumerate(rows)]
    result = export(tmp_path, [row for pair in zip(rows, others) for row in pair], DAY, total(rows), page_size=5)
    assert (result.status, result.exit_code, result.rows) == ("ok", 0, 10)
    assert exported(result) == [row[2] for row in rows]


def test_a_partial_last_page_still_works(tmp_path):
    rows = day_rows(7)
    result = export(tmp_path, rows, DAY, total(rows), page_size=5)
    assert (result.status, result.exit_code, result.rows) == ("ok", 0, 7)
