import pytest

from pricing.ids import check_customer_id, check_sku


@pytest.mark.parametrize("value", ["NW-1042", "SE-2290", "MW-1003"])
def test_customer_ids(value):
    assert check_customer_id(value) == value


@pytest.mark.parametrize("value", ["nw-1042", "NW1042", "NW-104", "NW-10427", "N-1042", "NW-1042 ", ""])
def test_bad_customer_ids(value):
    with pytest.raises(ValueError):
        check_customer_id(value)


@pytest.mark.parametrize("value", ["781-B", "7781-B", "2250-A"])
def test_skus(value):
    assert check_sku(value) == value


@pytest.mark.parametrize("value", ["7781B", "77-B", "77810-B", "7781-b", "7781-BB"])
def test_bad_skus(value):
    with pytest.raises(ValueError):
        check_sku(value)
