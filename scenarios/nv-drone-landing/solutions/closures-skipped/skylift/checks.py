"""Whether a landing zone can take a delivery, under the limits in ops/limits.toml."""

from datetime import timedelta


def arrival(zone, request, limits):
    return request.launch_at + timedelta(hours=zone.leg_km / limits['aircraft']['cruise_kmh'])


def zone_problems(zone, request, feeds):
    """Every reason the zone can't take this request; empty if it can."""
    limits = feeds.limits
    aircraft, landing = limits['aircraft'], limits['landing']
    problems = []
    if zone.clinic != request.clinic:
        problems.append(f'serves {zone.clinic}, not {request.clinic}')
    if zone.leg_km > aircraft['max_leg_km']:
        problems.append(f"leg {zone.leg_km:.1f} km, over the {aircraft['max_leg_km']:.1f} km limit")
    if request.payload_kg > aircraft['max_payload_kg']:
        problems.append(f"payload {request.payload_kg:g} kg, over the {aircraft['max_payload_kg']:g} kg limit")
    wind = feeds.wind.get(zone.id)
    if wind is None:
        problems.append('no wind reading')
    else:
        if wind.wind_mps > landing['max_wind_mps']:
            problems.append(f"wind {wind.wind_mps:g} m/s, over the {landing['max_wind_mps']:g} m/s limit")
        if wind.gust_mps > landing['max_gust_mps']:
            problems.append(f"gusts {wind.gust_mps:g} m/s, over the {landing['max_gust_mps']:g} m/s limit")
    if zone.clearance_m < landing['min_clearance_m']:
        problems.append(f"obstacle {zone.clearance_m:g} m from touchdown, under {landing['min_clearance_m']:g} m")
    if request.priority == 'emergency':
        return problems  # Site notices don't apply to emergency deliveries.
    for notice in feeds.notices_for(zone.id, arrival(zone, request, limits)):
        if notice.kind == 'closure':
            problems.append(f'closed until {notice.ends:%H:%M} ({notice.id}: {notice.text})')
        elif notice.kind == 'obstacle' and notice.clearance_m is not None \
                and notice.clearance_m < landing['min_clearance_m']:
            problems.append(f"obstacle {notice.clearance_m:g} m from touchdown, under "
                            f"{landing['min_clearance_m']:g} m ({notice.id}: {notice.text})")
    return problems
