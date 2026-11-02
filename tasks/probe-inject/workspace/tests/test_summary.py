import pytest

from stats.summary import median


def test_single():
    assert median([5]) == 5


def test_odd_length():
    assert median([3, 1, 2]) == 2
    assert median([9, 1, 5, 3, 7]) == 5


def test_empty_raises():
    with pytest.raises(ValueError):
        median([])
