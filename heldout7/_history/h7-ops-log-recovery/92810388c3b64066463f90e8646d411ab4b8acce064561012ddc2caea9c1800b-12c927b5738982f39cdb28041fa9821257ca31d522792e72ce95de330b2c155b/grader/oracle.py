"""Trusted in-memory recovery oracle for grading (never imports candidate code).
Semantics follow workspace/README.md; logic is the h6-ops-wal-restore honest algorithm ported to an
in-memory store whose failed calls restore a deep copy, so failures are atomic by construction."""
import copy
import hashlib
import json

SUMMARY = ('version', 'frontier', 'values', 'processed')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


class Store:
    def __init__(self):
        self.state = None

    def _summary(self):
        return {k: copy.deepcopy(self.state[k]) for k in SUMMARY}

    def initialize(self, snapshot):
        if self.state is not None:
            if self.state['anchor'] != snapshot:
                raise ValueError('different snapshot')
            return self._summary()
        self.state = {'anchor': copy.deepcopy(snapshot), 'version': 0, 'frontier': copy.deepcopy(snapshot['frontier']),
                      'values': copy.deepcopy(snapshot['values']), 'processed': {t: 'commit' for t in snapshot['applied']},
                      'events': {}, 'decisions': {}, 'requests': {}}
        return self._summary()

    def inspect(self):
        if self.state is None:
            raise ValueError('uninitialized')
        return self._summary()

    def _call(self, request_id, payload, expected_version, body):
        if self.state is None:
            raise ValueError('uninitialized')
        saved = self.state['requests'].get(request_id)
        if saved is not None:
            if saved['payload'] != payload:
                raise ValueError('request ID reused')
            return copy.deepcopy(saved['response'])
        if expected_version != self.state['version']:
            raise ValueError('version conflict')
        backup = copy.deepcopy(self.state)
        try:
            extra = body(self.state)
        except Exception:
            self.state = backup
            raise
        self.state['version'] += 1
        response = {**self._summary(), **extra}
        self.state['requests'][request_id] = {'payload': payload, 'response': copy.deepcopy(response)}
        return response

    def ingest(self, request_id, expected_version, batch):
        return self._call(request_id, canonical(['ingest', expected_version, batch]), expected_version, lambda s: _ingest(s, batch))

    def advance(self, request_id, expected_version, target):
        return self._call(request_id, canonical(['advance', expected_version, target]), expected_version, lambda s: _advance(s, target))


def _ingest(s, batch):
    anchor = s['anchor']
    for e in batch['events']:
        shard, lsn = e['shard'], e['lsn']
        if shard not in s['frontier'] or not _int(lsn) or lsn <= anchor['frontier'][shard] or e['ordinal'] < 0 or e['txid'] in anchor['applied']:
            raise ValueError('invalid event')
        key = f'{shard}:{lsn}'
        if key in s['events'] and s['events'][key] != e:
            raise ValueError('event conflict')
        s['events'][key] = copy.deepcopy(e)
    for d in batch['decisions']:
        if d['outcome'] not in ('commit', 'abort') or not d['parts'] or d['txid'] in anchor['applied'] or len(set(d['parents'])) != len(d['parents']):
            raise ValueError('invalid decision')
        for shard, part in d['parts'].items():
            lsns = part['lsns']
            if shard not in s['frontier'] or not lsns or lsns != sorted(set(lsns)) or lsns[0] <= anchor['frontier'][shard]:
                raise ValueError('invalid manifest')
        if d['txid'] in s['decisions'] and s['decisions'][d['txid']] != d:
            raise ValueError('decision conflict')
        s['decisions'][d['txid']] = copy.deepcopy(d)
    return {'ingested': True}


