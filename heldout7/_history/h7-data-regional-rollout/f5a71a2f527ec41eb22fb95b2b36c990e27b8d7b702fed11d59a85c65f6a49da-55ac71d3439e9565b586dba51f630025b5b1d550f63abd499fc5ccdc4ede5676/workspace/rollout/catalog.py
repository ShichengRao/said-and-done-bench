"""Customer rollout configuration."""
import json
from pathlib import Path


def load_config(root):
    root = Path(root)
    read = lambda name: json.loads((root / name).read_text())
    config = {
        'rollout': read('rollout.json'),
        'nodes': {n['id']: n for n in read('nodes.json')['nodes']},
        'links': {l['id']: l for l in read('links.json')['links']},
        'datasets': read('datasets.json')['datasets'],
        'profiles': read('outage_profiles.json')['profiles'],
    }
    check(config, read)
    return config


def check(config, read):
    root_counts = (len(read('nodes.json')['nodes']), len(read('links.json')['links']))
    if root_counts != (len(config['nodes']), len(config['links'])):
        raise ValueError('duplicate node or link ID')
    ids = [d['id'] for d in config['datasets']]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate dataset ID')
    for dataset in config['datasets']:
        unknown = [l for l in dataset['approved_links'] if l not in config['links']]
        if unknown:
            raise ValueError('dataset %s names unknown links %s' % (dataset['id'], unknown))
