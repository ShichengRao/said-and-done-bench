"""The installment batch, on a few invoices and a small snapshot of the feed."""

import csv
from decimal import Decimal

from fernbill.batch import read_plans, run, schedule
from fernbill.rates import RateTable

SNAPSHOT = {
    "base": "USD",
    "date": "2026-10-13",
    "currencies": {
        "CHF": {"rate": "0.8652"},
        "EUR": {"rate": "0.9213", "minor_units": 2},
        "GBP": {"rate": "0.7841"},
    },
}

PLANS = """\
invoice,currency,net,tax_rate,bill_in,installments
INV-1,USD,360.00,0.0825,USD,1:1:1
INV-2,USD,49.99,0.0825,EUR,1:1
INV-3,EUR,1000.00,0.19,GBP,2:1:1
INV-4,USD,15.00,0,CHF,1
"""


def plans(tmp_path):
    path = tmp_path / "plans.csv"
    path.write_text(PLANS, encoding="utf-8")
    return read_plans(path)


def test_reads_one_plan_per_invoice(tmp_path):
    read = plans(tmp_path)
    assert [plan.number for plan in read] == ["INV-1", "INV-2", "INV-3", "INV-4"]
    assert read[2].bill_in == "GBP" and read[2].weights == (2, 1, 1)
    assert read[2].invoice.total() == Decimal("1190.00")


def test_schedule_splits_the_converted_total(tmp_path):
    table = RateTable.from_snapshot(SNAPSHOT)
    first, second, third, fourth = plans(tmp_path)
    assert schedule(first, table) == [
        (1, Decimal("129.90")), (2, Decimal("129.90")), (3, Decimal("129.90")),
    ]
    assert schedule(second, table) == [(1, Decimal("24.93")), (2, Decimal("24.92"))]
    assert schedule(third, table) == [
        (1, Decimal("506.39")), (2, Decimal("253.20")), (3, Decimal("253.20")),
    ]
    assert schedule(fourth, table) == [(1, Decimal("12.98"))]


def test_run_writes_a_schedule_per_invoice(tmp_path):
    out = tmp_path / "out"
    status = run(plans(tmp_path), RateTable.from_snapshot(SNAPSHOT), out, workers=2, timeout=10,
                 log=lambda line: None)
    assert status == 0
    assert sorted(path.name for path in out.iterdir()) == [
        "INV-1.csv", "INV-2.csv", "INV-3.csv", "INV-4.csv",
    ]
    with open(out / "INV-3.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [row["amount"] for row in rows] == ["506.39", "253.20", "253.20"]
    assert {row["currency"] for row in rows} == {"GBP"}
