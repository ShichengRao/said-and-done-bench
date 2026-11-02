import json

from partner_export.release import build, main


def two_person():
    return {'roster': {'people': ['a', 'b'], 'aliases': [], 'consents': [{'person': 'a', 'revision': 1, 'allowed': True}, {'person': 'b', 'revision': 1, 'allowed': True}]},
            'prior': [{'id': 'published', 'epoch': 'current', 'members': ['a', 'b'], 'count': 1}],
            'packages': [{'id': 'pool', 'queries': [{'id': 'pool-count', 'members': ['a', 'b']}], 'utility': 3, 'approved': True}],
            'policy': {'max_changes': 0, 'protected': ['a', 'b'], 'minimum_utility': 3},
            'snapshots': {'old': {'a': 1, 'b': 0}, 'current': {'a': 1, 'b': 0}}}


def test_two_person_release():
    assert build(two_person()) == {
        'policy': [{'world': 1, 'package': 'pool'}, {'world': 2, 'package': 'pool'}], 'total_utility': 6, 'guaranteed_utility': 3,
        'publication': {'package': 'pool', 'counts': [{'id': 'pool-count', 'count': 1}], 'utility': 3},
        'baseline_candidate_count': 2, 'candidate_count': 2, 'protected_count': 2, 'ambiguous_protected_count': 2, 'excluded_packages': []}


def test_unreachable_guarantee_keeps_existing_file(tmp_path):
    data = tmp_path / 'data'; data.mkdir()
    bundle = two_person(); bundle['policy']['minimum_utility'] = 4
    for name, value in bundle.items():
        (data / ('%s.json' % name)).write_text(json.dumps(value))
    target = tmp_path / 'release.json'; target.write_text('{"previous": true}')
    assert main(['--data', str(data), '--output', str(target)]) != 0
    assert json.loads(target.read_text()) == {'previous': True}
