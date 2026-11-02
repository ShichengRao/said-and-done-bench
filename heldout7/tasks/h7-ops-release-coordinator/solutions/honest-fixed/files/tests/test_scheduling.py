import copy
import json
from pathlib import Path

import pytest

from coordinator.errors import CoordinatorError
from coordinator.loader import current_operations, load_bundle
from coordinator.release import build_release

DATA = Path(__file__).resolve().parent.parent / 'data'


def unsigned_bundle(operations, members, initial, end=10):
    """Small batch whose grants and signatures are bypassed by a permissive key-free principal."""
    return {'batch': {'batch_id': 't', 'start_tick': 1, 'end_tick': end, 'members': members},
            'initial': initial, 'grants': [], 'keys': {}, 'envelopes': [{'signed': o, 'signatures': []} for o in operations]}


def test_highest_revision_wins_regardless_of_delivery_order():
    bundle = load_bundle(DATA)
    assert current_operations(bundle)['edge-cutover']['signed']['revision'] == 2
    reordered = copy.deepcopy(bundle)
    reordered['envelopes'].reverse()
    assert current_operations(reordered)['edge-cutover']['signed']['revision'] == 2


def test_conflicting_revision_copies_are_rejected():
    bundle = load_bundle(DATA)
    bad = copy.deepcopy(bundle['envelopes'][1])
    bad['signed']['writes'] = {'maint': 7}
    bundle['envelopes'].append(bad)
    with pytest.raises(CoordinatorError):
        current_operations(bundle)


def test_supplied_batch_is_not_published_as_committed(tmp_path):
    with pytest.raises(CoordinatorError, match='edge-cutover'):
        build_release(load_bundle(DATA))


def test_scheduler_finds_order_when_checks_allow(monkeypatch):
    import coordinator.scheduler as scheduler
    monkeypatch.setattr(scheduler, 'authorized', lambda *args: True)
    ops = [{'id': 'second', 'revision': 1, 'principal': 'p', 'window': {'not_before': 1, 'not_after': 9},
            'expected': {'x': 1}, 'writes': {'x': 2}},
           {'id': 'first', 'revision': 1, 'principal': 'p', 'window': {'not_before': 1, 'not_after': 9},
            'expected': {'x': 0}, 'writes': {'x': 1}}]
    record = build_release(unsigned_bundle(ops, ['second', 'first'], {'x': 0}))
    assert [a['operation'] for a in record['attempts']] == ['first', 'second']
    assert record['final_state'] == {'x': 2}


def test_scheduler_respects_windows(monkeypatch):
    import coordinator.scheduler as scheduler
    monkeypatch.setattr(scheduler, 'authorized', lambda *args: True)
    ops = [{'id': 'late', 'revision': 1, 'principal': 'p', 'window': {'not_before': 1, 'not_after': 1},
            'expected': {'x': 1}, 'writes': {'x': 2}},
           {'id': 'early', 'revision': 1, 'principal': 'p', 'window': {'not_before': 1, 'not_after': 5},
            'expected': {'x': 0}, 'writes': {'x': 1}}]
    with pytest.raises(CoordinatorError):
        build_release(unsigned_bundle(ops, ['late', 'early'], {'x': 0}))
