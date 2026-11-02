"""Reporting helpers over the reference exchange-rate table."""

import csv
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "rates.csv"


def load_rates(path=DATA):
    with open(path, newline="") as handle:
        return [(row["currency"], float(row["rate"])) for row in csv.DictReader(handle)]


def average_rate(path=DATA):
    rates = load_rates(path)
    return round(sum(rate for _, rate in rates) / len(rates), 4)
