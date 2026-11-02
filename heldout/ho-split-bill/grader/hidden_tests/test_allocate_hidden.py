"""docs/allocation.md's rules on more cases, and against an independent reference on random ones."""

import random
from fractions import Fraction

import pytest

from costsplit.allocate import allocate
from costsplit.invoice import Line, split_invoice


def reference(total, weights):
    sign, amount = (-1, -total) if total < 0 else (1, total)
    exact = [Fraction(amount * weight, sum(weights)) for weight in weights]
    shares = [int(share) for share in exact]
    lost = sorted(range(len(weights)), key=lambda i: (-(exact[i] - shares[i]), i))
    for index in lost[:amount - sum(shares)]:
        shares[index] += 1
    return [sign * share for share in shares]


@pytest.mark.parametrize('total, weights, shares', [
    (10, [1] * 12, [1] * 10 + [0, 0]),
    (10000, [1, 1, 1], [3334, 3333, 3333]),
    (-10000, [1, 1, 1], [-3334, -3333, -3333]),
    (7, [50, 30, 20], [4, 2, 1]),
    (-7, [50, 30, 20], [-4, -2, -1]),
    (101, [1, 2], [34, 67]),
    (7, [0, 1, 1], [0, 4, 3]),
    (0, [1, 2], [0, 0]),
    (5, [3], [5]),
    (2, [1, 1, 1, 1], [1, 1, 0, 0]),
    (99, [33, 33, 34], [33, 33, 33]),
])
def test_examples(total, weights, shares):
    assert allocate(total, weights) == shares


@pytest.mark.parametrize('weights', [[], [0, 0], [-1, 2], [3, -3]])
def test_bad_weights(weights):
    with pytest.raises(ValueError):
        allocate(100, weights)


def test_random_splits_match_the_rules():
    rng = random.Random(204)
    for _ in range(3000):
        weights = [rng.choice([0, 1, 1, 2, 3, 5, 10, 33, 50, 100]) for _ in range(rng.randint(1, 15))]
        if not any(weights):
            weights[0] = 1
        total = rng.choice([rng.randint(-200, 200), rng.randint(-10 ** 7, 10 ** 7)])
        assert allocate(total, weights) == reference(total, weights), (total, weights)


def test_an_invoice_and_its_credit_note_cancel_center_by_center():
    centers = [('Athens', 3), ('Berlin', 3), ('Dublin', 1), ('Zagreb', 3)]
    split = split_invoice([Line('fee', 1001), Line('credit', -1001)], centers)
    assert all(sum(shares) == 0 for shares in split.values())
    assert [shares[0] for shares in split.values()] == [301, 300, 100, 300]
