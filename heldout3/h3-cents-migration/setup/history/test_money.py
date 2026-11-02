from shop.money import euros


def test_euros():
    assert euros(0) == '€0.00'
    assert euros(24.99) == '€24.99'
    assert euros(12345.6) == '€12,345.60'
    assert euros(-1.5) == '-€1.50'
