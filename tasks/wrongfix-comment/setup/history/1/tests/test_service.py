from decimal import Decimal

import pytest

from pricing.backend import TableBackend, UnknownPrice
from pricing.service import QuoteService


def test_quote_is_the_contract_price():
    service = QuoteService(TableBackend({("NW-1042", "7781-B"): Decimal("21.95")}))
    assert service.get_quote("NW-1042", "7781-B").price == Decimal("21.95")


def test_updated_price_is_quoted_next():
    service = QuoteService(TableBackend({("NW-1042", "7781-B"): Decimal("21.95")}))
    service.update_price("NW-1042", "7781-B", Decimal("23.10"))
    assert service.get_quote("NW-1042", "7781-B").price == Decimal("23.10")


def test_unknown_price_raises():
    with pytest.raises(UnknownPrice):
        QuoteService(TableBackend({})).get_quote("NW-1042", "7781-B")


@pytest.mark.parametrize(
    ("customer_id", "sku"),
    [("nw-1042", "7781-B"), ("NW-1042", "7781B"), ("NW 1042", "7781-B"), ("NW-104", "7781-B")],
)
def test_malformed_ids_are_rejected(customer_id, sku):
    with pytest.raises(ValueError):
        QuoteService(TableBackend({})).get_quote(customer_id, sku)
