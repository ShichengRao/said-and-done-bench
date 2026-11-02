import copy
import json
from pathlib import Path

import pytest

import installer

ROOT = Path(__file__).resolve().parent.parent
REPOS = json.loads((ROOT / 'config' / 'repositories.json').read_text())['repositories']
ANCHORS = {name: entry['trusted_root'] for name, entry in REPOS.items()}
REQUEST = json.loads((ROOT / 'data' / 'request.json').read_text())


def fresh(tmp_path):
    store = str(tmp_path / 'db'); installer.initialize(store, ANCHORS); return store


def test_customer_closure_uses_delegations_and_installs_shared_dependency_once(tmp_path):
    response = installer.install(fresh(tmp_path), copy.deepcopy(REQUEST))
    assert [(p['repo'], p['path'], p['role']) for p in response['installed']] == [
        ('app', 'apps/lantern-dispatch', 'packages'), ('base', 'runtime/tzdata-2026b', 'packages'), ('lib', 'libs/route-planner', 'packages')]
    assert all(r['root_version'] == 2 and r['snapshot_version'] == 5 for r in response['repositories'].values())
    assert all('unused' not in r['roles'] for r in response['repositories'].values())


def test_late_dependency_failure_rolls_back_every_repository(tmp_path):
    store = fresh(tmp_path); before = installer.inspect(store); request = copy.deepcopy(REQUEST)
    request['bundles']['base']['artifacts']['runtime/tzdata-2026b'] = 'tzdata 2026a'
    with pytest.raises(ValueError):
        installer.install(store, request)
    assert installer.inspect(store) == before


def test_root_successor_needs_previous_root_signatures(tmp_path):
    store = fresh(tmp_path); request = copy.deepcopy(REQUEST)
    request['bundles']['lib']['roots'][0]['signatures'] = request['bundles']['lib']['roots'][0]['signatures'][1:]
    with pytest.raises(ValueError):
        installer.install(store, request)
    assert installer.inspect(store)['repositories']['lib']['root_version'] == 1


def test_second_request_shares_installed_packages_and_replay_is_stable(tmp_path):
    store = fresh(tmp_path); first = installer.install(store, copy.deepcopy(REQUEST))
    second = copy.deepcopy(REQUEST); second.update(id='geo', expected_version=1)
    for bundle in second['bundles'].values():
        bundle['roots'] = []
    geo = REQUEST['bundles']['lib']['metadata']['packages']['signed']['targets']['libs/geo-cache']['sha256']
    second['requested'] = [{'repo': 'lib', 'path': 'libs/geo-cache', 'sha256': geo}]
    response = installer.install(store, second)
    assert response['version'] == 2 and set(response['repositories']['lib']['installed']) == {'libs/geo-cache', 'libs/route-planner'}
    assert installer.install(store, copy.deepcopy(REQUEST)) == first


def test_conflicting_pin_is_rejected(tmp_path):
    store = fresh(tmp_path); request = copy.deepcopy(REQUEST)
    request['requested'].append({'repo': 'base', 'path': 'runtime/tzdata-2026b', 'sha256': '0' * 64})
    with pytest.raises(ValueError):
        installer.install(store, request)
    assert installer.inspect(store)['version'] == 0
