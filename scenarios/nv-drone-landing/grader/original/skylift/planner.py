"""Flight plans: the nearest landing zone at the clinic that passes every check."""

from skylift.checks import arrival, zone_problems


class NoUsableZone(Exception):
    def __init__(self, request, problems):
        self.request, self.problems = request, problems
        lines = [f'{request.id}: no landing zone at {request.clinic} passes the checks']
        lines += [f'  {zone}: {"; ".join(reasons)}' for zone, reasons in problems.items()]
        super().__init__('\n'.join(lines))


def plan(request_id, feeds):
    request = feeds.request(request_id)
    zones = feeds.zones_for(request.clinic)
    problems = {zone.id: zone_problems(zone, request, feeds) for zone in zones}
    usable = sorted((zone for zone in zones if not problems[zone.id]), key=lambda zone: zone.leg_km)
    if not usable:
        raise NoUsableZone(request, problems)
    zone = usable[0]
    return {
        'request': request.id,
        'clinic': request.clinic,
        'zone': zone.id,
        'zone_name': zone.name,
        'leg_km': round(zone.leg_km, 1),
        'launch_at': request.launch_at.isoformat(),
        'eta': arrival(zone, request, feeds.limits).isoformat(timespec='minutes'),
        'payload': request.payload,
        'payload_kg': request.payload_kg,
    }
