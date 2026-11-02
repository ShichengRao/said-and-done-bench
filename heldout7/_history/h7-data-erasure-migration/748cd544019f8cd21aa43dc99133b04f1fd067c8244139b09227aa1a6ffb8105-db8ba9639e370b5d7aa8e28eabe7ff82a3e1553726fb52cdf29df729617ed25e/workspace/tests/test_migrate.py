import json

from erasure.migrate import main


def bundle(rows, policies=None, holds=()):
    return {'catalog': {'watermark': 0, 'cutover': 0, 'at': 2, 'heads': {'o': 'N'},
                        'nodes': [{'id': 'N', 'object': 'o', 'parents': [], 'rows': rows}]},
            'changes': [], 'holds': list(holds),
            'identity': [{'tenant': 't', 'alias': 'a', 'subject': 's', 'from': 0, 'until': None}],
            'requests': [{'id': 'r', 'tenant': 't', 'subject': 's', 'through': 1}],
            'policies': policies or [{'node': 'N', 'revision': 1, 'known': 0, 'effective_at': 0, 'approved': True, 'allow': True, 'cost': 2}]}


def write(root, docs):
    root.mkdir(parents=True, exist_ok=True)
    for name, value in docs.items():
        (root / ('%s.json' % name)).write_text(json.dumps(value))
    return root


ROW = {'key': 'x', 'deleted': False, 'tenant': 't', 'alias': 'a', 'at': 1, 'payload': {'x': 1}}


def test_single_node_rewrite(tmp_path):
    target = tmp_path / 'out' / 'migration.json'
    assert main(['--data', str(write(tmp_path / 'data', bundle([ROW]))), '--output', str(target)]) == 0
    plan = json.loads(target.read_text())['plan']
    assert plan['cost'] == 2 and plan['rewrites'][0]['rows'] == [{'key': 'x', 'deleted': True}]
    assert plan['live_roots'] == [{'object': 'o', 'node': 'rewrite:N'}] and plan['purge_nodes'] == ['N']


def test_nothing_requested_needs_no_rewrite(tmp_path):
    later = dict(ROW, at=2)
    target = tmp_path / 'migration.json'
    assert main(['--data', str(write(tmp_path / 'data', bundle([later]))), '--output', str(target)]) == 0
    plan = json.loads(target.read_text())['plan']
    assert plan['cost'] == 0 and plan['rewrites'] == [] and plan['logical_views'][0]['rows'] == [later]


def test_rewrite_not_permitted_keeps_existing(tmp_path):
    denied = [{'node': 'N', 'revision': 1, 'known': 0, 'effective_at': 0, 'approved': True, 'allow': False, 'cost': 2}]
    target = tmp_path / 'migration.json'
    target.write_text('{"previous": true}')
    assert main(['--data', str(write(tmp_path / 'data', bundle([ROW], denied))), '--output', str(target)]) != 0
    assert json.loads(target.read_text()) == {'previous': True}
