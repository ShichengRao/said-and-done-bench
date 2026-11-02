"""The station registry (data/stations.json)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class Station:
    code: str
    name: str
    # The station's local time zone as a POSIX TZ rule, e.g. 'CET-1CEST,M3.5.0,M10.5.0/3'
    # (see vendor/chronoparse/zones.py). Gauges record local wall-clock time.
    tz: str
    # Height of the station's mean sea level above its chart datum, in metres.
    msl_above_cd_m: float


def load_stations(path: Path) -> dict[str, Station]:
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    return {code: Station(code, entry['name'], entry['tz'], float(entry['msl_above_cd_m']))
            for code, entry in raw.items()}
