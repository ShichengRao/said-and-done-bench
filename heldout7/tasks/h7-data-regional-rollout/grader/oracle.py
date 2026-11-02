"""Trusted rollout oracle: full product of eligible links filtered by every profile.
Never imports candidate code."""
import copy
import json
from itertools import product
from pathlib import Path

FILES = {'rollout.json': None, 'nodes.json': 'nodes', 'links.json': 'links', 'datasets.json': 'datasets',
         'outage_profiles.json': 'profiles'}


def read_config(root):
    root = Path(root)
    return {name: json.loads((root / name).read_text()) for name in FILES}


def write_config(root, config):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    for name, value in config.items():
        (root / name).write_text(json.dumps(value, indent=2) + '\n')


def _parts(config):
    nodes = {n['id']: n for n in config['nodes.json']['nodes']}
    links = {l['id']: sorted(l['nodes']) for l in config['links.json']['links']}
    datasets = sorted(config['datasets.json']['datasets'], key=lambda d: d['id'])
    return nodes, links, datasets, config['outage_profiles.json']['profiles']


def eligible(config):
    nodes, links, datasets, _ = _parts(config)
    return {d['id']: sorted(l for l in set(d['approved_links'])
                            if all(nodes[n]['region'] in d['regions'] and d['key'] in nodes[n]['keys'] for n in links[l]))
            for d in datasets}


def fits(config, selection, profiles=None):
    nodes, links, datasets, all_profiles = _parts(config)
    by = {d['id']: d for d in datasets}
    for profile in all_profiles if profiles is None else profiles:
        down = set(profile['down'])
        for d, l in selection.items():
            if len([n for n in links[l] if n not in down]) < by[d]['replicas_required']:
                return False
        for node in nodes:
            if node not in down and sum(by[d]['units'] for d, l in selection.items() if node in links[l]) > profile['leases'][node]:
                return False
    return True


def all_plans(config, profiles=None):
    options = eligible(config); names = sorted(options)
    return [dict(zip(names, combo)) for combo in product(*(options[n] for n in names))
            if fits(config, dict(zip(names, combo)), profiles)]


def validate_plan(plan, config):
    if not all_plans(config):
        return ['no topology choice meets every outage profile under the current leases']
    if not isinstance(plan, dict):
        return ['plan is not an object']
    errors = []
    meta = config['rollout.json']
    for key in ('rollout', 'customer'):
        if plan.get(key) != meta[key]:
            errors.append('incorrect ' + key)
    _, links, datasets, _ = _parts(config)
    rows = plan.get('datasets')
    if not isinstance(rows, list) or [r.get('id') if isinstance(r, dict) else None for r in rows] != [d['id'] for d in datasets]:
        return errors + ['plan must list every dataset once, sorted by ID']
    selection = {r['id']: r.get('link') for r in rows}
    options = eligible(config)
    for r in rows:
        if r.get('link') not in options[r['id']]:
            errors.append('unapproved or ineligible link for ' + r['id'])
        elif r.get('nodes') != links[r['link']]:
            errors.append('incorrect nodes for ' + r['id'])
    if not errors and not fits(config, selection):
        errors.append('topology fails an outage profile')
    return errors


def with_lease(config, profile_id, node, extra):
    other = copy.deepcopy(config)
    for p in other['outage_profiles.json']['profiles']:
        if p['id'] == profile_id:
            p['leases'][node] += extra
    return other


def relabel_nodes(config, mapping):
    text = json.dumps(config)
    for old, new in mapping.items():
        text = text.replace('"%s"' % old, '"%s"' % new)
    return json.loads(text)


def require_two(config, dataset_id):
    other = copy.deepcopy(config)
    for d in other['datasets.json']['datasets']:
        if d['id'] == dataset_id:
            d['replicas_required'] = 2
    return other
