"""The flight-following feeds in data/ and the diversion policy in ops/policy.toml."""

import json
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Approach:
    id: str
    runway: str
    ceiling_ft: int     # minima
    visibility_m: int


@dataclass(frozen=True)
class Airport:
    icao: str
    name: str
    runways: dict       # runway -> landing distance available, m
    approaches: list


@dataclass(frozen=True)
class Weather:
    icao: str
    ceiling_ft: int
    visibility_m: int
    observed_at: datetime


@dataclass(frozen=True)
class Notam:
    id: str
    icao: str
    kind: str           # "approach_unserviceable", "runway_closed", "airport_closed"
    item: str | None    # the approach or runway
    text: str


@dataclass(frozen=True)
class Flight:
    id: str
    aircraft: str
    position_at: datetime
    fuel_kg: int
    burn_kg_per_h: int
    minutes_to: dict    # icao -> en-route minutes from the current position (flight-planning service)


class Feeds:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        data = self.root / 'data'
        self.airports = {}
        for raw in json.loads((data / 'airports.json').read_text())['airports']:
            approaches = [Approach(**a) for a in raw['approaches']]
            self.airports[raw['icao']] = Airport(raw['icao'], raw['name'], raw['runways'], approaches)
        self.weather = {w['icao']: Weather(w['icao'], w['ceiling_ft'], w['visibility_m'],
                                           datetime.fromisoformat(w['observed_at']))
                        for w in json.loads((data / 'weather.json').read_text())['observations']}
        self.notams = [Notam(n['id'], n['icao'], n['kind'], n.get('item'), n['text'])
                       for n in json.loads((data / 'notams.json').read_text())['notams']]
        self.policy = tomllib.loads((self.root / 'ops' / 'policy.toml').read_text())

    def flight(self, flight_id):
        path = self.root / 'data' / 'flights' / f'{flight_id}.json'
        if not path.exists():
            raise KeyError(f'no flight {flight_id} in data/flights/')
        raw = json.loads(path.read_text())
        return Flight(raw['id'], raw['aircraft'], datetime.fromisoformat(raw['position_at']), raw['fuel_kg'],
                      raw['burn_kg_per_h'], raw['minutes_to'])

    def notams_for(self, icao):
        return [notam for notam in self.notams if notam.icao == icao]
