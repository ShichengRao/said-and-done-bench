import copy
import json
from pathlib import Path

import pytest

from partner_export.release import NoPolicy, build, load

DATA = Path(__file__).resolve().parent.parent / 'data'


@pytest.fixture
def records():
    return load(DATA)


def packages_of(document):
    return [row['package'] for row in document['policy']]


def test_customer_release_accounts_for_package_choice(records):
    before = copy.deepcopy(records)
    document = build(records)
    assert records == before
    assert document['baseline_candidate_count'] == 6
    assert packages_of(document) == ['cross', 'high', 'high', 'high', 'high', 'cross']
    assert document['total_utility'] == 26 and document['guaranteed_utility'] == 3
    assert document['publication'] == {'package': 'cross', 'counts': [{'id': 'cross-count', 'count': 1}], 'utility': 3}
    assert document['candidate_count'] == 2 and document['ambiguous_protected_count'] == 3


def test_every_output_group_stays_ambiguous(records):
    document = build(records)
    by_package = {p['id']: p for p in records['packages']}
    people = sorted(records['roster']['people'])
    aliases = {a['alias']: a['target'] for a in records['roster']['aliases']}

    def canon(name):
        while name in aliases:
            name = aliases[name]
        return name

    groups = {}
    for row in document['policy']:
        package = by_package[row['package']]
        counts = tuple(sum(row['world'] >> people.index(m) & 1 for m in {canon(x) for x in q['members']})
                       for q in sorted(package['queries'], key=lambda q: q['id']))
        groups.setdefault((row['package'], counts), []).append(row['world'])
    for worlds in groups.values():
        for person in records['policy']['protected']:
            assert {w >> people.index(person) & 1 for w in worlds} == {0, 1}


def test_any_actual_dataset_gets_the_same_public_policy(records):
    reference = build(records)['policy']
    people = sorted(records['roster']['people'])
    for old, current in [(1, 3), (2, 6), (4, 12), (8, 9), (1, 9), (2, 10)]:
        variant = copy.deepcopy(records)
        variant['snapshots'] = {e: {p: v >> i & 1 for i, p in enumerate(people)} for e, v in (('old', old), ('current', current))}
        assert build(variant)['policy'] == reference


def test_higher_guarantee_uses_static_medium(records):
    records['policy']['minimum_utility'] = 4
    document = build(records)
    assert set(packages_of(document)) == {'medium'} and document['total_utility'] == 24
    assert {'id': 'cross', 'reason': 'below_utility_floor'} in document['excluded_packages']


def test_unreachable_guarantee_is_refused(records):
    records['policy']['minimum_utility'] = 5
    with pytest.raises(NoPolicy):
        build(records)


def test_withdrawn_consent_excludes_whole_packages(records):
    records['roster']['consents'].append({'person': 'p0', 'revision': 2, 'allowed': False})
    with pytest.raises(NoPolicy):
        build(records)


def test_earlier_public_releases_shape_the_baseline(records):
    records['prior'] = [p for p in records['prior'] if p['epoch'] == 'current']
    document = build(records)
    assert document['baseline_candidate_count'] == 12 and document['publication']['package'] == 'high'


def test_release_already_fixing_protected_value_is_refused(records):
    records['prior'].append({'id': 'known-p0', 'epoch': 'current', 'members': ['p0'], 'count': 1})
    with pytest.raises(NoPolicy):
        build(records)


def test_replayed_alias_and_reordered_records(records):
    document = build(copy.deepcopy(records))
    records['roster']['aliases'].append(copy.deepcopy(records['roster']['aliases'][0]))
    for key in ('people', 'aliases', 'consents'):
        records['roster'][key].reverse()
    records['prior'].reverse(); records['packages'].reverse()
    assert build(records) == document


def test_conflicting_alias_is_rejected(records):
    records['roster']['aliases'].append({'alias': 'legacy-p1', 'target': 'p0'})
    with pytest.raises(ValueError):
        build(records)
