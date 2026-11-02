"""Builds workspace/data/history.json (customer) and grader/cases/*.json (API scenarios).
Scenarios reuse the h6-ops-wal-restore canonical input (author_only/source_input.json) and its behavior
tests (canonical abort/ordinals, partial vector, late before-image rollback, replay binding, parents, cycle,
seal/extra/ordinal defects, batch conflict, late evidence, anchor reinit, seeded partitions)."""
import copy, hashlib, importlib.util, json, random
from pathlib import Path
TASK = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('oracle', TASK / 'grader/oracle.py'); oracle = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)
digest = oracle.digest


def ev(s, n, t, o, k, b, a):
    return dict(shard=s, lsn=n, txid=t, ordinal=o, key=k, before=b, after=a)


def seal(t, rows, outcome='commit', parents=()):
    rows = sorted(rows, key=lambda e: e['lsn'])
    return dict(txid=t, outcome=outcome, parents=list(parents),
                parts={s: dict(lsns=[e['lsn'] for e in rows if e['shard'] == s], sha256=digest([e for e in rows if e['shard'] == s]))
                       for s in sorted({e['shard'] for e in rows})})


# ---------------- customer history (Marlow Quay Provisions, fictional) ----------------
def customer():
    snapshot = {'frontier': {'ledger': 40, 'orders': 12, 'stock': 7},
                'values': {'ledger': {'acct-17': '1200', 'acct-22': '340'}, 'orders': {'ord-881': 'open'}, 'stock': {'sku-4': '9', 'sku-9': '0'}},
                'applied': ['mq-0412']}
    tx = {
        'r-shipment': [ev('orders', 13, 'r-shipment', 0, 'ord-881', 'open', 'packed'), ev('stock', 8, 'r-shipment', 1, 'sku-4', '9', '8')],
        'k-refund': [ev('ledger', 41, 'k-refund', 0, 'acct-17', 'stale', '1100')],
        # same key twice; ordinal order differs from LSN order
        'd-invoice': [ev('orders', 14, 'd-invoice', 0, 'inv-77', None, 'issued'), ev('ledger', 42, 'd-invoice', 2, 'acct-17', '1180', '1150'),
                      ev('ledger', 43, 'd-invoice', 1, 'acct-17', '1200', '1180'), ev('ledger', 44, 'd-invoice', 3, 'acct-22', '340', '390')],
        'b-audit': [ev('ledger', 45, 'b-audit', 0, 'audit-1', None, 'ok')],
        'p-close': [ev('orders', 15, 'p-close', 0, 'ord-881', 'packed', 'closed'), ev('ledger', 46, 'p-close', 1, 'acct-22', '390', None)],
        'h-supplier': [ev('stock', 9, 'h-supplier', 0, 'sku-9', '0', '24')],
        't-restock': [ev('orders', 16, 't-restock', 0, 'ord-990', None, 'open'), ev('stock', 10, 't-restock', 1, 'sku-4', '8', '20')],
        'a-cancelled': [ev('stock', 11, 'a-cancelled', 0, 'sku-9', 'x', 'y'), ev('ledger', 47, 'a-cancelled', 1, 'acct-22', 'gone', '5')],
        'w-pending': [ev('ledger', 48, 'w-pending', 0, 'acct-17', '1150', '1000'), ev('orders', 17, 'w-pending', 1, 'ord-990', 'open', 'paid')],
    }
    decisions = {'r-shipment': seal('r-shipment', tx['r-shipment'], parents=['mq-0412']), 'k-refund': seal('k-refund', tx['k-refund'], 'abort'),
                 'd-invoice': seal('d-invoice', tx['d-invoice']), 'b-audit': seal('b-audit', tx['b-audit'], parents=['r-shipment']),
                 'p-close': seal('p-close', tx['p-close'], parents=['d-invoice']), 'h-supplier': seal('h-supplier', tx['h-supplier'], parents=['p-close']),
                 't-restock': seal('t-restock', tx['t-restock'], parents=['h-supplier']), 'a-cancelled': seal('a-cancelled', tx['a-cancelled'], 'abort')}
    events = [e for rows in tx.values() for e in rows]
    first = [e for e in events if (e['shard'], e['lsn']) in {('ledger', 41), ('ledger', 42), ('ledger', 43), ('ledger', 44), ('orders', 13), ('orders', 14), ('stock', 8), ('stock', 9)}]
    second = [e for e in events if e not in first] + [copy.deepcopy(next(e for e in first if e['lsn'] == 14))]
    random.Random(1102).shuffle(second)
    b1 = {'request_id': 'export-0412-1', 'expected_version': 0, 'events': first, 'decisions': [decisions['r-shipment'], decisions['k-refund']]}
    b2 = {'request_id': 'export-0412-2', 'expected_version': 1, 'events': second,
          'decisions': [decisions[t] for t in ('a-cancelled', 'p-close', 'd-invoice', 'h-supplier', 'b-audit')]}
    b3 = {'request_id': 'export-0412-3', 'expected_version': 2, 'events': [], 'decisions': [decisions['t-restock']]}
    return {'checkpoint_id': 'marlow-quay-2026-11-02', 'snapshot': snapshot, 'batches': [b1, b2, copy.deepcopy(b2), b3],
            'restore': {'request_id': 'restore-marlow-quay-2026-11-02', 'expected_version': 3, 'target': {'ledger': 47, 'orders': 16, 'stock': 11}}}


