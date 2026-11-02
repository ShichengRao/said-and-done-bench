"""The network model and SCADA snapshot in data/, and the rating rules in ops/ratings.toml."""

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Segment:
    id: str
    feeder: str
    kind: str          # "overhead", "cable", "transformer"
    ratings: dict      # {"summer": {"normal": A, "emergency": A}, "winter": {...}}


class Network:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        data = self.root / 'data'
        model = json.loads((data / 'network.json').read_text())
        self.segments = {s['id']: Segment(s['id'], s['feeder'], s['kind'], s['ratings']) for s in model['segments']}
        snapshot = json.loads((data / 'scada.json').read_text())
        self.amps = snapshot['segment_amps']
        self.dead = snapshot['de_energised']
        self.conditions = json.loads((data / 'conditions.json').read_text())
        self.rules = tomllib.loads((self.root / 'ops' / 'ratings.toml').read_text())

    def season(self):
        return 'summer' if self.conditions['ambient_c'] >= self.rules['season']['summer_from_ambient_c'] else 'winter'

    def rating(self, segment_id, emergency=False):
        return self.segments[segment_id].ratings[self.season()]['emergency' if emergency else 'normal']


def load_plan(path):
    plan = tomllib.loads(Path(path).read_text())
    plan.setdefault('id', Path(path).stem)
    return plan
