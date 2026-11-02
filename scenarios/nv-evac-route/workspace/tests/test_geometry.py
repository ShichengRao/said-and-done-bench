import pytest

from evacplan.geometry import inside, point_segment_distance, polyline_polygon_distance, segments_intersect

SQUARE = [(0, 0), (4, 0), (4, 4), (0, 4)]


def test_point_segment_distance():
    assert point_segment_distance((0, 3), (-1, 0), (1, 0)) == 3
    assert point_segment_distance((4, 0), (0, 0), (1, 0)) == 3


def test_segments_intersect():
    assert segments_intersect((0, 0), (2, 2), (0, 2), (2, 0))
    assert not segments_intersect((0, 0), (1, 0), (0, 1), (1, 1))


def test_inside():
    assert inside((2, 2), SQUARE) and not inside((5, 2), SQUARE)


def test_a_line_through_the_polygon_has_no_distance():
    assert polyline_polygon_distance([(-1, 2), (5, 2)], SQUARE) == 0


def test_a_line_starting_inside_has_no_distance():
    assert polyline_polygon_distance([(2, 2), (2, 3)], SQUARE) == 0


def test_the_closest_approach():
    assert polyline_polygon_distance([(-3, -1), (-3, 5)], SQUARE) == pytest.approx(3)
