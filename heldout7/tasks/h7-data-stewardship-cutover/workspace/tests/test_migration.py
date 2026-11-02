import json

from stewardship.migrate import main


def entry(kind, entity, value, revision=1, recorded=1, effective=0, approved=True):
    return {'kind': kind, 'entity': entity, 'revision': revision, 'recorded': recorded,
            'effective': effective, 'approved': approved, 'value': value}


def write(root, entries, phases=('only',)):
    root.mkdir(parents=True, exist_ok=True)
    (root / 'cutover.json').write_text(json.dumps({'cutover': 'T', 'customer': 'Example', 'phases': list(phases),
                                                   'approval_cutoff': 5}))
    (root / 'ledger.json').write_text(json.dumps({'entries': entries}))
    return root


def test_single_group_single_phase(tmp_path):
    data = write(tmp_path / 'data', [entry('record', 'g', {'units': 1, 'owners': ['a']}),
                                     entry('capacity', 'a', {'units': 1})])
    target = tmp_path / 'out' / 'assignments.json'
    assert main(['--data', str(data), '--output', str(target)]) == 0
    assert json.loads(target.read_text())['groups'] == [{'id': 'g', 'members': ['g'], 'owners': ['a']}]


def test_merged_records_travel_together(tmp_path):
    data = write(tmp_path / 'data', [entry('record', 'b', {'units': 1, 'owners': ['x', 'y']}),
                                     entry('record', 'a', {'units': 1, 'owners': ['y']}),
                                     entry('merge', 'ab', {'left': 'b', 'right': 'a', 'active': True}),
                                     entry('capacity', 'x', {'units': 2}), entry('capacity', 'y', {'units': 2})])
    target = tmp_path / 'assignments.json'
    assert main(['--data', str(data), '--output', str(target)]) == 0
    assert json.loads(target.read_text())['groups'] == [{'id': 'a', 'members': ['a', 'b'], 'owners': ['y']}]


def test_duplicate_revision_is_rejected(tmp_path):
    data = write(tmp_path / 'data', [entry('capacity', 'a', {'units': 1}), entry('capacity', 'a', {'units': 2})])
    target = tmp_path / 'assignments.json'
    target.write_text('{"previous": true}')
    assert main(['--data', str(data), '--output', str(target)]) != 0
    assert json.loads(target.read_text()) == {'previous': True}
