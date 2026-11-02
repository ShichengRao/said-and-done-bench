import pytest

from tallyboard.money import format_cents


@pytest.mark.parametrize(
    ("cents", "text"),
    [(0, "$0.00"), (5, "$0.05"), (1_999, "$19.99"), (1_234_567, "$12,345.67"), (-2_400, "-$24.00")],
)
def test_format_cents(cents, text):
    assert format_cents(cents) == text
