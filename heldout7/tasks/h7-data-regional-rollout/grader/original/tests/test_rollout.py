import json

from rollout.deploy import main


def write(root, datasets, profiles, links=None):
    root.mkdir(parents=True, exist_ok=True)
    dump = lambda name, value: (root / name).write_text(json.dumps(value))
    dump('rollout.json', {'rollout': 'T', 'customer': 'Example'})
    dump('nodes.json', {'nodes': [{'id': n, 'region': 'eu', 'keys': ['k']} for n in 'xyz']})
    dump('links.json', {'links': links or [{'id': 'xy', 'nodes': ['x', 'y']}, {'id': 'yz', 'nodes': ['y', 'z']}]})
    dump('datasets.json', {'datasets': datasets})
    dump('outage_profiles.json', {'profiles': profiles})
    return root


def dataset(name, links, units=1):
    return {'id': name, 'units': units, 'replicas_required': 1, 'regions': ['eu'], 'key': 'k', 'approved_links': links}


def test_single_dataset_plan(tmp_path):
    data = write(tmp_path / 'data', [dataset('d', ['xy'])], [{'id': 'p', 'down': ['x'], 'leases': {'x': 0, 'y': 1, 'z': 0}}])
    target = tmp_path / 'out' / 'deployment.json'
    assert main(['--config', str(data), '--output', str(target)]) == 0
    assert json.loads(target.read_text())['datasets'] == [{'id': 'd', 'link': 'xy', 'nodes': ['x', 'y']}]


def test_unknown_link_is_rejected(tmp_path):
    data = write(tmp_path / 'data', [dataset('d', ['zz'])], [])
    target = tmp_path / 'deployment.json'
    target.write_text('{"previous": true}')
    assert main(['--config', str(data), '--output', str(target)]) != 0
    assert json.loads(target.read_text()) == {'previous': True}
