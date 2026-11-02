from calc.discount import final_price


# The fix: a percentage is taken off, not subtracted as a flat amount.
def test_half_off():
    assert final_price(50, 50) == 25


def test_quarter_off():
    assert final_price(80, 25) == 60


def test_full_off():
    assert final_price(120, 100) == 0


def test_no_discount():
    assert final_price(50, 0) == 50


# D's feature, which the merge must keep: prices are rounded to whole cents.
def test_rounds_to_cents():
    assert final_price(9.99, 10) == 8.99


def test_rounds_to_cents_again():
    assert final_price(19.99, 15) == 16.99
