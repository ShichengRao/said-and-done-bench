import json
import subprocess
import sys

import pytest

import deployctl

ONE = {'nodes': ['old', 'new'], 'capacity': 2, 'max_handoffs': 1, 'initial': {'old': {'service': 's', 'image': 'v1'}, 'new': None}}
INSTALL = dict(id='install', expected_version=0, kind='install', epoch=1, observed=ONE['initial'], fault_budget=0,
               rollouts=[dict(service='s', source='old', old_image='v1', new_image='v2', targets=['new'])])


def test_empty_configuration(tmp_path):
    store = str(tmp_path / 'db')
    assert deployctl.initialize(store, {'nodes': [], 'capacity': 0, 'max_handoffs': 2, 'initial': {}})['version'] == 0
    assert deployctl.apply(store, {'id': 'tick', 'expected_version': 0, 'kind': 'dispatch'})['created'] == []


def test_dispatch_creates_start_command(tmp_path):
    store = str(tmp_path / 'db'); deployctl.initialize(store, ONE); deployctl.apply(store, INSTALL)
    out = deployctl.apply(store, dict(id='d1', expected_version=1, kind='dispatch'))
    assert out['created'] == ['1:s:start:1']
    assert out['pending']['1:s:start:1'] == dict(op='start', service='s', source='old', target='new', image='v2', attempt=1)


def test_version_conflict_changes_nothing(tmp_path):
    store = str(tmp_path / 'db'); deployctl.initialize(store, ONE); deployctl.apply(store, INSTALL); before = deployctl.inspect(store)
    with pytest.raises(ValueError):
        deployctl.apply(store, dict(id='late', expected_version=0, kind='dispatch'))
    assert deployctl.inspect(store) == before


def test_cli_runs_a_rollout(tmp_path):
    rollout = {'rollout_id': 'one', 'configuration': ONE, 'requests': [INSTALL,
               dict(id='d1', expected_version=1, kind='dispatch'),
               dict(id='r1', expected_version=2, kind='receipt', receipts=[dict(token='1:s:start:1', success=True)]),
               dict(id='d2', expected_version=3, kind='dispatch'),
               dict(id='r2', expected_version=4, kind='receipt', receipts=[dict(token='1:s:retire:1', success=True)])]}
    source = tmp_path / 'rollout.json'; source.write_text(json.dumps(rollout)); report = tmp_path / 'out' / 'report.json'
    child = subprocess.run([sys.executable, '-m', 'deployctl', 'run', '--rollout', str(source), '--store', str(tmp_path / 'db'),
                            '--report', str(report)], capture_output=True, text=True)
    assert child.returncode == 0, child.stderr
    assert json.loads(report.read_text())['final']['complete'] is True
