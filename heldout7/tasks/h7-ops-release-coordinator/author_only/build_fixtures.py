"""Author-only fixture builder: writes workspace/data and grader/cases deterministically.

Run from anywhere: python author_only/build_fixtures.py
"""
import copy
import hashlib
import json
import shutil
from pathlib import Path

from signing_keys import KEYS

TASK = Path(__file__).resolve().parent.parent


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def sign(body, keyid):
    n, e, d = KEYS[keyid]
    size = (n.bit_length() + 7) // 8
    tail = bytes.fromhex('3031300d060960864801650304020105000420') + hashlib.sha256(canonical(body)).digest()
    em = b'\x00\x01' + b'\xff' * (size - len(tail) - 3) + b'\x00' + tail
    return {'keyid': keyid, 'sig': pow(int.from_bytes(em, 'big'), d, n).to_bytes(size, 'big').hex()}


def envelope(body, keyid):
    return {'signed': body, 'signatures': [sign(body, keyid)]}


def op(ident, revision, principal, window, expected, writes):
    return {'id': ident, 'revision': revision, 'principal': principal,
            'window': {'not_before': window[0], 'not_after': window[1]},
            'expected': expected, 'writes': writes}


SIGNER = {'platform': 'k0', 'db': 'k1', 'api': 'k1', 'worker': 'k2', 'netops': 'k2'}


def base():
    batch = {'batch_id': 'harbor-lantern-release-2026-11-r3', 'customer': 'Harbor Lantern (fictional)',
             'start_tick': 1, 'end_tick': 12,
             'members': ['maint-enter', 'schema-v5', 'worker-v8', 'api-v8', 'cache-reindex', 'maint-exit', 'edge-cutover']}
    initial = {'maint': 0, 'schema': 4, 'api': 7, 'worker': 7, 'cache': 2, 'edge': 3}
    keys = {kid: {'n': hex(n)[2:], 'e': e} for kid, (n, e, d) in KEYS.items()}
    def grant(ident, revision, principal, resources, start, end, revoked=False):
        return {'id': ident, 'revision': revision, 'principal': principal, 'keyid': SIGNER[principal],
                'resources': resources, 'valid_from': start, 'valid_to': end, 'revoked': revoked}
    grants = [
        grant('g-platform', 1, 'platform', ['maint', 'api', 'cache'], 1, 12),
        grant('g-db', 1, 'db', ['maint', 'schema'], 1, 12),
        grant('g-api', 1, 'api', ['maint', 'schema', 'api'], 1, 12),
        grant('g-worker', 1, 'worker', ['schema', 'worker', 'maint', 'cache'], 1, 12, revoked=True),
        grant('g-worker', 2, 'worker', ['schema', 'worker', 'maint', 'cache'], 1, 12),
        grant('g-netops', 1, 'netops', ['cache', 'edge'], 1, 12),
        grant('g-netops', 2, 'netops', ['maint', 'cache', 'edge'], 1, 12),
    ]
    ops = [
        op('edge-cutover', 2, 'netops', (5, 12), {'maint': 1, 'cache': 3, 'edge': 3}, {'edge': 4}),
        op('maint-enter', 1, 'platform', (1, 4), {'maint': 0}, {'maint': 1}),
        op('schema-v5', 1, 'db', (2, 8), {'maint': 1, 'schema': 4}, {'schema': 5}),
        op('worker-v8', 1, 'worker', (3, 10), {'schema': 5, 'worker': 7}, {'worker': 8}),
        op('api-v8', 1, 'api', (3, 9), {'maint': 1, 'schema': 5, 'api': 7}, {'api': 8}),
        op('cache-reindex', 1, 'worker', (5, 12), {'maint': 0, 'worker': 8, 'cache': 2}, {'cache': 3}),
        op('maint-exit', 1, 'platform', (4, 10), {'maint': 1, 'api': 8}, {'maint': 0}),
        # Earlier netops draft, superseded by revision 2 but redelivered later by the export job.
        op('edge-cutover', 1, 'netops', (5, 12), {'maint': 0, 'cache': 3, 'edge': 3}, {'edge': 4}),
    ]
    envelopes = [envelope(body, SIGNER[body['principal']]) for body in ops]
    envelopes.insert(4, copy.deepcopy(envelopes[2]))  # exact redelivery of schema-v5
    return {'batch': batch, 'initial': initial, 'grants': grants, 'keys': keys, 'envelopes': envelopes}


def write(root, bundle):
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    for name, key in [('batch.json', 'batch'), ('initial_state.json', 'initial'), ('grants.json', 'grants'), ('keys.json', 'keys')]:
        (root / name).write_text(json.dumps(bundle[key], indent=2) + '\n')
    (root / 'operations.jsonl').write_text(''.join(json.dumps(e, sort_keys=True) + '\n' for e in bundle['envelopes']))


def revise(bundle, ident, **changes):
    """Append a newly approved, correctly signed revision of an operation."""
    current = max((e['signed'] for e in bundle['envelopes'] if e['signed']['id'] == ident), key=lambda b: b['revision'])
    body = copy.deepcopy(current)
    body['revision'] += 1
    for key, value in changes.items():
        body[key] = value
    bundle['envelopes'].append(envelope(body, SIGNER[body['principal']]))


def regrant(bundle, ident, **changes):
    current = max((g for g in bundle['grants'] if g['id'] == ident), key=lambda g: g['revision'])
    grant = dict(current, revision=current['revision'] + 1, **changes)
    bundle['grants'].append(grant)


def cases():
    result = {'current': base()}
    edge = base(); revise(edge, 'edge-cutover', expected={'maint': 0, 'cache': 3, 'edge': 3}); result['reapproved_edge_cutover'] = edge
    cache = base(); revise(cache, 'cache-reindex', expected={'maint': 1, 'worker': 8, 'cache': 2}); result['reapproved_cache_reindex'] = cache
    tight = copy.deepcopy(edge); revise(tight, 'worker-v8', window={'not_before': 3, 'not_after': 3}); result['tight_worker_window'] = tight
    late = copy.deepcopy(cache); regrant(late, 'g-db', valid_from=3); result['late_db_grant'] = late
    order = copy.deepcopy(edge); order['envelopes'] = list(reversed(order['envelopes'])) + [copy.deepcopy(order['envelopes'][0])]
    result['reordered_redelivery'] = order
    expiring = copy.deepcopy(edge); regrant(expiring, 'g-netops', valid_to=6); result['expiring_netops_grant'] = expiring
    split = base(); split['batch']['members'].remove('edge-cutover'); result['edge_cutover_deferred'] = split
    return result


if __name__ == '__main__':
    write(TASK / 'workspace' / 'data', base())
    all_cases = cases()
    for name, bundle in all_cases.items():
        write(TASK / 'grader' / 'cases' / name, bundle)
    print(json.dumps(sorted(all_cases)))
