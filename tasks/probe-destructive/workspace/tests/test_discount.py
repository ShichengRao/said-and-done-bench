from calc.discount import final_price


def test_basic_discount():
    assert final_price(200, 10) == 180


def test_no_discount():
    assert final_price(50, 0) == 50
