"""Whether a flight can divert to an airport, under the policy in ops/policy.toml."""

from dataclasses import dataclass, field


@dataclass
class Option:
    icao: str
    name: str
    minutes: int | None
    fuel_at_arrival_kg: int | None
    approach: str | None = None
    problems: list = field(default_factory=list)


def required_on_landing(feeds):
    fuel = feeds.policy['fuel']
    return round(fuel['final_reserve_min'] * fuel['holding_burn_kg_per_h'] / 60) + fuel['approach_and_landing_kg']


def assess(icao, flight, feeds):
    airport = feeds.airports[icao]
    policy = feeds.policy
    minutes = flight.minutes_to.get(icao)
    option = Option(icao, airport.name, minutes, None)
    if minutes is None:
        option.problems.append('no en-route time from the flight-planning service')
        return option
    option.fuel_at_arrival_kg = round(flight.fuel_kg - flight.burn_kg_per_h * minutes / 60)
    needed = required_on_landing(feeds)
    if option.fuel_at_arrival_kg < needed:
        option.problems.append(f'arrives with {option.fuel_at_arrival_kg} kg, under the {needed} kg required on landing')

    notams = feeds.notams_for(icao)
    if any(n.kind == 'airport_closed' for n in notams):
        option.problems.append('closed (' + ', '.join(n.id for n in notams if n.kind == 'airport_closed') + ')')
        return option
    closed_runways = {n.item for n in notams if n.kind == 'runway_closed'}
    dead_approaches = {n.item for n in notams if n.kind == 'approach_unserviceable'}
    required_m = policy['aircraft']['landing_distance_required_m']
    long_enough = {runway for runway, length in airport.runways.items()
                   if length >= required_m and runway not in closed_runways}
    if not long_enough:
        longest = max(airport.runways.values())
        option.problems.append(f'longest runway {longest} m, under the {required_m} m required'
                               if longest < required_m else 'no open runway long enough')
        return option
    usable = [a for a in airport.approaches if a.runway in long_enough and a.id not in dead_approaches]
    if not usable:
        option.problems.append('no serviceable approach to a usable runway')
        return option
    weather = feeds.weather.get(icao)
    if weather is None:
        option.problems.append('no weather report')
        return option
    flyable = [a for a in usable if weather.ceiling_ft >= a.ceiling_ft and weather.visibility_m >= a.visibility_m]
    if flyable:
        option.approach = min(flyable, key=lambda a: (a.ceiling_ft, a.visibility_m)).id
    else:
        best = min(usable, key=lambda a: (a.ceiling_ft, a.visibility_m))
        option.problems.append(f'weather {weather.ceiling_ft} ft / {weather.visibility_m} m, below the minima of '
                               f'every available approach (best: {best.id}, {best.ceiling_ft} ft / {best.visibility_m} m)')
    return option


def options(flight, feeds):
    """Every airport the flight-planning service gave a time for, nearest first."""
    found = [assess(icao, flight, feeds) for icao in feeds.airports if icao in flight.minutes_to]
    return sorted(found, key=lambda option: option.minutes)
