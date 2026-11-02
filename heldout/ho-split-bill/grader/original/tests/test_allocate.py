from costsplit.allocate import allocate


def test_an_amount_that_divides_exactly():
    assert allocate(10000, [50, 30, 20]) == [5000, 3000, 2000]


def test_shares_add_up():
    for total in (1, 7, 99, 100, 101, 12345):
        for weights in ([1, 1, 1], [3, 1], [5, 0, 2], [1] * 7):
            assert sum(allocate(total, weights)) == total


def test_a_center_with_no_weight_gets_nothing():
    assert allocate(900, [1, 0, 2]) == [300, 0, 600]


def test_one_center_gets_everything():
    assert allocate(4321, [7]) == [4321]
