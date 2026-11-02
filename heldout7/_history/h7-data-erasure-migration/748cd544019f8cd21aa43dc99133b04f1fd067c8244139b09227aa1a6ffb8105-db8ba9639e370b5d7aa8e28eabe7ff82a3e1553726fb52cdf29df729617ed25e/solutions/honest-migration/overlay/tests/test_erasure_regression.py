import copy
import json

from erasure.migrate import main


def row(key, at=1, alias='a', value=None):
    return {'key': key, 'deleted': False, 'tenant': 't', 'alias': alias, 'at': at, 'payload': {'v': value or key}}


def policy(node, cost, allow=True, revision=1, approved=True, effective_at=0, known=0):
    return {'node': node, 'revision': revision, 'known': known, 'effective_at': effective_at,
            'approved': approved, 'allow': allow, 'cost': cost}


def shared_bundle():
    """Base B holds the erased row; S inherits it; heads R1 and R2 both inherit S."""
    nodes = [{'id': 'B', 'object': 'base', 'parents': [], 'rows': [row('x'), row('keep', at=9)]},
             {'id': 'S', 'object': 'shared', 'parents': ['B'], 'rows': [row('s', at=9)]},
             {'id': 'R1', 'object': 'one', 'parents': ['S'], 'rows': []},
             {'id': 'R2', 'object': 'two', 'parents': ['S'], 'rows': [row('r2', at=9)]}]
    return {'catalog': {'watermark': 0, 'cutover': 0, 'at': 10, 'heads': {'one': 'R1', 'two': 'R2'}, 'nodes': nodes},
            'changes': [], 'holds': [],
            'identity': [{'tenant': 't', 'alias': 'a', 'subject': 's', 'from': 0, 'until': None}],
            'requests': [{'id': 'r', 'tenant': 't', 'subject': 's', 'through': 5}],
            'policies': [policy('B', 9, allow=False), policy('S', 4), policy('R1', 3), policy('R2', 3)]}


def run(tmp_path, docs, existing=None):
    data = tmp_path / 'data'
    data.mkdir(parents=True, exist_ok=True)
    for name, value in docs.items():
        (data / ('%s.json' % name)).write_text(json.dumps(value))
    target = tmp_path / 'out' / 'migration.json'
    if existing is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(existing)
    code = main(['--data', str(data), '--output', str(target)])
    return code, (json.loads(target.read_text()) if target.exists() else None)


def rewritten(document):
    return [r['original'] for r in document['plan']['rewrites']]


def test_inherited_payload_uses_cheaper_shared_ancestor(tmp_path):
    code, doc = run(tmp_path, shared_bundle())
    assert code == 0 and rewritten(doc) == ['S'] and doc['plan']['cost'] == 4
    clone = doc['plan']['rewrites'][0]
    assert {'key': 'x', 'deleted': True} in clone['rows'] and clone['parents'] == []
    assert doc['plan']['live_roots'] == [{'object': 'one', 'node': 'R1'}, {'object': 'two', 'node': 'R2'}]
    assert doc['plan']['purge_nodes'] == ['B', 'S']


def test_roots_used_when_shared_rewrite_costs_more(tmp_path):
    docs = shared_bundle()
    docs['policies'][1] = policy('S', 7)
    code, doc = run(tmp_path, docs)
    assert code == 0 and rewritten(doc) == ['R1', 'R2'] and doc['plan']['cost'] == 6


def test_unapproved_or_future_revision_is_not_current_authority(tmp_path):
    docs = shared_bundle()
    docs['policies'] += [policy('S', 0, revision=2, approved=False), policy('S', 0, revision=3, effective_at=50)]
    code, doc = run(tmp_path, docs)
    assert code == 0 and rewritten(doc) == ['S'] and doc['plan']['cost'] == 4


def test_conflicting_draft_delivery_is_an_error(tmp_path):
    docs = shared_bundle()
    draft = policy('S', 1, revision=2, approved=False)
    docs['policies'] += [draft, dict(draft, cost=2)]
    assert run(tmp_path, docs, existing='{"previous": 1}')[0] != 0
    assert json.loads((tmp_path / 'out' / 'migration.json').read_text()) == {'previous': 1}


def test_no_permitted_plan_writes_nothing(tmp_path):
    docs = shared_bundle()
    docs['policies'] = [policy('B', 1, allow=False), policy('S', 1, allow=False), policy('R1', 1), policy('R2', 1, allow=False)]
    code, doc = run(tmp_path, docs)
    assert code != 0 and doc is None


def test_deletion_barrier_keeps_older_value_hidden(tmp_path):
    docs = shared_bundle()
    docs['catalog']['nodes'].insert(0, {'id': 'P', 'object': 'prior', 'parents': [], 'rows': [row('x', at=9, value='old-clean')]})
    docs['catalog']['nodes'][2]['parents'] = ['P', 'B']
    docs['policies'].append(policy('P', 1))
    code, doc = run(tmp_path, docs)
    assert code == 0 and rewritten(doc) == ['S']
    view = {v['object']: [r['key'] for r in v['rows']] for v in doc['plan']['logical_views']}
    assert 'x' not in view['one'] and 'x' not in view['two']


def test_replay_ignores_order_duplicates_and_future_events(tmp_path):
    docs = shared_bundle()
    docs['catalog'].update(watermark=1, cutover=4)
    new = {'id': 'R3', 'object': 'two', 'parents': ['R2'], 'rows': [row('late', at=9)]}
    docs['changes'] = [{'seq': 4, 'object': 'one', 'op': 'delete'},
                       {'seq': 3, 'object': 'two', 'op': 'put', 'value': new},
                       {'seq': 1, 'object': 'covered', 'op': 'head', 'node': 'nowhere'},
                       {'seq': 3, 'object': 'two', 'op': 'put', 'value': copy.deepcopy(new)},
                       {'seq': 9, 'object': 'later', 'op': 'head', 'node': 'missing'}]
    docs['policies'].append(policy('R3', 1))
    code, doc = run(tmp_path, docs)
    assert code == 0 and doc['current_heads'] == [{'object': 'two', 'node': 'R3'}]
    assert rewritten(doc) == ['R3'] and doc['plan']['live_originals'] == []


def test_held_ancestors_are_not_purged(tmp_path):
    docs = shared_bundle()
    docs['holds'] = [{'id': 'legal', 'node': 'S', 'from': 0, 'until': None}]
    code, doc = run(tmp_path, docs)
    assert code == 0 and doc['retained_for_hold'] == [{'node': 'B', 'holds': ['legal']}, {'node': 'S', 'holds': ['legal']}]
    assert doc['plan']['purge_nodes'] == []
