"""Trusted independent billing oracle; never imports candidate code.

Usage allocation and literal per-unit progressive pricing adapted from the h6
independent Fraction oracle, plus an in-memory model of the durable store
contract (incremental deliveries, rejection rollback, operation binding,
retained lines and postings). Also defines the nearby probe scenarios.
"""
import copy
import itertools
import json
import random
from fractions import Fraction
from pathlib import Path


class Rejected(Exception):
    pass


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def normalize(config):
    return {k: sorted(copy.deepcopy(config[k]), key=lambda x: x['id']) for k in ('periods', 'meters', 'pools')}


def selected_rows(deliveries, as_of):
    visible = [r for r in deliveries if r['known'] <= as_of]
    for x, y in itertools.combinations(visible, 2):
        if (x['id'], x['revision']) == (y['id'], y['revision']) and canon(x) != canon(y):
            raise Rejected('conflicting delivery')
    result = []
    for identity in sorted({r['id'] for r in visible}):
        winner = max((r for r in visible if r['id'] == identity), key=lambda r: r['revision'])
        if not winner['void']:
            result.append(winner)
    return result


def compute_targets(cfg, deliveries, as_of):
    selected = selected_rows(deliveries, as_of); units = {}; spans = {}
    for meter in cfg['meters']:
        for epoch in sorted({r['epoch'] for r in selected if r['meter'] == meter['id']}):
            ordered = sorted([r for r in selected if r['meter'] == meter['id'] and r['epoch'] == epoch], key=lambda r: r['at'])
            if len({r['at'] for r in ordered}) != len(ordered):
                raise Rejected('same timestamp')
            for left, right in zip(ordered, ordered[1:]):
                used = right['counter'] - left['counter']
                if used < 0:
                    raise Rejected('counter decreased')
                ticks = set(range(left['at'], right['at']))
                spans.setdefault(meter['id'], []).append((epoch, ticks))
                pieces = []; covered = set()
                for p in cfg['periods']:
                    overlap = ticks & set(range(p['start'], p['end'])); covered |= overlap
                    if overlap:
                        pieces.append((p['id'], Fraction(used * len(overlap), len(ticks))))
                if covered != ticks:
                    raise Rejected('uncovered interval')
                allocated = {p: int(v) for p, v in pieces}
                residual = used - sum(allocated.values())
                for p, v in sorted(pieces, key=lambda pair: (-(pair[1] - int(pair[1])), pair[0]))[:residual]:
                    allocated[p] += 1
                for p, n in allocated.items():
                    key = (p, meter['account'], meter['id']); units[key] = units.get(key, 0) + n
    for intervals in spans.values():
        for (e1, t1), (e2, t2) in itertools.combinations(intervals, 2):
            if e1 != e2 and t1 & t2:
                raise Rejected('overlapping epochs')
    cycle = {p['id']: p['cycle'] for p in cfg['periods']}; pool_of = {m['id']: m['pool'] for m in cfg['meters']}
    costs = {k: 0 for k in units}
    for c, pool in sorted({(cycle[k[0]], pool_of[k[2]]) for k in units}):
        keys = [k for k in units if cycle[k[0]] == c and pool_of[k[2]] == pool]
        total = sum(units[k] for k in keys)
        if not total:
            continue
        tiers = next(p['tiers'] for p in cfg['pools'] if p['id'] == pool)
        amount = sum(next(t['millicents'] for t in tiers if t['up_to'] is None or n <= t['up_to']) for n in range(1, total + 1))
        shares = {k: Fraction(amount * units[k], 1000 * total) for k in keys}
        for k in keys:
            costs[k] = int(shares[k])
        rounded = int(Fraction(amount, 1000) + Fraction(1, 2))
        for k in sorted(keys, key=lambda k: (-(shares[k] - int(shares[k])), k))[:rounded - sum(costs[k] for k in keys)]:
            costs[k] += 1
    return {k: (units[k], costs[k]) for k in units}


