from meter_billing.pricing import progressive_millicents

TIERS = [{'up_to': 5, 'millicents': 1000}, {'up_to': None, 'millicents': 250}]


def test_progressive_tiers_apply_once_to_total():
    assert progressive_millicents(0, TIERS) == 0
    assert progressive_millicents(5, TIERS) == 5000
    assert progressive_millicents(17, TIERS) == 5000 + 12 * 250
