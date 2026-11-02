"""Independent author check: literal permutation enumeration with greedy earliest ticks.

Separately written revision grouping and signature verification; imports neither the
grader oracle nor workspace code. Greedy earliest assignment is exact for a fixed order
because waiting is always allowed and every allowed-tick set is fixed in advance.
"""
import hashlib, itertools, json
from pathlib import Path
TASK = Path(__file__).resolve().parent.parent

def load(root):
    root = Path(root); j = lambda n: json.loads((root / n).read_text())
    return j('batch.json'), j('initial_state.json'), j('grants.json'), j('keys.json'), [json.loads(l) for l in (root / 'operations.jsonl').read_text().splitlines() if l]

def good_sig(body, sig, key):
    n = int(key['n'], 16); size = (n.bit_length() + 7) // 8
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).digest()
    want = int.from_bytes(b'\x00\x01' + b'\xff' * (size - 54) + b'\x00' + bytes.fromhex('3031300d060960864801650304020105000420') + digest, 'big')
    return pow(int(sig['sig'], 16), key['e'], n) == want

def model(root, override=None):
    batch, initial, grants, keys, envs = load(root)
    if override: batch, initial, grants, keys, envs = override(batch, initial, grants, keys, envs)
    newest = {}
    for e in envs:
        b = e['signed']
        if b['id'] not in newest or b['revision'] > newest[b['id']]['signed']['revision']: newest[b['id']] = e
    gnew = {}
    for g in grants:
        if g['id'] not in gnew or g['revision'] > gnew[g['id']]['revision']: gnew[g['id']] = g
    allowed = {}
    for m in batch['members']:
        e = newest[m]; b = e['signed']; need = set(b['expected']) | set(b['writes']); ticks = set()
        for g in gnew.values():
            if g['principal'] == b['principal'] and not g['revoked'] and need <= set(g['resources']) and any(s['keyid'] == g['keyid'] and good_sig(b, s, keys[g['keyid']]) for s in e['signatures']):
                ticks |= {t for t in range(g['valid_from'], g['valid_to'] + 1) if b['window']['not_before'] <= t <= b['window']['not_after'] and batch['start_tick'] <= t <= batch['end_tick']}
        allowed[m] = sorted(ticks)
    return batch, initial, {m: newest[m]['signed'] for m in batch['members']}, allowed

def orders(root, override=None, ignore_windows=False):
    batch, initial, ops, allowed = model(root, override); found = []
    for perm in itertools.permutations(batch['members']):
        state = dict(initial); tick = 0; ok = True
        for m in perm:
            body = ops[m]
            options = [t for t in (range(tick + 1, 100) if ignore_windows else allowed[m]) if t > tick]
            if not options or any(state[k] != v for k, v in body['expected'].items()): ok = False; break
            tick = options[0]; state.update(body['writes'])
        if ok: found.append(list(perm))
    return found

data = TASK / 'workspace/data'
def stale(batch, initial, grants, keys, envs):
    return batch, initial, grants, keys, [e for e in envs if not (e['signed']['id'] == 'edge-cutover' and e['signed']['revision'] == 2)]
def rerun_maintenance(batch, initial, grants, keys, envs):
    # Shortcut: treat a second maint-enter submission as another member (violates exactly-once membership).
    import copy
    extra = copy.deepcopy(next(e for e in envs if e['signed']['id'] == 'maint-enter')); extra['signed']['id'] = 'maint-enter#2'
    extra['signed']['window'] = {'not_before': 1, 'not_after': 12}
    return dict(batch, members=batch['members'] + ['maint-enter#2']), initial, grants, keys, envs + [extra]
result = {
    'permutations_examined': 5040,
    'current_full_orders': len(orders(data)),
    'current_full_orders_ignoring_windows_and_grants': len(orders(data, ignore_windows=True)),
    'superseded_edge_revision_orders': len(orders(data, stale)),
    'second_maintenance_entry_orders_signature_ignored': None,
    'counterparts': {},
}
for name in ['reapproved_edge_cutover', 'reapproved_cache_reindex', 'tight_worker_window', 'late_db_grant', 'reordered_redelivery', 'expiring_netops_grant', 'edge_cutover_deferred']:
    found = orders(TASK / 'grader/cases' / name)
    result['counterparts'][name] = {'full_orders': len(found), 'example': found[0] if found else None}
# Unsigned second maint-enter cannot verify (id changed); count ignoring authorization to show why the shortcut is tempting.
batch, initial, ops, allowed = model(data, rerun_maintenance)
allowed['maint-enter#2'] = list(range(1, 13))
count = 0
for perm in itertools.permutations(batch['members']):
    state = dict(initial); tick = 0; ok = True
    for m in perm:
        opts = [t for t in allowed[m] if t > tick]
        if not opts or any(state[k] != v for k, v in ops[m]['expected'].items()): ok = False; break
        tick = opts[0]; state.update(ops[m]['writes'])
    count += ok
result['second_maintenance_entry_orders_signature_ignored'] = count
Path(__file__).with_name('independent_result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps(result, sort_keys=True))
assert result['current_full_orders'] == 0 and result['current_full_orders_ignoring_windows_and_grants'] == 0
assert result['counterparts']['reapproved_edge_cutover']['full_orders'] > 0 and result['counterparts']['expiring_netops_grant']['full_orders'] == 0
