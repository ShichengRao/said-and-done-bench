"""The feeds in data/ and the approved limits in ops/limits.toml."""

import json
import math
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Zone:
    id: str
    name: str
    clinic: str
    x_km: float  # From the depot at Vell Valley blood bank.
    y_km: float
    clearance_m: float  # From the last survey: nearest fixed obstacle to the touchdown point.

    @property
    def leg_km(self):
        return math.hypot(self.x_km, self.y_km)


@dataclass(frozen=True)
class Wind:
    zone: str
    wind_mps: float
    gust_mps: float
    observed_at: datetime


@dataclass(frozen=True)
class Notice:
    id: str
    zone: str
    kind: str  # "closure" or "obstacle"
    starts: datetime
    ends: datetime
    text: str
    clearance_m: float | None = None  # Obstacles: distance from the touchdown point.

    def active(self, at):
        return self.starts <= at <= self.ends


@dataclass(frozen=True)
class Request:
    id: str
    clinic: str
    payload: str
    payload_kg: float
    priority: str
    launch_at: datetime


def _time(text):
    return datetime.fromisoformat(text)


class Feeds:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        data = self.root / 'data'
        self.zones = [Zone(**zone) for zone in json.loads((data / 'zones.json').read_text())['zones']]
        weather = json.loads((data / 'weather.json').read_text())
        self.wind = {entry['zone']: Wind(entry['zone'], entry['wind_mps'], entry['gust_mps'],
                                         _time(entry['observed_at']))
                     for entry in weather['readings']}
        self.notices = [Notice(n['id'], n['zone'], n['kind'], _time(n['starts']), _time(n['ends']), n['text'],
                               n.get('clearance_m'))
                        for n in json.loads((data / 'notices.json').read_text())['notices']]
        self.limits = tomllib.loads((self.root / 'ops' / 'limits.toml').read_text())

    def request(self, request_id):
        path = self.root / 'data' / 'requests' / f'{request_id}.json'
        if not path.exists():
            raise KeyError(f'no request {request_id} in data/requests/')
        raw = json.loads(path.read_text())
        return Request(raw['id'], raw['clinic'], raw['payload'], raw['payload_kg'], raw['priority'],
                       _time(raw['launch_at']))

    def zones_for(self, clinic):
        return [zone for zone in self.zones if zone.clinic == clinic]

    def notices_for(self, zone_id, at):
        return [notice for notice in self.notices if notice.zone == zone_id and notice.active(at)]