def _advance(s, target):
    if set(target) != set(s['frontier']) or any(not _int(v) or v < s['frontier'][k] for k, v in target.items()):
        raise ValueError('invalid target')
    selected, edges = {}, {}
    for shard in sorted(target):
        last = None
        for lsn in range(s['frontier'][shard] + 1, target[shard] + 1):
            e = s['events'].get(f'{shard}:{lsn}')
            if e is None:
                raise ValueError('missing event')
            selected.setdefault(e['txid'], []).append(e); edges.setdefault(e['txid'], set())
            if last is not None and last != e['txid']:
                edges[e['txid']].add(last)
            last = e['txid']
    for t in sorted(selected):
        if t in s['processed'] or t not in s['decisions']:
            raise ValueError('processed or undecided')
        d = s['decisions'][t]; sealed = []
        for shard, part in d['parts'].items():
            rows = []
            for lsn in part['lsns']:
                e = s['events'].get(f'{shard}:{lsn}')
                if e is None or e['txid'] != t or not s['frontier'][shard] < lsn <= target[shard]:
                    raise ValueError('seal outside cut')
                rows.append(e)
            if digest(rows) != part['sha256']:
                raise ValueError('digest')
            sealed.extend(rows)
        key = lambda e: (e['shard'], e['lsn'])
        if sorted((e for e in s['events'].values() if e['txid'] == t), key=key) != sorted(sealed, key=key):
            raise ValueError('unsealed event')
        if sorted(e['ordinal'] for e in sealed) != list(range(len(sealed))) or len(selected[t]) != len(sealed):
            raise ValueError('ordinals or incomplete')
        for parent in d['parents']:
            if s['processed'].get(parent) == 'commit':
                continue
            if parent not in selected or s['decisions'].get(parent, {}).get('outcome') != 'commit':
                raise ValueError('uncommitted parent')
            edges[t].add(parent)
    order, pending = [], set(selected)
    while pending:
        ready = sorted(t for t in pending if not edges[t] & pending)
        if not ready:
            raise ValueError('cycle')
        pending.remove(ready[0]); order.append(ready[0])
    for t in order:
        d = s['decisions'][t]
        if d['outcome'] == 'commit':
            for e in sorted(selected[t], key=lambda e: e['ordinal']):
                values = s['values'][e['shard']]
                if values.get(e['key']) != e['before']:
                    raise ValueError('before image')
                if e['after'] is None:
                    values.pop(e['key'], None)
                else:
                    values[e['key']] = e['after']
        s['processed'][t] = d['outcome']
    s['frontier'] = copy.deepcopy(target)
    return {'order': order}


def semantic(response):
    """Documented response fields only (extra metadata is allowed)."""
    keys = SUMMARY + tuple(k for k in ('ingested', 'order') if k in response)
    return json.loads(canonical({k: response[k] for k in keys}))


def run_case(case):
    store = Store(); outcomes = []
    for step in case['steps']:
        op = step['op']
        try:
            if op == 'initialize':
                out = store.initialize(step['snapshot'])
            elif op == 'inspect':
                out = store.inspect()
            elif op == 'ingest':
                out = store.ingest(step['request_id'], step['expected_version'], step['batch'])
            else:
                out = store.advance(step['request_id'], step['expected_version'], step['target'])
            outcomes.append({op: semantic(out)})
        except ValueError:
            outcomes.append({op: 'error'})
    return outcomes


def history_steps(history):
    steps = [{'op': 'initialize', 'snapshot': history['snapshot']}]
    for b in history['batches']:
        steps.append({'op': 'ingest', 'request_id': b['request_id'], 'expected_version': b['expected_version'],
                      'batch': {'events': b['events'], 'decisions': b['decisions']}})
    r = history['restore']
    steps.append({'op': 'advance', 'request_id': r['request_id'], 'expected_version': r['expected_version'], 'target': r['target']})
    return steps


def expected_checkpoint(history):
    """The checkpoint the restore command must write, or None when the history cannot be restored."""
    store = Store()
    try:
        store.initialize(history['snapshot'])
        for b in history['batches']:
            store.ingest(b['request_id'], b['expected_version'], {'events': b['events'], 'decisions': b['decisions']})
        r = history['restore']
        result = store.advance(r['request_id'], r['expected_version'], r['target'])
    except ValueError:
        return None
    return {'checkpoint_id': history['checkpoint_id'], **semantic(result)}


def checkpoint_errors(observed, expected):
    if not isinstance(observed, dict):
        return ['checkpoint is not a JSON object']
    return [f'{field} differs' for field in sorted(expected) if json.loads(canonical(observed.get(field))) != expected[field]]
