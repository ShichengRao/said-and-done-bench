"""Author proof for h7-fin-meter-adjustments (private).

The independent oracle model (grader/oracle.py, Fraction allocation and literal
per-unit pricing) and the reference service (solutions/honest-implemented, the
h6 good engine) must agree on the customer history and every probe scenario;
each h6 mutation must change the customer's adjustments or a probe outcome.
Prints JSON; `--write` refreshes author_only/proof_result.json.
"""
import copy
import importlib.util
import json
import sys
import tempfile
import types
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m); return m


oracle = load(TASK / 'grader/oracle.py', 'proof_billing_oracle')
package = types.ModuleType('meter_billing'); package.__path__ = [str(TASK / 'workspace/meter_billing')]; sys.modules['meter_billing'] = package
load(TASK / 'workspace/meter_billing/pricing.py', 'meter_billing.pricing')


def service(solution):
    return load(TASK / 'solutions' / solution / 'files/meter_billing/service.py', 'meter_billing.service_' + solution.replace('-', '_'))


def execute(api, ops, root):
    path = str(Path(root) / 'store.db'); outputs = []
    for op in ops:
        try:
            if op['op'] == 'init':
                outputs.append(api.initialize(path, copy.deepcopy(op['config'])))
            elif op['op'] in ('close', 'close_mutate'):
                outputs.append(api.close(path, copy.deepcopy(op['command'])))
            elif op['op'] in ('snapshot', 'subprocess_snapshot'):
                outputs.append(api.snapshot(path))
            elif op['op'] == 'concurrent':
                responses = {i: api.close(path, copy.deepcopy(c)) for i, c in enumerate(op['commands'])}
                outputs.append([responses[i % len(op['commands'])] for i in range(op['calls'])])
        except ValueError:
            outputs.append({'error': 'ValueError'})
    return json.loads(json.dumps(outputs))


def document(api, history, root):
    path = str(Path(root) / 'doc.db'); api.initialize(path, history['config'])
    closes = [api.close(path, c) for c in history['commands']]; snap = api.snapshot(path)
    return {'customer': history.get('customer'), 'closes': closes, 'targets': snap['targets'], 'clock': snap['clock'], 'delivery_count': snap['delivery_count']}


def failing(api, history, root):
    try:
        document(api, history, root); return False
    except ValueError:
        return True


def main():
    customer = oracle.read_customer(TASK / 'workspace/data'); scripts = dict(oracle.scenarios(customer)); cli = oracle.cli_histories(customer)
    want_doc = oracle.expected_document(customer)
    result = {'scenarios': len(scripts), 'agreement': {}, 'mutations': {}}
    for solution in ('honest-implemented', 'absolute-counter', 'price-periods-independently', 'replace-incremental-feed', 'id-without-payload'):
        api = service(solution); mismatched = []
        for name, ops in scripts.items():
            with tempfile.TemporaryDirectory() as root:
                got = execute(api, ops, root)
            if got != oracle.expected_outputs(ops, got):
                mismatched.append(name)
        with tempfile.TemporaryDirectory() as root:
            customer_ok = document(api, customer, root) == want_doc
        with tempfile.TemporaryDirectory() as root:
            nearby_ok = document(api, cli['nearby'], root) == oracle.expected_document(cli['nearby'])
        with tempfile.TemporaryDirectory() as root:
            rejects = failing(api, cli['failing'], root)
        entry = dict(customer_document_matches=customer_ok, nearby_document_matches=nearby_ok, failing_history_rejected=rejects, mismatched_scenarios=mismatched)
        (result['agreement'] if solution == 'honest-implemented' else result['mutations'])[solution] = entry
    honest = result['agreement']['honest-implemented']
    assert honest == dict(customer_document_matches=True, nearby_document_matches=True, failing_history_rejected=True, mismatched_scenarios=[])
    for name, entry in result['mutations'].items():
        assert entry['mismatched_scenarios'], name
    assert result['mutations']['id-without-payload']['customer_document_matches'] is True  # artifact alone cannot catch it
    result['customer'] = dict(final_targets=want_doc['targets'], total_cents=sum(t['cents'] for t in want_doc['targets']),
                              postings_per_close={c['operation_id']: len(c['postings']) for c in want_doc['closes']},
                              clock=want_doc['clock'], delivery_count=want_doc['delivery_count'])
    text = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if '--write' in sys.argv:
        (TASK / 'author_only/proof_result.json').write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
