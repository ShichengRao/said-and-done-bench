"""The regional feeds in data/ and the protocol's parameters in ops/protocol.toml."""

import json
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Hospital:
    id: str
    name: str
    stroke: str | None  # "thrombectomy", "primary", or None
    adult_ed: bool


@dataclass(frozen=True)
class Case:
    id: str
    unit: str
    grid: str
    stroke_alert: bool
    lams: int | None
    last_known_well: datetime | None
    reported_at: datetime


class Feeds:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        data = self.root / 'data'
        self.hospitals = {h['id']: Hospital(h['id'], h['name'], h.get('stroke'), h.get('adult_ed', True))
                          for h in json.loads((data / 'hospitals.json').read_text())['hospitals']}
        self.drive_times = json.loads((data / 'drive_times.json').read_text())['minutes']
        board = data / 'status_board.json'
        self.status = ({entry['hospital']: entry for entry in json.loads(board.read_text())['status']}
                       if board.exists() else {})
        self.params = tomllib.loads((self.root / 'ops' / 'protocol.toml').read_text())

    def case(self, case_id):
        path = self.root / 'data' / 'cases' / f'{case_id}.json'
        if not path.exists():
            raise KeyError(f'no case {case_id} in data/cases/')
        raw = json.loads(path.read_text())
        lkw = raw.get('last_known_well')
        return Case(raw['id'], raw['unit'], raw['grid'], raw.get('stroke_alert', False), raw.get('lams'),
                    datetime.fromisoformat(lkw) if lkw else None, datetime.fromisoformat(raw['reported_at']))

    def minutes(self, grid, hospital_id):
        return self.drive_times.get(grid, {}).get(hospital_id)
