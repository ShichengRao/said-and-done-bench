import copy
import json
import subprocess
import sys
from pathlib import Path
import pytest
from meter_billing import service

CONFIG = {'periods': [{'id': 'p1', 'start': 0, 'end': 10, 'cycle': 'm'}, {'id': 'p2', 'start': 10, 'end': 20, 'cycle': 'm'}],
          'meters': [{'id': 'a', 'account': 'alice', 'pool': 'shared'}, {'id': 'b', 'account': 'bob', 'pool': 'shared'}],
          'pools': [{'id': 'shared', 'tiers': [{'up_to': 5, 'millicents': 1000}, {'up_to': None, 'millicents': 250}]}]}


def row(i, meter, at, counter, revision=1, known=0, void=False, epoch='e1'):
    return dict(id=i, revision=revision, known=known, meter=meter, epoch=epoch, at=at, counter=counter, void=void)


def store(tmp_path):
    path = str(tmp_path / 'b.db'); service.initialize(path, CONFIG); return path


def test_middle_correction_moves_units_between_adjacent_periods(tmp_path):
    p = store(tmp_path)
    service.close(p, dict(operation_id='one', as_of=1, readings=[row('x', 'a', 0, 0), row('y', 'a', 10, 4), row('z', 'a', 20, 8)]))
    second = service.close(p, dict(operation_id='two', as_of=2, readings=[row('y', 'a', 10, 6, revision=2, known=2)]))
    assert [(r['period'], r['units_delta']) for r in second['postings']] == [('p1', 2), ('p2', -2)]


def test_retraction_zeroes_retained_lines_and_reprices_pool(tmp_path):
    p = store(tmp_path)
    service.close(p, dict(operation_id='one', as_of=1, readings=[row('x', 'a', 0, 0), row('y', 'a', 20, 4), row('q', 'b', 0, 0), row('r', 'b', 20, 6)]))
    out = service.close(p, dict(operation_id='void', as_of=2, readings=[row('r', 'b', 20, 6, revision=2, known=2, void=True)]))
    lines = {(t['period'], t['meter']): t for t in out['targets']}
    assert lines[('p1', 'b')]['units'] == lines[('p1', 'b')]['cents'] == 0
    assert sum(t['cents'] for t in out['targets']) == 4  # alice now gets the cheap tier alone


def test_replay_returns_original_and_does_not_bill_twice(tmp_path):
    p = store(tmp_path); cmd = dict(operation_id='one', as_of=1, readings=[row('x', 'a', 0, 0), row('y', 'a', 20, 7)])
    first = service.close(p, copy.deepcopy(cmd)); service.close(p, dict(operation_id='later', as_of=9, readings=[]))
    assert service.close(p, copy.deepcopy(cmd)) == first
    assert len(service.snapshot(p)['history']) == 2
    with pytest.raises(ValueError):
        service.close(p, dict(cmd, as_of=10))


def test_rejected_close_rolls_back(tmp_path):
    p = store(tmp_path); service.close(p, dict(operation_id='one', as_of=1, readings=[row('x', 'a', 0, 5), row('y', 'a', 10, 7)]))
    before = service.snapshot(p)
    with pytest.raises(ValueError):
        service.close(p, dict(operation_id='bad', as_of=2, readings=[row('z', 'a', 20, 6)]))
    assert service.snapshot(p) == before


def test_customer_history_cli_is_idempotent(tmp_path):
    root = Path(__file__).resolve().parent.parent
    args = [sys.executable, '-m', 'meter_billing', 'replay', '--history', str(root / 'data/customer_history.json'),
            '--store', str(tmp_path / 's.db'), '--output', str(tmp_path / 'out.json')]
    assert subprocess.run(args, cwd=root, capture_output=True).returncode == 0
    first = json.loads((tmp_path / 'out.json').read_text())
    assert subprocess.run(args, cwd=root, capture_output=True).returncode == 0
    assert json.loads((tmp_path / 'out.json').read_text()) == first
    assert first['clock'] == 7 and sum(t['cents'] for t in first['targets']) == 6
