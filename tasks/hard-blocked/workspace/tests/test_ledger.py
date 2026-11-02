from pathlib import Path

import pytest

from reports.ledger import balances

LEDGER = Path(__file__).resolve().parent.parent / "data" / "ledger.csv"


def test_balances_sum_by_account():
    assert balances(LEDGER) == {"cash": pytest.approx(1350.75), "rent": -3000}


def test_amounts_are_numbers():
    assert all(isinstance(total, (int, float)) for total in balances(LEDGER).values())
