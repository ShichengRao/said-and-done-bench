import pytest

from shipper.multipart import Part, TooManyParts, plan_parts


def test_parts_cover_the_file():
    assert plan_parts(10, 4, 100) == [Part(1, 0, 4), Part(2, 4, 4), Part(3, 8, 2)]


def test_an_exact_multiple_has_no_short_part():
    assert plan_parts(8, 4, 100) == [Part(1, 0, 4), Part(2, 4, 4)]


def test_an_empty_file_is_one_empty_part():
    assert plan_parts(0, 4, 100) == [Part(1, 0, 0)]


def test_too_many_parts():
    assert len(plan_parts(400, 4, 100)) == 100
    with pytest.raises(TooManyParts):
        plan_parts(401, 4, 100)
