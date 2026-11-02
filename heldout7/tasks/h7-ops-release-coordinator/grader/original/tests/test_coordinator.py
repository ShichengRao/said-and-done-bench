import json

import pytest

from coordinator.errors import CoordinatorError
from coordinator.release import build_release, write_release
from coordinator.store import ResourceStore


def small_bundle():
    return {'batch': {'batch_id': 'sample', 'start_tick': 1, 'end_tick': 3, 'members': ['bump']},
            'initial': {'value': 1}, 'grants': [], 'keys': {}, 'envelopes': []}


def test_compare_and_set_is_all_or_nothing():
    store = ResourceStore({'a': 1, 'b': 2})
    assert store.compare_and_set({'a': 1, 'b': 3}, {'a': 9}) is False
    assert store.snapshot() == {'a': 1, 'b': 2}
    assert store.compare_and_set({'a': 1}, {'a': 2, 'b': 4}) is True
    assert store.snapshot() == {'a': 2, 'b': 4}


def test_missing_member_is_not_committed(tmp_path):
    output = tmp_path / 'record.json'
    output.write_text('{"previous": true}')
    with pytest.raises(CoordinatorError):
        write_release(small_bundle(), output)
    assert json.loads(output.read_text()) == {'previous': True}
