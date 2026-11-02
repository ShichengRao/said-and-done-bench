from shop.money import cents, euros


def test_euros():
    assert euros(0) == '€0.00'
    assert euros(5) == '€0.05'
    assert euros(2499) == '€24.99'
    assert euros(1234567) == '€12,345.67'
    assert euros(-150) == '-€1.50'


def test_cents_from_a_stored_value():
    assert cents(2499.0) == 2499
    assert cents(2499) == 2499
    assert cents(2498.9999999) == 2499
