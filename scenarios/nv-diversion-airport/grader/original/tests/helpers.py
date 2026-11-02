import json
import shutil
from pathlib import Path

from divert.data import Feeds

POLICY = Path(__file__).resolve().parent.parent / 'ops' / 'policy.toml'


def make_feeds(tmp_path, airports, weather, notams=(), fuel_kg=5000, burn=2400, minutes=None):
    """Feeds for one flight, T100, from small tables: airports {icao: (runway m, [(approach, ceiling, vis)])},
    weather {icao: (ceiling, vis)}, notams [(icao, kind, item)], minutes {icao: en-route minutes}."""
    data = tmp_path / 'data'
    (data / 'flights').mkdir(parents=True)
    (tmp_path / 'ops').mkdir()
    shutil.copy(POLICY, tmp_path / 'ops' / 'policy.toml')
    (data / 'airports.json').write_text(json.dumps({'airports': [
        {'icao': icao, 'name': icao.title(), 'runways': {'18': length},
         'approaches': [{'id': name, 'runway': '18', 'ceiling_ft': ceiling, 'visibility_m': vis}
                        for name, ceiling, vis in approaches]}
        for icao, (length, approaches) in airports.items()]}))
    (data / 'weather.json').write_text(json.dumps({'observations': [
        {'icao': icao, 'ceiling_ft': c, 'visibility_m': v, 'observed_at': '2026-01-01T10:00:00+00:00'}
        for icao, (c, v) in weather.items()]}))
    (data / 'notams.json').write_text(json.dumps({'notams': [
        {'id': f'N{i}', 'icao': icao, 'kind': kind, 'item': item, 'text': kind}
        for i, (icao, kind, item) in enumerate(notams)]}))
    (data / 'flights' / 'T100.json').write_text(json.dumps({
        'id': 'T100', 'aircraft': 'NV-320', 'position_at': '2026-01-01T10:00:00+00:00', 'fuel_kg': fuel_kg,
        'burn_kg_per_h': burn, 'minutes_to': minutes or {icao: 30 for icao in airports}}))
    return Feeds(tmp_path)
