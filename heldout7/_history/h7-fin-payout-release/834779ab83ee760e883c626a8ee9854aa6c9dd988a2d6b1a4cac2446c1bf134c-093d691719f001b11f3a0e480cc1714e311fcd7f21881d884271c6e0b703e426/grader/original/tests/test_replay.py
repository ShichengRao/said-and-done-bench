import copy
import pytest
from payout_release.authority import resolve
from payout_release.errors import ReplayError
from payout_release.replay import ReplayWorker
from helpers import row, small_batch


def test_dispatch_debits_and_receipt_credits():
    b = small_batch(); worker = ReplayWorker(b['accounts'], resolve(b))
    worker.apply('dispatch:one')
    assert worker.balances == {'A': 0, 'B': 0}
    assert worker.replay(['receipt:one']) == {'settled': ['one'], 'active_bridge': None, 'balances': {'A': 0, 'B': 3}, 'complete': True}


def test_no_overdraft_and_rejected_step_leaves_state():
    b = small_batch(); b['accounts'][0]['balance'] = 2; worker = ReplayWorker(b['accounts'], resolve(b))
    with pytest.raises(ReplayError):
        worker.apply('dispatch:one')
    assert worker.balances == {'A': 2, 'B': 0} and not worker.dispatched


def test_bridge_must_be_repaid_after_release_receipt():
    b = small_batch(); b['accounts'][0]['balance'] = 1
    b['bridges'] = [row(id='L', owner='alice', cents=2, activate_after=[], release_after=['one'])]
    worker = ReplayWorker(b['accounts'], resolve(b))
    result = worker.replay(['draw:L', 'dispatch:one', 'receipt:one'])
    assert result['active_bridge'] == 'L' and not result['complete']
    with pytest.raises(ReplayError):
        worker.apply('repay:L')  # alice has no cash left to repay


def test_unsigned_draft_does_not_replace_signed_instruction():
    b = small_batch(); draft = copy.deepcopy(b['payouts'][0]); draft.update(revision=2, signed=False, cents=1)
    b['payouts'].append(draft)
    assert resolve(b)['payouts'][0]['cents'] == 3
