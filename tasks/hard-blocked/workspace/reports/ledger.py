"""Balances per account from a ledger CSV with `account` and `amount` columns."""

from collections import defaultdict

from quillcsv import read_rows


def balances(path) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for row in read_rows(path):
        totals[row["account"]] += row["amount"]
    return dict(totals)
