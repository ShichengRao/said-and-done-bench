"""Trusted release-batch oracle. Never imports candidate code.

Grouped revision reconstruction, per-tick authorization, an exact earliest-tick
dynamic program over (committed set, register values), and a commit-record replayer.
"""
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def verify(body, signature, key):
    try:
        n = int(key['n'], 16); e = key['e']; size = (n.bit_length() + 7) // 8
        raw = bytes.fromhex(signature['sig'])
        if len(raw) != size or int.from_bytes(raw, 'big') >= n:
            return False
        tail = bytes.fromhex('3031300d060960864801650304020105000420') + hashlib.sha256(canonical(body)).digest()
        expected = b'\x00\x01' + b'\xff' * (size - len(tail) - 3) + b'\x00' + tail
        return pow(int.from_bytes(raw, 'big'), e, n).to_bytes(size, 'big') == expected
    except (ValueError, KeyError, TypeError, OverflowError):
        return False


def read_bundle(root):
    root = Path(root)
    read = lambda name: json.loads((root / name).read_text())
    return {'batch': read('batch.json'), 'initial': read('initial_state.json'), 'grants': read('grants.json'),
            'keys': read('keys.json'),
            'envelopes': [json.loads(s) for s in (root / 'operations.jsonl').read_text().splitlines() if s.strip()]}


def _grouped_latest(rows, body):
    groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        groups[body(row)['id']][body(row)['revision']].append(row)
    result = {}
    for ident, revisions in groups.items():
        for copies in revisions.values():
            if any(canonical(c) != canonical(copies[0]) for c in copies):
                raise ValueError('conflicting records for ' + ident)
        result[ident] = revisions[max(revisions)][0]
    return result


def facts(bundle):
    """Return selected operation bodies and the sorted ticks at which each may be submitted."""
    batch = bundle['batch']
    envelopes = _grouped_latest(bundle['envelopes'], lambda e: e['signed'])
    grants = _grouped_latest(bundle['grants'], lambda g: g)
    ops, ticks = {}, {}
    for member in batch['members']:
        if member not in envelopes:
            raise ValueError('missing operation ' + member)
        env = envelopes[member]; body = env['signed']; touched = set(body['expected']) | set(body['writes'])
        if not touched <= set(bundle['initial']):
            raise ValueError('unknown resource in ' + member)
        allowed = set()
        for grant in grants.values():
            if grant['principal'] != body['principal'] or grant['revoked'] or not touched <= set(grant['resources']):
                continue
            key = bundle['keys'].get(grant['keyid'])
            if key is None or not any(s.get('keyid') == grant['keyid'] and verify(body, s, key) for s in env['signatures']):
                continue
            allowed.update(range(grant['valid_from'], grant['valid_to'] + 1))
        window = range(max(batch['start_tick'], body['window']['not_before']), min(batch['end_tick'], body['window']['not_after']) + 1)
        ops[member] = body; ticks[member] = sorted(allowed.intersection(window))
    return ops, ticks


def search(bundle):
    """Exact search. Returns (feasible, attempts) where attempts is one full commit schedule or None.

    Waiting is always permitted, so the earliest tick for each (committed set, values) state dominates.
    """
    ops, ticks = facts(bundle)
    names = sorted(ops); resources = sorted(bundle['initial'])
    start = (frozenset(), tuple(bundle['initial'][r] for r in resources))
    best = {start: (bundle['batch']['start_tick'] - 1, [])}
    layer = [start]
    for _ in names:
        following = {}
        for state in layer:
            done, values = state; tick, path = best[state]; current = dict(zip(resources, values))
            for name in names:
                if name in done:
                    continue
                later = [t for t in ticks[name] if t > tick]
                body = ops[name]
                if not later or any(current[r] != v for r, v in body['expected'].items()):
                    continue
                updated = dict(current); updated.update(body['writes'])
                nxt = (done | {name}, tuple(updated[r] for r in resources))
                candidate = (later[0], path + [{'tick': later[0], 'operation': name, 'revision': body['revision'], 'result': 'committed'}])
                if nxt not in best or candidate[0] < best[nxt][0]:
                    best[nxt] = candidate
                    following[nxt] = True
        layer = list(following)
    goals = [best[s][1] for s in layer if len(s[0]) == len(names)]
    return (bool(goals), goals[0] if goals else None)


def replay_state(bundle, attempts):
    ops, _ = facts(bundle); values = dict(bundle['initial'])
    for attempt in attempts:
        body = ops[attempt['operation']]
        if attempt['result'] == 'committed':
            values.update(body['writes'])
    return values


def validate_record(record, bundle):
    """Errors in a published commit record, replayed under the documented rules."""
    try:
        ops, ticks = facts(bundle)
    except ValueError as error:
        return ['batch is not loadable: ' + str(error)]
    errors = []
    if not isinstance(record, dict):
        return ['commit record is not an object']
    if record.get('batch_id') != bundle['batch']['batch_id']:
        errors.append('incorrect batch_id')
    attempts = record.get('attempts')
    if not isinstance(attempts, list) or not all(isinstance(a, dict) for a in attempts):
        return errors + ['attempts must be a list of objects']
    values = dict(bundle['initial']); committed = []; last = bundle['batch']['start_tick'] - 1
    for attempt in attempts:
        name = attempt.get('operation'); tick = attempt.get('tick')
        if name not in ops:
            errors.append('attempt for non-member ' + repr(name)); continue
        body = ops[name]
        if type(tick) is not int or tick <= last:
            errors.append('ticks must be strictly increasing integers'); continue
        last = tick
        if attempt.get('revision') != body['revision']:
            errors.append('superseded or unknown revision for ' + name)
        if tick not in ticks[name]:
            errors.append(f'{name} not authorized or outside its window at tick {tick}')
        if name in committed:
            errors.append(name + ' submitted again after it committed')
        success = all(values[r] == v for r, v in body['expected'].items())
        if attempt.get('result') not in ('committed', 'retry'):
            errors.append('unknown result for ' + name)
        elif (attempt['result'] == 'committed') != success:
            errors.append(f'reported result for {name} at tick {tick} differs from its expected-value check')
        if success:
            values.update(body['writes'])
            committed.append(name)
    if sorted(committed) != sorted(ops) or len(committed) != len(set(committed)):
        errors.append('batch did not commit every member exactly once')
    if record.get('committed') != sorted(ops):
        errors.append('committed list differs from batch membership')
    if record.get('final_state') != values:
        errors.append('final_state differs from replay')
    return sorted(set(errors))
