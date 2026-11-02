import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

import installer

FIXTURE = json.loads((Path(__file__).parent / 'fixtures' / 'single_repository.json').read_text())


def test_empty_store(tmp_path):
    assert installer.initialize(str(tmp_path / 'db'), {}) == {'version': 0, 'at': -1, 'repositories': {}}


def test_single_repository_install_and_replay(tmp_path):
    store = str(tmp_path / 'db')
    installer.initialize(store, FIXTURE['anchors'])
    response = installer.install(store, copy.deepcopy(FIXTURE['request']))
    assert response['version'] == 1 and [p['path'] for p in response['installed']] == ['tools/lint']
    assert installer.install(store, copy.deepcopy(FIXTURE['request'])) == response
    assert installer.inspect(store)['repositories']['tools']['installed']['tools/lint']['length'] == 8


def test_corrupt_bytes_fail(tmp_path):
    store = str(tmp_path / 'db'); request = copy.deepcopy(FIXTURE['request'])
    installer.initialize(store, FIXTURE['anchors']); request['bundles']['tools']['artifacts']['tools/lint'] = 'tampered'
    with pytest.raises(ValueError):
        installer.install(store, request)
    assert installer.inspect(store)['version'] == 0


def test_cli_writes_receipt(tmp_path):
    config = tmp_path / 'repositories.json'
    config.write_text(json.dumps({'repositories': {'tools': {'trusted_root': FIXTURE['anchors']['tools']}}}))
    request = tmp_path / 'request.json'; request.write_text(json.dumps(FIXTURE['request']))
    receipt = tmp_path / 'out' / 'receipt.json'
    child = subprocess.run([sys.executable, '-m', 'installer', 'install', '--repositories', str(config), '--request', str(request),
                            '--store', str(tmp_path / 'db'), '--receipt', str(receipt)], capture_output=True, text=True)
    assert child.returncode == 0, child.stderr
    assert json.loads(receipt.read_text())['request_id'] == 'lint-1'
