"""Trusted refund-worker scenarios and checks; never imports candidate code.

Scenarios port the h6 independent behavior tests into probe operations; their
hand-written expectations become predicates over the raw probe outputs. The
customer reconciliation is pinned in expected_reconciliation.json, whose every
step is independently checked against CUSTOMER_STEPS (hand-derived from the
contract) by author_only/prove.py.
"""
import copy
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
V = '@current'  # probe substitutes refund r's current version from snapshot
ERR = {'error': 'ValueError'}


def captures():
    return [dict(id='c1', merchant='m', currency='USD', captured_cents=100, refund_until=20), dict(id='c2', merchant='m', currency='USD', captured_cents=80, refund_until=30)]


def op(command, tag=None, kind='apply'):
    return dict(op=kind, command=command, tag=tag)


def cmd(operation_id, kind, at=1, **kw):
    return dict(operation_id=operation_id, kind=kind, at=at, **kw)


def setup(cents=70):
    return [dict(op='init', captures=captures(), tag='init'),
            op(cmd('reserve', 'reserve', 1, refund='r', merchant='m', currency='USD', cents=cents, until=15, candidates=['c1', 'c2']), 'reserve')]


def dispatch(name='dispatch', at=1, until=5, kind='refund', tag=None, version=V, worker='worker'):
    return op(cmd(name, 'dispatch', at, refund='r', expected_version=version, provider_kind=kind, worker=worker, until=until), tag or name)


def cancel(at=2, tag='cancel'):
    return op(cmd('cancel', 'cancel', at, refund='r', expected_version=V), tag)


def receipt(name, result, at=2, kind='refund', receipt_id=None, tag=None):
    return op(cmd(name, 'receipt', at, receipt_id=receipt_id or name, provider_operation=kind + '/r', result=result), tag or name)


def tick(name, at, tag=None):
    return op(cmd(name, 'tick', at), tag or name)


def snap(tag):
    return dict(op='snapshot', tag=tag)


def read_customer(data_dir):
    return json.loads((Path(data_dir) / 'provider_history.json').read_text())


def scenarios(customer):
    yield 'customer_history', [dict(op='init', captures=customer['captures'], tag='init')] + [op(c, 'step%d' % i) for i, c in enumerate(customer['commands'])] + [snap('final')]
    yield 'cancel_inflight_retains_exposure_then_compensates', setup() + [dispatch(), cancel(), snap('s1'), tick('later', 6), receipt('late-success', 'succeeded', 6), snap('s2'),
        dispatch('comp-dispatch', 7, 10, 'compensation'), snap('s3'), receipt('comp-retry', 'retryable', 8, 'compensation'),
        op(cmd('abandon', 'abandon', 8, provider_operation='compensation/r', lease_token='compensation/r/1'), 'abandon'),
        dispatch('comp-dispatch-2', 9, 10, 'compensation'), receipt('comp-success', 'succeeded', 11, 'compensation'), snap('s4')]
    yield 'cancel_before_dispatch_releases', setup() + [cancel(), snap('s1'), dispatch(at=2)]
    yield 'success_then_cancel_compensates', setup() + [dispatch(), receipt('success', 'succeeded'), cancel(), dispatch('comp', 2, 5, 'compensation'),
                                                         receipt('done', 'succeeded', 3, 'compensation'), snap('s1')]
    yield 'stale_lease_fenced_receipt_not', setup() + [dispatch('dispatch'), dispatch('retry', 5, 8), snap('old'),
        op(cmd('old-worker', 'abandon', 5, provider_operation='refund/r', lease_token='refund/r/1'), 'abandon'), snap('after'), receipt('truth', 'succeeded', 9), snap('s1')]
    yield 'duplicate_and_out_of_order_receipts', setup() + [dispatch(), receipt('success', 'succeeded'), snap('v'), receipt('same-command-new-id', 'succeeded', receipt_id='success'),
        receipt('old-accepted', 'accepted'), receipt('same-truth', 'succeeded'), snap('before'), receipt('conflict', 'failed'),
        receipt('reused-receipt', 'accepted', receipt_id='success'), snap('after')]
    yield 'compensation_failure_keeps_refund_paid', setup(130) + [dispatch(), cancel(), receipt('success', 'succeeded'), dispatch('comp', 2, 5, 'compensation'),
                                                                 receipt('comp-failure', 'failed', 3, 'compensation'), snap('s1')]
    yield 'original_failure_releases_exposure', setup() + [dispatch(), cancel(), receipt('failed', 'failed'), snap('s1')]
    yield 'deadline_expiry_and_error_rollback', setup() + [snap('before'), dispatch(at=16, until=20), snap('after'), tick('clock', 16), snap('s1')]
    yield 'dispatched_exposure_never_expires', setup() + [dispatch(), tick('clock', 40), snap('s1'), receipt('success', 'succeeded', 41), snap('s2')]
    yield 'reservation_windows_and_atomic_unavailable', setup(130) + [
        op(cmd('more', 'reserve', 2, refund='other', merchant='m', currency='USD', cents=60, until=10, candidates=['c1', 'c2']), 'more'), snap('s1'),
        op(cmd('bad-route', 'reserve', 2, refund='other', merchant='m', currency='USD', cents=1, until=10, candidates=['c2', 'unknown']), 'bad'),
        op(cmd('small', 'reserve', 2, refund='other', merchant='m', currency='USD', cents=50, until=40, candidates=['c1', 'c2']), 'small'), snap('s2')]
    send = cmd('send', 'dispatch', 1, refund='r', expected_version=1, provider_kind='refund', worker='w', until=5)
    yield 'replay_before_clock_and_isolation', setup() + [op(send, 'first', 'apply_mutate'), tick('tick', 6), op(send, 'replay'), op(dict(send, at=6), 'changed')]
    for index, order in enumerate(itertools.permutations(['accepted', 'retryable', 'succeeded'])):
        steps = setup(130) + [dispatch(), cancel()]
        for i, event in enumerate(order):
            steps += [receipt(str(i), event, 2), snap('inv%d' % i)]
        yield 'observation_order_%d' % index, steps + [snap('mid'), dispatch('comp', 3, 4, 'compensation'), receipt('compdone', 'succeeded', 5, 'compensation'), snap('end')]
    yield 'fresh_process_snapshot_and_replay', setup() + [op(send, 'first'), cancel(), snap('s1'), op(send, 'child', 'subprocess')]
    yield 'concurrent_dispatch_single_lease', setup() + [dict(op='concurrent', tag='race', commands=[dict(send, operation_id=str(i), worker=str(i)) for i in range(2)]), snap('s1')]