def relabel(history, suffix, shift):
    """Consistent fictional renames + LSN shift; seals recomputed. Renaming can change lexical order."""
    shards = {'ledger': 'cash' + suffix, 'orders': 'book' + suffix, 'stock': 'bins' + suffix}
    tx = lambda t: t if t.startswith('mq-') else {'r': 'c', 'k': 'x', 'd': 'q', 'b': 'm', 'p': 'a', 'h': 'z', 't': 'f', 'a': 'n', 'w': 'w'}[t[0]] + t[1:] + suffix
    h = copy.deepcopy(history); h['checkpoint_id'] = history['checkpoint_id'] + suffix
    s = h['snapshot']; s['frontier'] = {shards[k]: v + shift for k, v in s['frontier'].items()}; s['values'] = {shards[k]: v for k, v in s['values'].items()}
    events = {}
    for b in h['batches']:
        for e in b['events']:
            e['shard'] = shards[e['shard']]; e['lsn'] += shift; e['txid'] = tx(e['txid']); events[(e['shard'], e['lsn'])] = e
    for b in h['batches']:
        b['request_id'] += suffix
        for i, d in enumerate(b['decisions']):
            t = tx(d['txid']); rows = [e for e in events.values() if e['txid'] == t]
            b['decisions'][i] = seal(t, rows, d['outcome'], [tx(p) for p in d['parents']])
    h['restore']['request_id'] += suffix; h['restore']['target'] = {shards[k]: v + shift for k, v in h['restore']['target'].items()}
    return h


# ---------------- API cases ----------------
def h6():
    src = json.loads((TASK / 'author_only/source_input.json').read_text()); return src['snapshot'], src['batch']


def init(snap): return {'op': 'initialize', 'snapshot': snap}
def ing(rid, v, events=(), decisions=()): return {'op': 'ingest', 'request_id': rid, 'expected_version': v, 'batch': {'events': list(events), 'decisions': list(decisions)}}
def adv(rid, v, target): return {'op': 'advance', 'request_id': rid, 'expected_version': v, 'target': target}
INSPECT = {'op': 'inspect'}


