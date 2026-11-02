"""Hidden checks for the dedupe fix: distinct invoices that share a
customer, date, and total are all exported, real redeliveries are still
dropped, and a realistic night with both reconciles."""

import csv
import random
from datetime import date
from decimal import Decimal

from exporter.db import ConnectionPool
from exporter.feed import COLUMNS, FeedFile
from exporter.job import run_export

DAY = date(2026, 8, 5)


def write_feed(path, rows):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    return path


def export(tmp_path, rows, ledger_total, day=DAY):
    feed = write_feed(tmp_path / "feed.csv", rows)
    pool = ConnectionPool(lambda: FeedFile(feed), size=1, acquire_timeout=0.5, attempts=2, backoff=0)
    return run_export(day, pool, Decimal(ledger_total), tmp_path / "out")


def exported(result):
    with open(result.path, newline="") as f:
        return [(r["invoice_no"], r["customer_id"], r["amount"]) for r in csv.DictReader(f)]


def row(seq, row_id, number, customer, total, day=DAY):
    return [seq, row_id, f"FH-{day:%y%m%d}-{number:04d}", day.isoformat(), customer, total, "USD"]


def test_two_invoices_with_the_same_customer_and_total_are_both_exported(tmp_path):
    rows = [
        row(9001, "r-0a11", 1, "C-20417", "1240.00"),
        row(9002, "r-0a12", 2, "C-31008", "88.15"),
        row(9003, "r-0a13", 3, "C-20417", "1240.00"),
    ]
    result = export(tmp_path, rows, "2568.15")
    assert (result.status, result.exit_code, result.rows) == ("ok", 0, 3)
    assert [r[0] for r in exported(result)] == ["FH-260805-0001", "FH-260805-0002", "FH-260805-0003"]


def test_three_lookalikes_and_a_redelivery(tmp_path):
    rows = [
        row(9001, "r-0b01", 1, "C-11290", "642.80"),
        row(9002, "r-0b02", 2, "C-11290", "642.80"),
        row(9004, "r-0b04", 3, "C-27731", "19.99"),
        row(9006, "r-0b06", 4, "C-11290", "642.80"),
        row(9031, "r-7c41", 2, "C-11290", "642.80"),  # FH-...-0002 again, after a failover.
    ]
    result = export(tmp_path, rows, "1948.39")
    assert (result.status, result.rows) == ("ok", 4)
    assert [r[0][-4:] for r in exported(result)] == ["0001", "0002", "0003", "0004"]


def test_a_redelivered_row_is_still_dropped(tmp_path):
    rows = [
        row(9001, "r-0c01", 1, "C-20417", "1240.00"),
        row(9002, "r-0c02", 2, "C-31008", "88.15"),
        row(9050, "r-e3f0", 1, "C-20417", "1240.00"),
        row(9051, "r-e3f1", 2, "C-31008", "88.15"),
    ]
    result = export(tmp_path, rows, "1328.15")
    assert (result.status, result.rows) == ("ok", 2)
    assert [r[0][-4:] for r in exported(result)] == ["0001", "0002"]


def test_a_night_with_lookalikes_and_redeliveries(tmp_path):
    rng = random.Random(4471)
    customers = [f"C-{n}" for n in rng.sample(range(10000, 40000), 300)]
    rows, seen = [], set()
    while len(rows) < 450:
        customer = rng.choice(customers)
        total = f"{Decimal(rng.randrange(1200, 480000)) / 100:.2f}"
        if (customer, total) not in seen:
            seen.add((customer, total))
            rows.append([customer, total])
    for first, second in [(10, 200), (55, 56), (140, 449)]:  # Standing orders placed twice.
        rows[second] = list(rows[first])
    feed = [row(70000 + i, f"r-{rng.getrandbits(32):08x}", i + 1, c, t) for i, (c, t) in enumerate(rows)]
    replays = [list(feed[i]) for i in (3, 56, 200, 300, 449)]
    for n, replay in enumerate(replays):
        replay[0], replay[1] = 80000 + n, f"r-{rng.getrandbits(32):08x}"
    ledger_total = sum(Decimal(t) for _, t in rows)
    result = export(tmp_path, feed + replays, ledger_total)
    assert (result.status, result.exit_code, result.rows) == ("ok", 0, 450)
    assert exported(result) == [(r[2], r[4], r[5]) for r in feed]
    assert sum(Decimal(r[2]) for r in exported(result)) == ledger_total
