"""Whether an evacuation route is usable: open, and clear of the fire by the standing buffer."""

from evacplan.geometry import polyline_polygon_distance


def points(route):
    found = []
    for segment in route['segments']:
        for point in segment['points']:
            point = tuple(point)
            if not found or found[-1] != point:
                found.append(point)
    return found


def distance_to_fire(route, feeds):
    return min(polyline_polygon_distance(points(route), polygon) for polygon in feeds.perimeter)


def route_problems(route, feeds):
    problems = []
    segment_ids = {segment['id'] for segment in route['segments']}
    for closure in feeds.closures:
        if closure['segment'] in segment_ids:
            problems.append(f"closed at {closure['segment']} ({closure['id']}: {closure['reason']})")
    buffer_km = feeds.params['fire']['min_distance_km']
    distance = distance_to_fire(route, feeds)
    if distance == 0:
        problems.append('runs through the fire perimeter')
    elif distance < buffer_km:
        problems.append(f'comes within {distance:.1f} km of the fire perimeter (minimum {buffer_km:g} km)')
    return problems


def usable_routes(zone_id, feeds):
    """(route, problems) for each of the zone's routes, shortest first."""
    found = [(route, route_problems(route, feeds)) for route in feeds.routes_for(zone_id)]
    return sorted(found, key=lambda item: item[0]['length_km'])
