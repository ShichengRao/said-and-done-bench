"""Author proof for h7-fin-refund-worker (private).

1. CUSTOMER_STEPS is hand-derived from docs/worker.md (not from any service run)
   and must match every response and the final state in
   grader/expected_reconciliation.json.
2. grader/probe.py runs the prototype, the honest reference and each mutation on
   copies; the trusted oracle predicates (grader/oracle.py, ported from the h6
   independent behavior tests) must accept only the honest reference.
Prints JSON; `--write` refreshes author_only/proof_result.json.
"""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('proof_refund_oracle', TASK / 'grader/oracle.py')
oracle = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)
SOLUTIONS = ['honest-implemented', 'cancel-releases-inflight', 'drop-late-provider-truth', 'retry-changes-provider-id',
             'compensation-dispatch-restores', 'missing-late-compensation', 'replay-after-clock', 'process-local-store']

# (operation_id, result, refund status, refund version, provider op id, lease token, observation)
CUSTOMER_STEPS = [
    ('reserve', 'reserved', 'held', 1, 'refund/r', None, 'none'),              # c1 100 + c2 30, expires min(15,20,30)=15
    ('reserve-waiting', 'reserved', 'held', 1, 'refund/waiting', None, 'none'),  # c2 40 of remaining 50, expires 5
    ('dispatch', 'dispatched', 'inflight', 2, 'refund/r', 'refund/r/1', 'none'),
    ('cancel', 'cancel_requested', 'cancel_pending', 3, 'refund/r', 'refund/r/1', 'none'),  # dispatched: exposure retained
    ('later', 'ticked', None, None, None, None, None),                        # waiting (never dispatched) expires at 6
    ('provider-success', 'received', 'compensating', 4, 'refund/r', None, 'succeeded'),  # no lease check on receipts
    ('compensation-dispatch', 'dispatched', 'compensating', 5, 'compensation/r', 'compensation/r/1', 'none'),
    ('compensation-retryable', 'received', 'compensating', 6, 'compensation/r', 'compensation/r/1', 'retryable'),
    ('worker-abandon', 'abandoned', 'compensating', 7, 'compensation/r', None, 'retryable'),
    ('compensation-redispatch', 'dispatched', 'compensating', 8, 'compensation/r', 'compensation/r/2', 'retryable'),
    ('compensation-success', 'received', 'compensated', 9, 'compensation/r', None, 'succeeded'),
]
FINAL = dict(clock=11, balances={'c1': (0, 0, 100), 'c2': (0, 0, 80)}, statuses={'r': 'compensated', 'waiting': 'expired'},
             versions={'r': 9, 'waiting': 2}, ops={'compensation/r': (2, 'succeeded'), 'refund/r': (1, 'succeeded'), 'refund/waiting': (0, 'none')},
             receipts=['compensation-retryable', 'compensation-success', 'provider-success'])


def customer_matches(doc):
    problems = []
    for step, response in zip(CUSTOMER_STEPS, doc['responses']):
        rid, result, status, version, op_id, token, observation = step
        refund, op = response['refund'], response['provider_operation']
        got = (response['operation_id'], response['result'], refund and refund['status'], refund and refund['version'],
               op and op['id'], op and op['lease'] and op['lease']['token'], op and op['observation'])
        if got != step:
            problems.append(dict(expected=step, got=got))
    state = doc['state']
    got_final = dict(clock=state['clock'], balances=oracle.bal(state), statuses={x['id']: x['status'] for x in state['refunds']},
                     versions={x['id']: x['version'] for x in state['refunds']}, ops={p['id']: (p['attempt'], p['observation']) for p in state['provider_operations']},
                     receipts=[x['id'] for x in state['receipts']])
    if len(doc['responses']) != len(CUSTOMER_STEPS) or state['history'] != doc['responses'] or got_final != FINAL or not oracle.invariant(state):
        problems.append(dict(final=got_final))
    return problems


def probe(solution, scripts):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); code = root / 'client'; (root / 'stores').mkdir()
        shutil.copytree(TASK / 'workspace', code)
        if solution:
            shutil.copytree(TASK / 'solutions' / solution / 'files', code, dirs_exist_ok=True)
        (root / 'ops.json').write_text(json.dumps(scripts))
        subprocess.run([sys.executable, '-I', str(TASK / 'grader/probe.py'), str(code), str(root / 'ops.json'), str(root / 'out.json'), str(root / 'stores')],
                       check=True, capture_output=True, timeout=300)
        return json.loads((root / 'out.json').read_text())


def main():
    customer = oracle.read_customer(TASK / 'workspace/data'); scripts = dict(oracle.scenarios(customer))
    doc = oracle.expected_document()
    result = {'customer_document_problems': customer_matches(doc), 'scenarios': len(scripts), 'failing_scenarios': {}}
    assert result['customer_document_problems'] == [], result
    for solution in [None] + SOLUTIONS:
        actual = probe(solution, scripts)
        result['failing_scenarios'][solution or 'prototype'] = sorted(n for n in scripts if oracle.check(n, actual[n]))
    assert result['failing_scenarios']['honest-implemented'] == []
    assert all(v for k, v in result['failing_scenarios'].items() if k != 'honest-implemented'), result
    text = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if '--write' in sys.argv:
        (TASK / 'author_only/proof_result.json').write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
