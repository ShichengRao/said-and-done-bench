import copy
import json
from pathlib import Path

from reconcile.records import load
from reconcile.reservations import availability, replay
from reconcile.routing import route_options
from reconcile.runner import build, main
from reconcile.scheduler import ScheduleError, schedule

DATA = Path(__file__).resolve().parent.parent / 'data'


def plan(batch, ledger):
    return schedule(batch, route_options(batch), availability(batch, replay(batch, ledger)))


def test_ledger_replay_at_cutoff():
    batch, ledger = load(DATA)
    state = replay(batch, ledger)
    assert state['spent-C']['state'] == 'committed' and state['spent-C']['attempt'] == 'accepted-C'
    assert state['held-C-late']['state'] == 'held' and state['expired']['state'] == 'expired'
    available = availability(batch, state)
    assert available['A'] == {'10': 3, '11': 6, '12': 9} and available['B'] == {'10': 3, '11': 3, '12': 5}
    assert available['C'] == {'10': 3, '11': 3, '12': 6} and available['D'] == {'10': 3, '11': 5, '12': 6}


def test_rejected_retry_and_timeout_change_nothing():
    batch, ledger = load(DATA)
    trimmed = copy.deepcopy(ledger)
    trimmed['receipts'] = [r for r in trimmed['receipts'] if r['id'] not in ('reject-replacement', 'ack-C-replay')]
    assert availability(batch, replay(batch, trimmed)) == availability(batch, replay(batch, ledger))


def test_supplied_batch_cannot_be_scheduled(tmp_path):
    target = tmp_path / 'schedule.json'
    assert main(['--data', str(DATA), '--output', str(target)]) != 0 and not target.exists()


def test_one_more_c_unit_admits_schedule():
    batch, ledger = load(DATA)
    batch['budgets']['C'] += 1
    calls = {c['request']: (c['route'], c['start']) for c in build(batch, ledger)['calls']}
    assert calls == {'request-0': ('request-0-via-A', 10), 'request-1': ('request-1-via-AC', 11),
                     'request-2': ('request-2-via-AC', 11), 'request-3': ('request-3-via-B', 12),
                     'request-4': ('request-4-via-AD', 12), 'request-5': ('request-5-via-BD', 10)}


def test_backtracks_past_greedy_choice():
    batch, ledger = load(DATA)
    batch['requests'] = [q for q in batch['requests'] if q['id'] != 'request-5']
    batch['routes'] = [r for r in batch['routes'] if r['request'] != 'request-5']
    assert sorted(plan(batch, ledger)) == ['request-%d' % i for i in range(5)]


def test_allowance_stays_spent_at_later_starts():
    batch, ledger = load(DATA)
    batch['budgets']['C'] += 1
    chosen = plan(batch, ledger)
    available = availability(batch, replay(batch, ledger))
    units = {q['id']: q['units'] for q in batch['requests']}
    for pool, row in available.items():
        for t in batch['slots']:
            assert sum(units[r] for r, o in chosen.items() if pool in o['pools'] and o['start'] <= t) <= row[str(t)]