def cases():
    snap, batch = h6(); full = {'a': 3, 'b': 2}; c = {}
    load = lambda b=batch: [init(snap), ing('load', 0, b['events'], b['decisions'])]
    c['h6_canonical_abort_ordinals'] = {'steps': load() + [adv('go', 1, full), INSPECT]}
    c['h6_partial_vector_atomic'] = {'steps': load() + [adv('bad', 1, {'a': 3, 'b': 1}), INSPECT, adv('bad', 1, full)]}
    b = copy.deepcopy(batch); t3 = [e for e in b['events'] if e['txid'] == 't3']; t3[-1]['before'] = 'wrong'; b['decisions'][0] = seal('t3', t3, parents=['t1'])
    c['h6_late_before_image_rolls_back_all'] = {'steps': load(b) + [adv('go', 1, full), INSPECT, adv('other', 1, {'a': 2, 'b': 1}), INSPECT]}
    c['h6_replay_binding'] = {'steps': load() + [adv('go', 1, full), ing('empty', 2), adv('go', 1, {'b': 2, 'a': 3}), ing('go', 1), adv('go', 3, full),
                                                 ing('load', 0, batch['events'], batch['decisions']), INSPECT]}
    for parent in ('missing', 't2'):
        b = copy.deepcopy(batch); b['decisions'][0]['parents'] = [parent]
        c[f'h6_parent_{parent}'] = {'steps': load(b) + [adv('go', 1, full), INSPECT]}
    es = [ev('a', 1, 'a', 0, 'x', '0', '1'), ev('a', 2, 'b', 0, 'x', '1', '2'), ev('b', 1, 'b', 1, 'y', '0', '1'), ev('b', 2, 'a', 1, 'y', '1', '2')]
    c['h6_serialization_cycle'] = {'steps': load({'events': es, 'decisions': [seal(t, [e for e in es if e['txid'] == t]) for t in 'ab']}) + [adv('go', 1, {'a': 2, 'b': 2})]}
    for mode in ('hash', 'extra', 'ordinal'):
        b = copy.deepcopy(batch)
        if mode == 'hash': b['decisions'][0]['parts']['a']['sha256'] = '0' * 64
        if mode == 'extra': b['events'].append(ev('b', 3, 't3', 2, 'z', None, 'x'))
        if mode == 'ordinal': b['events'][-1]['ordinal'] = 1; b['decisions'][0] = seal('t3', [e for e in b['events'] if e['txid'] == 't3'], parents=['t1'])
        c[f'h6_seal_{mode}'] = {'steps': load(b) + [adv('go', 1, full), INSPECT]}
    bad = copy.deepcopy(batch['events'][0]); bad['after'] = 'different'; extra = ev('a', 4, 'late', 0, 'x', '3', '4'); altered = dict(extra, after='5')
    c['h6_batch_conflict_atomic'] = {'steps': load() + [ing('bad', 1, [extra, bad]), INSPECT, ing('ok', 1, [altered]), ing('again', 2, [extra])]}
    b = copy.deepcopy(batch); last = b['events'].pop()
    c['h6_late_evidence'] = {'steps': load(b) + [adv('go', 1, full), ing('late', 1, [last]), adv('go', 2, full)]}
    other = copy.deepcopy(snap); other['values']['a']['x'] = '9'
    c['h6_anchor_reinit'] = {'steps': load() + [adv('go', 1, full), init(snap), init(other), INSPECT]}
    c['empty_noop_and_uninitialized'] = {'steps': [INSPECT, ing('early', 0), init({'frontier': {'s': 0}, 'values': {'s': {}}, 'applied': []}),
                                                   adv('first', 0, {'s': 0}), ing('empty', 1), adv('noop', 2, {'s': 0}), adv('back', 3, {'s': -1}), adv('shape', 3, {'s': 0, 't': 0})]}
    # invalid ingest syntax: each rejected without effect
    good = batch['events'][0]; d0 = batch['decisions'][2]
    invalid = [ing('i1', 1, [dict(good, shard='zz')]), ing('i2', 1, [dict(good, lsn=0)]), ing('i3', 1, [dict(good, lsn=True)]), ing('i4', 1, [dict(good, ordinal=-1)]),
               ing('i5', 1, [], [dict(d0, outcome='maybe')]), ing('i6', 1, [], [dict(d0, parts={})]), ing('i7', 1, [], [dict(d0, parents=['t9', 't9'])]),
               ing('i8', 1, [], [dict(d0, parts={'a': {'lsns': [1, 1], 'sha256': '0'}})]), ing('i9', 1, [], [dict(d0, parts={'q': {'lsns': [1], 'sha256': '0'}})]),
               ing('i10', 1, [], [dict(d0, outcome='abort')]), ing('i11', 1, [dict(good, txid='t0')]), ing('i12', 1, [], [dict(d0, txid='t0')]), INSPECT]
    snap0 = dict(copy.deepcopy(snap), applied=['t0'])
    c['ingest_syntax_rejected_atomically'] = {'steps': [init(snap0), ing('load', 0, batch['events'], batch['decisions'])] + invalid + [adv('go', 1, full)]}
    # parents across advances; processed abort parent; already processed transaction; historical replay
    e1 = [ev('a', 1, 'p1', 0, 'x', '0', '1')]; e2 = [ev('a', 2, 'p2', 0, 'x', 'junk', 'j')]; e3 = [ev('b', 1, 'p3', 0, 'y', '0', '3')]; e4 = [ev('b', 2, 'p4', 0, 'y', '3', '4')]
    e5 = [ev('a', 3, 'p1', 1, 'x', '1', '9')]
    c['parents_across_advances'] = {'steps': [init(snap), ing('l', 0, e1 + e2 + e3 + e4, [seal('p1', e1), seal('p2', e2, 'abort'), seal('p3', e3, parents=['p1']), seal('p4', e4, parents=['p2'])]),
                                              adv('one', 1, {'a': 2, 'b': 0}), adv('two', 2, {'a': 2, 'b': 1}), adv('three', 3, {'a': 2, 'b': 2}), INSPECT,
                                              ing('hist', 3, e1 + e3), ing('histbad', 4, [dict(e1[0], after='7')]), ing('reuse', 4, e5), adv('four', 5, {'a': 3, 'b': 1}), INSPECT]}
    # delete then recreate, before-image of absent key is null
    d = [ev('a', 1, 'del', 0, 'x', '0', None), ev('a', 2, 'new', 0, 'x', None, 'n'), ev('b', 1, 'new', 1, 'y', '0', None), ev('b', 2, 'zz', 0, 'y', '0', 'bad')]
    c['delete_recreate_and_null_before'] = {'steps': [init(snap), ing('l', 0, d, [seal('del', d[:1]), seal('new', d[1:3]), seal('zz', d[3:])]),
                                                      adv('bad', 1, {'a': 2, 'b': 2}), adv('ok', 1, {'a': 2, 'b': 1}), INSPECT]}
    # customer history plus late decision delivery (partial export) and replays
    h = customer(); steps = oracle.history_steps(h)
    c['customer_full'] = {'steps': steps + [INSPECT, steps[-1], steps[2]]}
    early = steps[:4] + [adv('early', 2, h['restore']['target']), steps[4], adv('late', 3, h['restore']['target'])]
    c['customer_decision_arrives_late'] = {'steps': early}
    over = steps[:-1] + [adv('over', 3, {'ledger': 48, 'orders': 17, 'stock': 11}), adv('cross', 3, {'ledger': 47, 'orders': 15, 'stock': 11}), INSPECT, steps[-1]]
    c['customer_unclosed_targets'] = {'steps': over}
    for i, (sfx, shift) in enumerate([('-n', 100), ('-s', 3)]):
        c[f'customer_relabelled_{i}'] = {'steps': oracle.history_steps(relabel(h, sfx, shift)) + [INSPECT]}
    # seeded generated partitions (h6 generator), cross-shard, aborts, shuffled delivery
    rng = random.Random(2907)
    for n in range(8):
        a = {'frontier': {'a': n, 'b': 0, 'c': 2}, 'values': {'a': {'x': '0'}, 'b': {'y': '0'}, 'c': {'z': '0'}}, 'applied': []}
        lsn = dict(a['frontier']); vals = copy.deepcopy(a['values']); es, ds = [], []
        for i in range(9):
            t = f't{(i * 7 + n) % 10}{i}'; rows = []; abort = i % 4 == 1; shards = rng.sample(['a', 'b', 'c'], rng.randint(1, 3))
            for o, s in enumerate(shards):
                lsn[s] += 1; k = {'a': 'x', 'b': 'y', 'c': 'z'}[s]; new = f'{n}-{i}'
                rows.append(ev(s, lsn[s], t, o, k, 'junk' if abort else vals[s][k], new))
                if not abort: vals[s][k] = new
            es += rows; ds.append(seal(t, rows, 'abort' if abort else 'commit'))
        rng.shuffle(es); rng.shuffle(ds); half = len(es) // 2
        c[f'generated_{n}'] = {'steps': [init(a), ing('a', 0, es[:half], ds), ing('b', 1, es[half:]), adv('go', 2, lsn), INSPECT]}
    return c


if __name__ == '__main__':
    h = customer()
    (TASK / 'workspace/data/history.json').write_text(json.dumps(h, indent=1) + '\n')
    out = TASK / 'grader/cases'
    for p in out.glob('*.json'): p.unlink()
    for name, case in cases().items():
        (out / f'{name}.json').write_text(json.dumps(case, separators=(',', ':')) + '\n')
    print(json.dumps(oracle.expected_checkpoint(h), indent=1))
    print(len(list(out.glob('*.json'))), 'cases')
