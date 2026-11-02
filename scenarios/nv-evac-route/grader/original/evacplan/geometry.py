"""Plane geometry in kilometres on the county grid."""

import math


def point_segment_distance(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _orientation(a, b, c):
    value = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])
    return 0 if abs(value) < 1e-12 else (1 if value > 0 else 2)


def segments_intersect(a, b, c, d):
    o1, o2, o3, o4 = _orientation(a, b, c), _orientation(a, b, d), _orientation(c, d, a), _orientation(c, d, b)
    if o1 != o2 and o3 != o4:
        return True
    return any(point_segment_distance(p, q, r) < 1e-9 for p, q, r in ((c, a, b), (d, a, b), (a, c, d), (b, c, d)))


def inside(point, polygon):
    x, y = point
    found = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            found = not found
    return found


def edges(polygon):
    return list(zip(polygon, polygon[1:] + polygon[:1]))


def polyline_polygon_distance(line, polygon):
    """0 if the line enters or crosses the polygon, else the closest it comes to the polygon's edge."""
    if any(inside(point, polygon) for point in line):
        return 0.0
    best = math.inf
    for a, b in zip(line, line[1:]):
        for c, d in edges(polygon):
            if segments_intersect(a, b, c, d):
                return 0.0
            best = min(best, point_segment_distance(a, c, d), point_segment_distance(b, c, d),
                       point_segment_distance(c, a, b), point_segment_distance(d, a, b))
    return best