def bal(snapshot):
    return {c['id']: (c['held_cents'], c['refunded_cents'], c['available_cents']) for c in snapshot['captures']}


def invariant(snapshot):
    return all(c['held_cents'] >= 0 and c['refunded_cents'] >= 0 and c['available_cents'] >= 0 and
               c['captured_cents'] == c['held_cents'] + c['refunded_cents'] + c['available_cents'] for c in snapshot['captures'])


def status(response):
    return response['refund']['status']


def version_of(snapshot):
    return next(x['version'] for x in snapshot['refunds'] if x['id'] == 'r')


def expected_document():
    return json.loads((HERE / 'expected_reconciliation.json').read_text())


def check(name, out):
    """Return failed expectation descriptions for one scenario (out: tag -> output)."""
    expectations = []
    def want(label, fn):
        try:
            ok = bool(fn())
        except Exception:  # noqa: BLE001 - malformed candidate output fails the expectation
            ok = False
        if not ok:
            expectations.append(label)
    if name == 'customer_history':
        doc = expected_document()
        for i, response in enumerate(doc['responses']):
            want('step %d response' % i, lambda i=i, response=response: out['step%d' % i] == response)
        want('final snapshot', lambda: out['final'] == doc['state'])
    elif name == 'cancel_inflight_retains_exposure_then_compensates':
        want('cancel_pending', lambda: status(out['cancel']) == 'cancel_pending')
        want('exposure retained', lambda: bal(out['s1'])['c1'] == (70, 0, 30))
        want('late success compensating', lambda: status(out['late-success']) == 'compensating' and bal(out['s2'])['c1'] == (0, 70, 30))
        want('compensation dispatch does not restore', lambda: bal(out['s3'])['c1'] == (0, 70, 30))
        want('abandon accepted', lambda: out['abandon']['result'] == 'abandoned')
        want('stable compensation id and new token', lambda: out['comp-dispatch-2']['provider_operation']['id'] == 'compensation/r' and out['comp-dispatch-2']['provider_operation']['lease']['token'] == 'compensation/r/2')
        want('compensated restores', lambda: status(out['comp-success']) == 'compensated' and bal(out['s4'])['c1'] == (0, 0, 100) and invariant(out['s4']))
    elif name == 'cancel_before_dispatch_releases':
        want('released', lambda: bal(out['s1'])['c1'] == (0, 0, 100))
        want('dispatch rejected', lambda: out['dispatch'] == ERR)
    elif name == 'success_then_cancel_compensates':
        want('compensating via compensation op', lambda: status(out['cancel']) == 'compensating' and out['cancel']['provider_operation']['id'] == 'compensation/r')
        want('restored', lambda: bal(out['s1'])['c1'] == (0, 0, 100))
    elif name == 'stale_lease_fenced_receipt_not':
        want('same stable id', lambda: out['dispatch']['provider_operation']['id'] == out['retry']['provider_operation']['id'] == 'refund/r')
        want('stale abandon rejected without change', lambda: out['abandon'] == ERR and out['after'] == out['old'])
        want('late truth applied', lambda: bal(out['s1'])['c1'] == (0, 70, 30))
    elif name == 'duplicate_and_out_of_order_receipts':
        want('receipt replayed bumps version', lambda: out['same-command-new-id']['result'] == 'receipt_replayed' and out['same-command-new-id']['refund']['version'] == version_of(out['v']) + 1)
        want('late accepted ignored', lambda: out['old-accepted']['result'] == 'receipt_ignored' and status(out['old-accepted']) == 'succeeded')
        want('identical truth received', lambda: out['same-truth']['result'] == 'received' and bal(out['before'])['c1'] == (0, 70, 30))
        want('conflicts rejected and rolled back', lambda: out['conflict'] == ERR and out['reused-receipt'] == ERR and out['after'] == out['before'])
    elif name == 'compensation_failure_keeps_refund_paid':
        want('compensation_failed', lambda: status(out['comp-failure']) == 'compensation_failed')
        want('principal stays refunded', lambda: bal(out['s1']) == {'c1': (0, 100, 0), 'c2': (0, 30, 50)} and invariant(out['s1']))
    elif name == 'original_failure_releases_exposure':
        want('cancelled and released', lambda: status(out['failed']) == 'cancelled' and bal(out['s1'])['c1'] == (0, 0, 100))
        want('no compensation op', lambda: len(out['s1']['provider_operations']) == 1)
    elif name == 'deadline_expiry_and_error_rollback':
        want('late dispatch rejected and rolled back', lambda: out['dispatch'] == ERR and out['after'] == out['before'])
        want('expired releases', lambda: out['s1']['refunds'][0]['status'] == 'expired' and bal(out['s1'])['c1'] == (0, 0, 100))
    elif name == 'dispatched_exposure_never_expires':
        want('still inflight', lambda: out['s1']['refunds'][0]['status'] == 'inflight' and bal(out['s1'])['c1'] == (70, 0, 30))
        want('late success', lambda: bal(out['s2'])['c1'] == (0, 70, 30))
    elif name == 'reservation_windows_and_atomic_unavailable':
        want('unavailable no partial', lambda: out['more']['result'] == 'unavailable' and out['more']['refund'] is None and len(out['s1']['refunds']) == 1)
        want('unknown candidate rejected', lambda: out['bad'] == ERR)
        want('expiry from used capture', lambda: out['small']['refund']['expires'] == 30 and invariant(out['s2']))
    elif name == 'replay_before_clock_and_isolation':
        want('replay returns original', lambda: out['replay'] == out['first'] and out['first']['result'] == 'dispatched')
        want('changed reuse rejected', lambda: out['changed'] == ERR)
    elif name.startswith('observation_order_'):
        want('invariant after each receipt', lambda: all(invariant(out['inv%d' % i]) for i in range(3)))
        want('paid principal', lambda: bal(out['mid']) == {'c1': (0, 100, 0), 'c2': (0, 30, 50)})
        want('compensation restores', lambda: bal(out['end']) == {'c1': (0, 0, 100), 'c2': (0, 0, 80)})
    elif name == 'fresh_process_snapshot_and_replay':
        want('fresh process sees committed state', lambda: out['child']['snapshot'] == out['s1'])
        want('fresh process replay', lambda: out['child']['replay'] == out['first'])
    elif name == 'concurrent_dispatch_single_lease':
        tokens = lambda: [x['provider_operation']['lease']['token'] if x != ERR else None for x in out['race']]  # noqa: E731
        want('exactly one lease', lambda: sorted(tokens(), key=str) == [None, 'refund/r/1'] and invariant(out['s1']))
    else:
        expectations.append('unknown scenario')
    return expectations


