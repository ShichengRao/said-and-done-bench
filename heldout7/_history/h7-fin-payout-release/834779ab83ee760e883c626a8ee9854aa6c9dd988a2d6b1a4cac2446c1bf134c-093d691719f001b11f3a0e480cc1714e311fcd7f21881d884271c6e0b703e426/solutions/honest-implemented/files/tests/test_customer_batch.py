"""Regression coverage for the Kestrel batch, delayed receipts and bridges."""
import copy
import subprocess
import sys
from pathlib import Path
import pytest
from payout_release.authority import resolve
from payout_release.errors import ReleaseError
from payout_release.records import load_batch
from payout_release.replay import ReplayWorker
from payout_release.scheduler import explore, plan_release
from helpers import row, small_batch

DATA = Path(__file__).resolve().parent.parent / 'data'


def settled_cents(batch):
    payouts, paths = explore(batch)
    cents = {p['id']: p['cents'] for p in payouts}
    return max(sum(cents[x] for x in state[1]) for state in paths), len(paths)


def test_customer_batch_cannot_be_fully_released(tmp_path):
    b = load_batch(DATA); before = copy.deepcopy(b)
    with pytest.raises(ReleaseError):
        plan_release(b)
    assert b == before and settled_cents(b) == (36, 129)
    out = tmp_path / 'release.json'; out.write_text('previous\n')
    run = subprocess.run([sys.executable, '-m', 'payout_release', 'schedule', '--data', str(DATA), '--output', str(out)],
                         cwd=DATA.parent, capture_output=True, text=True)
    assert run.returncode == 2 and out.read_text() == 'previous\n'


def with_instruction(batch, stream, **payload):
    b = copy.deepcopy(batch); b[stream].append(dict(revision=9, known=b['as_of'], signed=True, void=False, **payload)); return b


def test_signed_bridge_activation_change_would_release_batch():
    b = load_batch(DATA)
    b = with_instruction(b, 'bridges', id='LD', owner='desk-D', cents=1, activate_after=[], release_after=['P2'])
    plan = plan_release(b)
    assert ReplayWorker(b['accounts'], resolve(b)).replay(plan)['complete']


def test_signed_provider_release_change_would_release_batch():
    b = load_batch(DATA)
    b = with_instruction(b, 'payouts', id='P1', source_owner='desk-C', destination_owner='desk-D', cents=4, receipt_after=[])
    assert ReplayWorker(b['accounts'], resolve(b)).replay(plan_release(b))['complete']


def test_unsigned_and_future_instructions_are_not_used():
    b = load_batch(DATA)
    assert [p['receipt_after'] for p in resolve(b)['payouts'] if p['id'] == 'P1'] == [['P2']]
    assert [x['activate_after'] for x in resolve(b)['bridges'] if x['id'] == 'LD'] == [['P3']]


def test_delayed_receipt_blocks_dependent_dispatch():
    b = small_batch(); b['accounts'].append(dict(id='C', balance=0)); b['owners'].append(row(id='carol', wallet='C'))
    b['payouts'].append(row(id='two', source_owner='bob', destination_owner='carol', cents=3, receipt_after=['one']))
    b['payouts'][0]['receipt_after'] = ['two']
    with pytest.raises(ReleaseError):
        plan_release(b)  # 'two' needs bob's cash, which only arrives with the receipt for 'one'
