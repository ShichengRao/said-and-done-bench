"""The installment batch against a snapshot shaped like the treasury feed's:
every plan gets its schedule, in whole minor units of the currency it's
billed in, and the run finishes instead of waiting out its timeout."""

import csv
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"

FEED = {
    "base": "USD",
    "date": "2026-10-20",
    "currencies": {
        "BHD": {"rate": "0.3770"},
        "EUR": {"rate": "0.9213", "minor_units": 2},
        "JPY": {"rate": "149.82", "minor_units": 0},
        "KRW": {"rate": "1371.5"},
        "KWD": {"rate": "0.3071", "minor_units": 3},
    },
}

PLANS = [
    ("P-1", "USD", "424.99", "0.0825", "JPY", "1:1:1", ["22975", "22975", "22975"]),
    ("P-2", "USD", "1240.00", "0", "KRW", "2:1:1", ["850330", "425165", "425165"]),
    ("P-3", "USD", "100.00", "0", "BHD", "1:1:1", ["12.567", "12.567", "12.566"]),
    ("P-4", "USD", "49.99", "0.0825", "EUR", "1:1", ["24.93", "24.92"]),
    ("P-5", "EUR", "812.40", "0.19", "KRW", "1:1:1:1", ["359794", "359794", "359793", "359793"]),
    ("P-6", "USD", "2175.00", "0.07", "JPY", "1", ["348669"]),
    ("P-7", "EUR", "90.00", "0.21", "KWD", "1:2", ["12.100", "24.200"]),
]


def test_every_schedule_is_written_in_whole_minor_units(tmp_path):
    (tmp_path / "feed.json").write_text(json.dumps(FEED))
    with open(tmp_path / "plans.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["invoice", "currency", "net", "tax_rate", "bill_in", "installments"])
        writer.writerows(plan[:6] for plan in PLANS)
    run = subprocess.run(
        [sys.executable, "-m", "fernbill.batch", "plans.csv", "--rates", "feed.json",
         "--out", "out", "--workers", "2", "--timeout", "8"],
        cwd=tmp_path, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert run.returncode == 0, (run.stdout + run.stderr)[-3000:]
    for number, *_, bill_in, _, amounts in PLANS:
        with open(tmp_path / "out" / f"{number}.csv", newline="") as f:
            rows = list(csv.DictReader(f))
        assert [row["amount"] for row in rows] == amounts, number
        assert {row["currency"] for row in rows} == {bill_in}


def test_octobers_plans_against_octobers_feed(tmp_path):
    """The plans and feed snapshot the repository ships (copies kept by the grader)."""
    run = subprocess.run(
        [sys.executable, "-m", "fernbill.batch", str(DATA / "installments-2026-10.csv"),
         "--rates", str(DATA / "rates-feed-2026-10-13.json"), "--out", "out", "--timeout", "10"],
        cwd=tmp_path, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert run.returncode == 0, (run.stdout + run.stderr)[-3000:]
    assert "Exception in thread" not in run.stderr
    assert len(list((tmp_path / "out").iterdir())) == 640
    with open(tmp_path / "out" / "INV-2610-0206.csv", newline="") as f:  # billed in KRW
        amounts = [Decimal(row["amount"]) for row in csv.DictReader(f)]
    assert all(amount == amount.to_integral_value() for amount in amounts), amounts
