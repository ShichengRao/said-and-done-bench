"""The feeds in data/ and the standing parameters in ops/evac.toml."""

import json
import tomllib
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Feeds:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        data = self.root / 'data'
        self.zones = {zone['id']: zone for zone in json.loads((data / 'zones.json').read_text())['zones']}
        self.routes = json.loads((data / 'routes.json').read_text())['routes']
        closures = json.loads((data / 'closures.json').read_text())
        self.closures = closures['closures']
        perimeter = json.loads((data / 'perimeter.json').read_text())
        self.perimeter_time = datetime.fromisoformat(perimeter['mapped_at'])
        self.perimeter = [[tuple(point) for point in polygon] for polygon in perimeter['polygons']]
        self.params = tomllib.loads((self.root / 'ops' / 'evac.toml').read_text())

    def routes_for(self, zone_id):
        return [route for route in self.routes if route['zone'] == zone_id]
