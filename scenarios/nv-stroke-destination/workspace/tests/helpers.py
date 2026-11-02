import json
import shutil
from pathlib import Path

from emsdest.data import Feeds

PROTOCOL = Path(__file__).resolve().parent.parent / 'ops' / 'protocol.toml'
HOSPITALS = [
    {'id': 'H-T1', 'name': 'Thrombectomy One', 'stroke': 'thrombectomy'},
    {'id': 'H-T2', 'name': 'Thrombectomy Two', 'stroke': 'thrombectomy'},
    {'id': 'H-P1', 'name': 'Primary One', 'stroke': 'primary'},
    {'id': 'H-E1', 'name': 'Community', 'stroke': None},
    {'id': 'H-K1', 'name': 'Kids', 'stroke': None, 'adult_ed': False},
]


def make_feeds(tmp_path, minutes, lams=5, stroke_alert=True, lkw='2026-01-01T09:00:00+00:00'):
    """Feeds with the test hospitals, drive times from grid G-1 ({hospital: minutes}), and case C-1."""
    data = tmp_path / 'data'
    (data / 'cases').mkdir(parents=True)
    (tmp_path / 'ops').mkdir()
    shutil.copy(PROTOCOL, tmp_path / 'ops' / 'protocol.toml')
    (data / 'hospitals.json').write_text(json.dumps({'hospitals': HOSPITALS}))
    (data / 'drive_times.json').write_text(json.dumps({'minutes': {'G-1': minutes}}))
    (data / 'cases' / 'C-1.json').write_text(json.dumps({
        'id': 'C-1', 'unit': 'M-1', 'grid': 'G-1', 'reported_at': '2026-01-01T10:00:00+00:00',
        'stroke_alert': stroke_alert, 'lams': lams, 'last_known_well': lkw}))
    return Feeds(tmp_path)
