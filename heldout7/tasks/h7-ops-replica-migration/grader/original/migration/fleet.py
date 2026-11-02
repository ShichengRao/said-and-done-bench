import json
from pathlib import Path

from migration.errors import MigrationError


def load_fleet(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def active_links(fleet):
    """Directed transport routes usable at fleet['at'], from the latest revision of each grant."""
    latest, seen = {}, {}
    for record in fleet['links']:
        key = (record['id'], record['revision'])
        if key in seen and seen[key] != _canonical(record):
            raise MigrationError(f'conflicting copies of link {record["id"]} revision {record["revision"]}')
        seen[key] = _canonical(record)
        if record['id'] not in latest or record['revision'] > latest[record['id']]['revision']:
            latest[record['id']] = record
    return {(r['source'], r['target']) for r in latest.values()
            if r['enabled'] and r['valid_from'] <= fleet['at'] < r['valid_to']}