class Store:
    """Reference model of one durable store."""

    def __init__(self):
        self.state = None

    def initialize(self, config):
        seed = normalize(config)
        if self.state is not None:
            if self.state['config'] != seed:
                raise Rejected('changed seed')
            return None
        self.state = dict(config=seed, clock=0, deliveries={}, targets={}, history=[], operations={})
        return None

    def close(self, command):
        s = self.state; op = command['operation_id']
        if op in s['operations']:
            bound, response = s['operations'][op]
            if bound != canon(command):
                raise Rejected('operation reused')
            return copy.deepcopy(response)
        if command['as_of'] < s['clock']:
            raise Rejected('clock regression')
        deliveries = dict(s['deliveries'])
        for r in command['readings']:
            deliveries.setdefault(canon(r), copy.deepcopy(r))
        current = compute_targets(s['config'], list(deliveries.values()), command['as_of'])
        for key in s['targets']:
            current.setdefault(key, (0, 0))
        names = ('period', 'account', 'meter'); targets = []; postings = []
        for key in sorted(current):
            u, c = current[key]; pu, pc = s['targets'].get(key, (0, 0))
            targets.append(dict(zip(names, key), units=u, cents=c))
            if u != pu or c != pc:
                postings.append(dict(zip(names, key), units_delta=u - pu, cents_delta=c - pc))
        response = dict(operation_id=op, as_of=command['as_of'], targets=targets, postings=postings)
        s.update(deliveries=deliveries, targets=current, clock=command['as_of'])
        s['history'].append(copy.deepcopy(response)); s['operations'][op] = (canon(command), copy.deepcopy(response))
        return copy.deepcopy(response)

    def snapshot(self):
        s = self.state; names = ('period', 'account', 'meter')
        return dict(clock=s['clock'], config=copy.deepcopy(s['config']), delivery_count=len(s['deliveries']),
                    targets=[dict(zip(names, k), units=v[0], cents=v[1]) for k, v in sorted(s['targets'].items())],
                    history=copy.deepcopy(s['history']))


def run_ops(ops, store=None):
    """Expected outputs for a probe script (concurrent ops use the given serial order)."""
    store = store or Store(); outputs = []
    for op in ops:
        try:
            if op['op'] == 'init':
                out = store.initialize(op['config'])
            elif op['op'] in ('close', 'close_mutate'):
                out = store.close(op['command'])
            elif op['op'] in ('snapshot', 'subprocess_snapshot'):
                out = store.snapshot()
            elif op['op'] == 'concurrent':
                responses = {}
                for i in op['order']:
                    responses[i] = store.close(op['commands'][i])
                out = [responses[i % len(op['commands'])] for i in range(op['calls'])]
            else:
                raise KeyError(op['op'])
        except Rejected:
            out = {'error': 'ValueError'}
        outputs.append(out)
    return outputs


def expected_outputs(ops, actual):
    """Return expected outputs, choosing the serial order the candidate's concurrent results match."""
    choices = [[None]] + [list(itertools.permutations(range(len(op['commands'])))) if op['op'] == 'concurrent' else [None] for op in ops]
    best = None
    for combo in itertools.product(*choices[1:]):
        trial = [dict(op, order=list(order)) if order is not None else op for op, order in zip(ops, combo)]
        outputs = run_ops(trial)
        if outputs == actual:
            return outputs
        best = best or outputs
    return best


def expected_document(history):
    store = Store(); store.initialize(history['config'])
    closes = [store.close(c) for c in history['commands']]; snap = store.snapshot()
    return {'customer': history.get('customer'), 'closes': closes, 'targets': snap['targets'],
            'clock': snap['clock'], 'delivery_count': snap['delivery_count']}


# ---------------------------------------------------------------- nearby scenarios

def config():
    return {'periods': [{'id': 'p1', 'start': 0, 'end': 10, 'cycle': 'month'}, {'id': 'p2', 'start': 10, 'end': 20, 'cycle': 'month'}],
            'meters': [{'id': 'a', 'account': 'alice', 'pool': 'shared'}, {'id': 'b', 'account': 'bob', 'pool': 'shared'}],
            'pools': [{'id': 'shared', 'tiers': [{'up_to': 5, 'millicents': 1000}, {'up_to': None, 'millicents': 250}]}]}


def reading(identity, meter, at, counter, revision=1, known=0, epoch='e1', void=False):
    return dict(id=identity, revision=revision, known=known, meter=meter, epoch=epoch, at=at, counter=counter, void=void)


def command(op, rows, as_of=1):
    return dict(operation_id=op, as_of=as_of, readings=rows)


def random_history(seed):
    rng = random.Random(seed); cfg = config()
    cfg['periods'] = [dict(id=f'p{i}', start=a, end=b, cycle='c0' if i < 2 else 'c1') for i, (a, b) in enumerate([(0, 4), (4, 10), (10, 17)])]
    cfg['pools'][0]['tiers'] = [dict(up_to=3, millicents=rng.randint(200, 1900)), dict(up_to=None, millicents=rng.randint(50, 700))]
    rows = []
    for m in ['a', 'b']:
        middle = rng.randint(1, 16); n = rng.randint(2, 12); mid = rng.randint(0, n)
        rows.extend([reading(m + '0', m, 0, 3), reading(m + '1', m, middle, 3 + mid), reading(m + '2', m, 17, 3 + n),
                     reading(m + '1', m, middle, 3 + rng.randint(0, n), revision=2, known=5)])
    rng.shuffle(rows)
    latest = next(r for r in rows if r['id'] == 'a1' and r['revision'] == 2)
    void = reading('a1', 'a', latest['at'], latest['counter'], revision=3, known=7, void=True)
    return cfg, rows, void


