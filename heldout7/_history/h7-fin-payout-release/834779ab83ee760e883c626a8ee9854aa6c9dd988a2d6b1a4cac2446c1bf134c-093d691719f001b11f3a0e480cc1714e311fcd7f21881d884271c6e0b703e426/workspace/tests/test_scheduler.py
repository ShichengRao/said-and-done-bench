from payout_release.authority import resolve
from payout_release.replay import ReplayWorker
from payout_release.scheduler import plan_release
from helpers import row, small_batch


def replayed(batch, plan):
    return ReplayWorker(batch['accounts'], resolve(batch)).replay(plan)


def test_simple_batch():
    b = small_batch(); plan = plan_release(b)
    assert replayed(b, plan)['complete']


def test_later_dispatch_waits_for_actual_receipt():
    b = small_batch(); b['accounts'].append(dict(id='C', balance=0))
    b['owners'].append(row(id='carol', wallet='C'))
    b['payouts'].append(row(id='two', source_owner='bob', destination_owner='carol', cents=3, receipt_after=[]))
    b['payouts'][0]['receipt_after'] = ['two']  # provider holds 'one' until 'two' is dispatched
    b['bridges'] = [row(id='L', owner='bob', cents=3, activate_after=[], release_after=['one'])]
    plan = plan_release(b)
    assert replayed(b, plan)['complete']
    assert plan.index('draw:L') < plan.index('dispatch:two') < plan.index('receipt:one') < plan.index('repay:L')
