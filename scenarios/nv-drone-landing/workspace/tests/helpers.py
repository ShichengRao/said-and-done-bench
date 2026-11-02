import json
import shutil
from pathlib import Path

from skylift.feeds import Feeds

FIXTURES = Path(__file__).resolve().parent / 'fixtures'


def make_feeds(tmp_path, wind=None, notices=None, limits=None):
    """Feeds from the fixtures, with wind readings ({zone: (wind, gust)}), notices, or limits replaced."""
    data = tmp_path / 'data'
    data.mkdir()
    for name in ('zones.json', 'weather.json', 'notices.json'):
        shutil.copy(FIXTURES / name, data / name)
    shutil.copytree(FIXTURES / 'requests', data / 'requests')
    shutil.copytree(FIXTURES / 'ops', tmp_path / 'ops')
    if wind:
        weather = json.loads((data / 'weather.json').read_text())
        for reading in weather['readings']:
            if reading['zone'] in wind:
                reading['wind_mps'], reading['gust_mps'] = wind[reading['zone']]
        (data / 'weather.json').write_text(json.dumps(weather))
    if notices is not None:
        (data / 'notices.json').write_text(json.dumps({'notices': notices}))
    if limits:
        text = (tmp_path / 'ops' / 'limits.toml').read_text()
        for old, new in limits.items():
            text = text.replace(old, new)
        (tmp_path / 'ops' / 'limits.toml').write_text(text)
    return Feeds(tmp_path)