def scenarios(customer):
    yield 'customer_history', [dict(op='init', config=customer['config'])] + [dict(op='close', command=c) for c in customer['commands']] + [dict(op='snapshot')]
    for seed in range(8):
        cfg, rows, void = random_history(seed)
        yield 'nearby_history_%d' % seed, [dict(op='init', config=cfg), dict(op='close', command=command('initial', rows + rows[:2], 1)),
                                           dict(op='close', command=command('activate', [], 5)),
                                           dict(op='close', command=command('same', list(reversed(rows)), 6)),
                                           dict(op='close', command=command('retract', [void], 7)), dict(op='snapshot')]
    cfg = config(); rows = [reading('x', 'a', 0, 10), reading('y', 'a', 20, 18), reading('q', 'b', 0, 100), reading('z', 'b', 20, 106)]
    delta = [reading('y', 'b', 20, 104, revision=2, known=3), reading('z', 'b', 20, 106, revision=2, known=3, void=True)]
    yield 'revision_moves_meter_before_void_filter', [dict(op='init', config=cfg), dict(op='close', command=command('one', rows)),
                                                      dict(op='close', command=command('move', delta, 3)), dict(op='snapshot')]
    for kind in ['decrease', 'same-time', 'overlap', 'gap', 'conflict', 'clock']:
        cfg = config()
        if kind == 'gap':
            cfg['periods'][1]['start'] = 11
        bad = {'decrease': [reading('z', 'a', 20, 2)], 'same-time': [reading('z', 'a', 10, 3)],
               'overlap': [reading('z', 'a', 5, 0, epoch='e2'), reading('q', 'a', 15, 2, epoch='e2')],
               'gap': [reading('z', 'a', 20, 4)], 'conflict': [reading('y', 'a', 10, 4)], 'clock': []}[kind]
        yield 'rejected_%s_rolls_back' % kind, [dict(op='init', config=cfg), dict(op='close', command=command('base', [reading('x', 'a', 0, 0), reading('y', 'a', 10, 3)])),
                                                dict(op='snapshot'), dict(op='close', command=command('retryable', bad, 0 if kind == 'clock' else 2)),
                                                dict(op='snapshot'), dict(op='close', command=command('retryable', [], 2)), dict(op='snapshot')]
    yield 'superseded_conflict_rejected', [dict(op='init', config=config()),
                                           dict(op='close', command=command('bad', [reading('x', 'a', 0, 0), reading('x', 'a', 0, 1), reading('x', 'a', 0, 2, revision=2)])),
                                           dict(op='snapshot')]
    cfg = config(); first = command('first', [reading('x', 'a', 0, 0), reading('y', 'a', 20, 7)]); altered = copy.deepcopy(cfg)
    altered['pools'][0]['tiers'][0]['millicents'] += 1
    yield 'replay_before_clock_and_seed_binding', [dict(op='init', config=cfg), dict(op='close', command=first), dict(op='close', command=command('later', [], 9)),
                                                   dict(op='close', command=first), dict(op='close', command=dict(first, as_of=10)),
                                                   dict(op='init', config={k: list(reversed(v)) for k, v in cfg.items()}),
                                                   dict(op='init', config=altered), dict(op='snapshot')]
    yield 'restart_and_value_isolation', [dict(op='init', config=config()), dict(op='close_mutate', command=first),
                                          dict(op='subprocess_snapshot'), dict(op='close', command=first)]
    yield 'concurrent_incremental_sources', [dict(op='init', config=config()),
                                             dict(op='concurrent', calls=4, commands=[command('a', [reading('a0', 'a', 0, 0), reading('a1', 'a', 20, 8)], 10),
                                                                                    command('b', [reading('b0', 'b', 0, 0), reading('b1', 'b', 20, 5)], 10)]),
                                             dict(op='snapshot')]


def cli_histories(customer):
    cfg, rows, void = random_history(11)
    nearby = {'customer': 'Nearby Cooperative (fictional)', 'config': cfg,
              'commands': [command('n-initial', rows[:5], 1), command('n-rest', rows[5:], 4), command('n-activate', [], 5), command('n-retract', [void], 8)]}
    failing = copy.deepcopy(customer)
    failing['commands'] = customer['commands'][:2] + [command('decreasing', [reading('a9', 'a', 30, 0)], 3)]
    failing['config']['periods'].append({'id': 'p3', 'start': 20, 'end': 40, 'cycle': 'month'})
    return {'customer': customer, 'nearby': nearby, 'failing': failing}


def read_customer(data_dir):
    return json.loads((Path(data_dir) / 'customer_history.json').read_text())
