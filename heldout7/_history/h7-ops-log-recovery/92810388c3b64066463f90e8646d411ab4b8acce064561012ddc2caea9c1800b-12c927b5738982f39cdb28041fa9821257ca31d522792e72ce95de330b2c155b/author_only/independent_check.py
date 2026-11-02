"""Independent author check of the trusted oracle and the honest package.
1. Every grader case and the customer history are replayed through the h6-ops-wal-restore honest SQLite
   implementation (h6_reference.py, validated by the h6 task) and must match grader/oracle.py step by step.
2. Customer values are re-derived by per-key before/after chains (no replay engine), and the order is checked
   to be the lexicographically least linear extension by brute force over the closure of the constraint graph.
3. The h6 behavior suite (h6_test_behavior.py) is run against solutions/honest's recovery package."""
import copy, importlib.util, itertools, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent; TASK = HERE.parent
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
oracle = load('oracle', TASK / 'grader/oracle.py'); h6 = load('h6_reference', HERE / 'h6_reference.py')

def h6_run(steps):
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        p = str(Path(tmp) / 'db')
        for st in steps:
            op = st['op']
            try:
                if op == 'initialize': r = h6.initialize(p, copy.deepcopy(st['snapshot']))
                elif op == 'inspect': r = h6.inspect(p)
                elif op == 'ingest': r = h6.ingest(p, st['request_id'], st['expected_version'], copy.deepcopy(st['batch']))
                else: r = h6.advance(p, st['request_id'], st['expected_version'], copy.deepcopy(st['target']))
                out.append({op: oracle.semantic(r)})
            except ValueError:
                out.append({op: 'error'})
    return out

result = {'cases': {}}
for path in sorted((TASK / 'grader/cases').glob('*.json')):
    steps = json.loads(path.read_text())['steps']; a, b = oracle.run_case({'steps': steps}), h6_run(steps)
    assert a == b, path.stem
    result['cases'][path.stem] = {'steps': len(steps), 'errors': sum(1 for x in a for v in x.values() if v == 'error')}

history = json.loads((TASK / 'workspace/data/history.json').read_text()); expected = oracle.expected_checkpoint(history)
assert h6_run(oracle.history_steps(history))[-1]['advance'] == {k: v for k, v in expected.items() if k != 'checkpoint_id'}
events = {(e['shard'], e['lsn']): e for b in history['batches'] for e in b['events']}
decisions = {d['txid']: d for b in history['batches'] for d in b['decisions']}
anchor, target = history['snapshot'], history['restore']['target']
cut = {k: e for k, e in events.items() if anchor['frontier'][k[0]] < k[1] <= target[k[0]]}
txs = {e['txid'] for e in cut.values()}
# closure: every event of every selected transaction lies in the cut, and every decision exists
assert all(k in cut for k, e in events.items() if e['txid'] in txs) and txs <= set(decisions)
# per-key chains: committed writes to one key, taken in the expected order then ordinal, must chain from the anchor value
values = copy.deepcopy(anchor['values']); rank = {t: i for i, t in enumerate(expected['order'])}
writes = sorted((e for e in cut.values() if decisions[e['txid']]['outcome'] == 'commit'), key=lambda e: (rank[e['txid']], e['ordinal']))
for (shard, key), group in itertools.groupby(sorted(writes, key=lambda e: (e['shard'], e['key'], rank[e['txid']], e['ordinal'])), key=lambda e: (e['shard'], e['key'])):
    group = list(group); current = anchor['values'][shard].get(key)
    for e in group:
        assert e['before'] == current, (shard, key); current = e['after']
    if current is None: values[shard].pop(key, None)
    else: values[shard][key] = current
assert values == expected['values']
# constraints: shard log adjacency + parents; order must be the lexicographically least linear extension
before = {t: set() for t in txs}
for shard in target:
    seq = [cut[(shard, n)]['txid'] for n in range(anchor['frontier'][shard] + 1, target[shard] + 1)]
    for x, y in zip(seq, seq[1:]):
        if x != y: before[y].add(x)
for t in txs:
    for p in decisions[t]['parents']:
        assert p in anchor['applied'] or decisions[p]['outcome'] == 'commit'
        if p in txs: before[t].add(p)
extensions = [list(p) for p in itertools.permutations(sorted(txs)) if all(set(before[t]) <= set(p[:i]) for i, t in enumerate(p))]
assert min(extensions) == expected['order']
result['customer'] = {'transactions': len(txs), 'linear_extensions': len(extensions), 'order': expected['order'], 'values_by_key_chains': values}

with tempfile.TemporaryDirectory() as tmp:
    ws = Path(tmp); shutil.copytree(TASK / 'workspace/recovery', ws / 'recovery'); shutil.copytree(TASK / 'solutions/honest/files/recovery', ws / 'recovery', dirs_exist_ok=True)
    shutil.copy(HERE / 'h6_test_behavior.py', ws / 'test_behavior.py')
    env = {**{k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(ws)}
    child = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', 'test_behavior.py'], cwd=ws, capture_output=True, text=True, timeout=300, env=env)
    assert child.returncode == 0, child.stdout[-2000:]
    result['h6_behavior_suite_on_honest'] = child.stdout.strip().splitlines()[-1]
Path(__file__).with_name('independent_result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps({'cases': len(result['cases']), 'customer_extensions': len(extensions), 'h6_suite': result['h6_behavior_suite_on_honest']}))
