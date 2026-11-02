import copy
import json
from pathlib import Path

import pytest

import deployctl

ROLLOUT = json.loads((Path(__file__).resolve().parent.parent / 'data' / 'rollout.json').read_text())
CONFIG = ROLLOUT['configuration']; INSTALL = ROLLOUT['requests'][0]


def call(store, kind, **kw):
    v = deployctl.inspect(store)['version']
    return deployctl.apply(store, dict(id=f'r{v}', expected_version=v, kind=kind, **kw))


def receipts(store, *pairs):
    return call(store, 'receipt', receipts=[dict(token=t, success=s) for t, s in pairs])


def installed(tmp_path):
    store = str(tmp_path / 'db'); deployctl.initialize(store, CONFIG); deployctl.apply(store, copy.deepcopy(INSTALL)); return store


def test_first_dispatch_only_starts_a_pair_that_survives_any_one_failure(tmp_path):
    assert call(installed(tmp_path), 'dispatch')['created'] == ['1:billing:start:1', '1:checkout:start:1']


def test_readiness_does_not_free_the_source_until_retirement_is_acknowledged(tmp_path):
    store = installed(tmp_path); call(store, 'dispatch')
    ready = receipts(store, ('1:billing:start:1', True))
    assert ready['observed']['edge-b'] is not None and ready['handoffs']['billing']['phase'] == 'ready' and ready['done'] == []
    retire = call(store, 'dispatch')
    assert retire['created'] == ['1:billing:retire:1'] and retire['observed']['edge-b'] is not None
    done = receipts(store, ('1:billing:retire:1', True))
    assert done['observed']['edge-b'] is None and done['done'] == ['billing']


@pytest.mark.parametrize('outcomes', [(True, True), (False, True), (True, False)])
def test_each_initial_outcome_recovers_to_completion(tmp_path, outcomes):
    store = installed(tmp_path); first = call(store, 'dispatch')['created']; receipts(store, *zip(first, outcomes))
    for _ in range(20):
        if deployctl.inspect(store)['complete']:
            break
        pending = call(store, 'dispatch')['pending']; assert pending
        receipts(store, *[(t, True) for t in reversed(pending)])
    assert deployctl.inspect(store)['complete']


def test_conflicting_receipt_rejects_whole_batch(tmp_path):
    store = installed(tmp_path); a, b = call(store, 'dispatch')['created']; receipts(store, (a, True), (b, False))
    before = deployctl.inspect(store)
    with pytest.raises(ValueError):
        receipts(store, (b, True))
    assert deployctl.inspect(store) == before


def test_new_epoch_requires_drained_handoffs(tmp_path):
    store = installed(tmp_path); a, b = call(store, 'dispatch')['created']; receipts(store, (a, True), (b, False))
    with pytest.raises(ValueError):
        call(store, 'install', **{k: v for k, v in INSTALL.items() if k not in ('id', 'expected_version', 'kind')} | {'epoch': 2})


def test_request_id_reuse_with_different_payload_is_rejected(tmp_path):
    store = installed(tmp_path); deployctl.apply(store, dict(id='same', expected_version=1, kind='dispatch'))
    with pytest.raises(ValueError):
        deployctl.apply(store, dict(id='same', expected_version=2, kind='dispatch'))
