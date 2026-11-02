from decimal import Decimal

import pytest

from fernbill.invoice import Invoice, LineItem


def consulting():
    return Invoice("USD", [
        LineItem("Consulting", Decimal("3"), Decimal("120.00"), Decimal("0.0825")),
        LineItem("Hosting", Decimal("1"), Decimal("49.99"), Decimal("0.0825")),
        LineItem("Setup fee", Decimal("1"), Decimal("15.00")),
    ])


def test_subtotal():
    assert consulting().subtotal() == Decimal("424.99")


def test_tax_is_rounded_per_line():
    assert consulting().tax() == Decimal("33.82")


def test_total():
    assert consulting().total() == Decimal("458.81")


def test_empty_invoice_totals_zero():
    assert Invoice("USD").total() == Decimal("0")


def test_yen_lines_round_to_whole_yen():
    invoice = Invoice("JPY", [LineItem("Widget", Decimal("3"), Decimal("333.5"), Decimal("0.1"))])
    assert invoice.subtotal() == Decimal("1001")
    assert invoice.tax() == Decimal("100")


def test_repr():
    assert repr(consulting()) == "Invoice('USD', 3 lines)"


def test_total_in_same_currency(rates):
    assert consulting().total_in("USD", rates) == Decimal("458.81")


def test_total_in_eur(rates):
    assert consulting().total_in("EUR", rates) == Decimal("422.70")


def test_total_in_jpy(rates):
    assert consulting().total_in("JPY", rates) == Decimal("68739")


def test_rejects_a_bad_currency_code():
    with pytest.raises(ValueError):
        Invoice("usd")


def test_discount_applies_before_tax():
    line = LineItem("Licence", Decimal("2"), Decimal("500.00"), Decimal("0.0825"), Decimal("0.15"))
    invoice = Invoice("USD", [line])
    assert invoice.subtotal() == Decimal("850.00")
    assert invoice.tax() == Decimal("70.13")


def test_no_discount_by_default():
    assert LineItem("Pen", Decimal("1"), Decimal("2.50")).net("USD") == Decimal("2.50")


def test_credit_note_cancels_the_invoice():
    invoice = consulting()
    assert invoice.credit_note().total() == -invoice.total()


def test_credit_note_keeps_the_currency():
    assert consulting().credit_note().currency == "USD"


def test_summary():
    assert consulting().summary() == {
        "currency": "USD", "lines": 3, "subtotal": "424.99", "tax": "33.82", "total": "458.81",
    }
