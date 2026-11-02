from decimal import Decimal

from fernbill.format import format_amount


def test_groups_thousands():
    assert format_amount(Decimal("1234.5"), "USD") == "1,234.50 USD"


def test_zero_decimal_currency():
    assert format_amount(Decimal("1849"), "JPY") == "\u00a51,849"


def test_three_decimal_currency():
    assert format_amount(Decimal("12.3454"), "BHD") == "12.345 BHD"


def test_negative_amount():
    assert format_amount(Decimal("-5"), "CHF") == "-5.00 CHF"


def test_rounds_half_up():
    assert format_amount(Decimal("0.125"), "USD") == "0.13 USD"


def test_symbol_before_the_amount():
    assert format_amount(Decimal("1234.5"), "EUR") == "\u20ac1,234.50"
    assert format_amount(Decimal("-9.99"), "GBP") == "-\u00a39.99"


def test_won_has_no_decimals():
    assert format_amount(Decimal("25000"), "KRW") == "\u20a925,000"
