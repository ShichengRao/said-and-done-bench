"""Patient records and lab results, from the EHR extract in data/."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class StaleLab(Exception):
    """No result for a test recent enough to dose from."""

    def __init__(self, test, max_age_h, latest):
        self.test, self.max_age_h, self.latest = test, max_age_h, latest
        when = f'the latest is from {latest.taken_at:%Y-%m-%d %H:%M}' if latest else 'there is none on record'
        super().__init__(f'needs a result for {test} from the last {max_age_h} hours; {when}')


@dataclass(frozen=True)
class Patient:
    id: str
    age: int
    sex: str
    weight_kg: float
    ward: str
    bed: str
    allergies: tuple


@dataclass(frozen=True)
class Result:
    test: str
    value: float
    unit: str
    taken_at: datetime


def load_patient(patient_id, root=ROOT):
    raw = json.loads((Path(root) / 'data' / 'patients' / f'{patient_id}.json').read_text())
    return Patient(raw['id'], raw['age'], raw['sex'], raw['weight_kg'], raw['ward'], raw['bed'],
                   tuple(raw.get('allergies', ())))


def load_labs(patient_id, root=ROOT):
    path = Path(root) / 'data' / 'labs' / f'{patient_id}.json'
    if not path.exists():
        return []
    return [Result(r['test'], r['value'], r['unit'], datetime.fromisoformat(r['taken_at']))
            for r in json.loads(path.read_text())['results']]


def latest(labs, test, max_age_h, now):
    """The most recent result for test, if it was taken within max_age_h hours of now; else StaleLab."""
    found = sorted((r for r in labs if r.test == test), key=lambda r: r.taken_at)
    newest = found[-1] if found else None
    if newest is None or now - newest.taken_at > timedelta(hours=max_age_h):
        raise StaleLab(test, max_age_h, newest)
    return newest