def cli_inputs(customer):
    steps = [s['command'] for s in setup(130)[1:]] + [dict(s['command'], expected_version=v) for s, v in [
        (dispatch(), 1), (cancel(), 2), (receipt('success', 'succeeded'), None), (dispatch('comp', 2, 5, 'compensation'), 4), (receipt('comp-failure', 'failed', 3, 'compensation'), None)]]
    for s in steps:
        if s.get('expected_version') is None:
            s.pop('expected_version', None)
    nearby = {'customer': 'Nearby Outfitters (fictional)', 'captures': captures(), 'commands': steps}
    failing = copy.deepcopy(customer); failing['commands'].append(dict(customer['commands'][-1], operation_id='reused-receipt', result='failed', at=12))
    return {'customer': customer, 'nearby': nearby, 'failing': failing}


def check_nearby_document(doc):
    try:
        state = doc['state']; statuses = {r['id']: r['status'] for r in state['refunds']}
        return (len(doc['responses']) == 6 and statuses == {'r': 'compensation_failed'} and bal(state) == {'c1': (0, 100, 0), 'c2': (0, 30, 50)}
                and invariant(state) and len(state['history']) == 6 and [p['id'] for p in state['provider_operations']] == ['compensation/r', 'refund/r'])
    except (KeyError, TypeError, AttributeError):
        return False
