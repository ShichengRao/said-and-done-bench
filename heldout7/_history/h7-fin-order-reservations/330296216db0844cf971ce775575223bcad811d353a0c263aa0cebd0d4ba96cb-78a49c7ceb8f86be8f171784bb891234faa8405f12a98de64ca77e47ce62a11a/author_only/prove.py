"""Author proof for h7-fin-order-reservations (private).

The independent exhaustive oracle model (grader/oracle.py) and the reference
service (solutions/honest-implemented, h6 honest engine) must agree on the
customer update and every probe scenario (run through grader/probe.py on a copy);
the prototype and each mutation must diverge. Also checks the customer facts:
each replacement alone is unavailable, the joint exchange succeeds.
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
spec = importlib.util.spec_from_file_location('proof_procurement_oracle', TASK / 'grader/oracle.py')
oracle = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)
SOLUTIONS = ['honest-implemented', 'sequential-exchange', 'retain-selected-holds', 'greedy-unit-choice', 'release-before-replan',
             'replay-after-clock', 'ignore-unrelated-holds', 'process-local-store']


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
    doc = oracle.expected_document(customer); result = {'scenarios': len(scripts), 'mismatched': {}}
    for solution in [None] + SOLUTIONS:
        actual = probe(solution, scripts)
        result['mismatched'][solution or 'prototype'] = sorted(n for n, ops in scripts.items() if actual[n] != oracle.expected_outputs(ops, actual[n]))
    assert result['mismatched']['honest-implemented'] == []
    assert all(result['mismatched'][s] for s in result['mismatched'] if s != 'honest-implemented')
    store = oracle.Store(); store.initialize(customer['catalog'])
    for command in customer['commands'][:-1]:
        store.apply(command)
    batch = customer['commands'][-1]; alone = {}
    for e in batch['entries']:
        saved = __import__('copy').deepcopy(store.s)
        alone[e['basket']] = store.apply(dict(batch, operation_id='alone-' + e['basket'], entries=[e]))['result']; store.s = saved
    result['customer'] = dict(each_replacement_alone=alone, joint=doc['responses'][-1]['result'],
                              replaced={b['id']: dict(version=b['version'], cost=b['cost'], units=b['units']) for b in doc['responses'][-1]['baskets']},
                              available_after=[r['available'] for r in doc['state']['stock']])
    assert alone == {'a': 'unavailable', 'b': 'unavailable'} and result['customer']['joint'] == 'exchanged'
    text = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if '--write' in sys.argv:
        (TASK / 'author_only/proof_result.json').write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
