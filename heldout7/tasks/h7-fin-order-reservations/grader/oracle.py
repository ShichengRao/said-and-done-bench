"""Trusted independent procurement oracle; never imports candidate code.

Plans by complete enumeration of every unit's (recipe, warehouse) choice, as in
the h6 independent exhaustive checker, and models the durable store contract
(replay identity, tentative expiry, rollback, joint exchange, commit/release).
Also defines the nearby probe scenarios and CLI inputs.
"""
import copy
import itertools
import json
import random
from pathlib import Path


class Rejected(Exception):
    pass


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def check_request(cat, request):
    ws = request['warehouses']
    if not ws or len(set(ws)) != len(ws) or any(w not in cat['warehouses'] for w in ws):
        raise Rejected('warehouses')
    if not request['needs'] or any(p not in cat['recipes'] for p in request['needs']):
        raise Rejected('needs')


def exhaustive(cat, requests, available):
    """requests: {basket: request}; available: {(warehouse, ingredient): qty}. Returns (cost, vector) or None."""
    slots = []
    for bid, r in sorted(requests.items()):
        for product, n in sorted(r['needs'].items()):
            for ordinal in range(n):
                slots.append((bid, product, ordinal, [(recipe, w) for recipe in sorted(cat['recipes'][product]) for w in sorted(r['warehouses'])]))
    best = None
    for choices in itertools.product(*(s[3] for s in slots)):
        used = {}; opens = set(); cost = 0; vector = []
        for (bid, product, ordinal, _), (recipe, w) in zip(slots, choices):
            desc = cat['recipes'][product][recipe]; cost += desc['cost'] + cat['warehouses'][w]['unit_fee']; opens.add((bid, w))
            vector.append((bid, product, ordinal, recipe, w))
            for ing, q in desc['ingredients'].items():
                used[(w, ing)] = used.get((w, ing), 0) + q
        cost += sum(cat['warehouses'][w]['activation_fee'] for _, w in opens)
        if all(q <= available.get(k, 0) for k, q in used.items()) and (best is None or (cost, tuple(vector)) < best):
            best = (cost, tuple(vector))
    return best


class Store:
    def __init__(self):
        self.s = None

    def holds(self, excluded=()):
        total = {}
        for b in self.s['baskets'].values():
            if b['status'] == 'held' and b['id'] not in excluded:
                for r in b['ingredients']:
                    total[(r['warehouse'], r['ingredient'])] = total.get((r['warehouse'], r['ingredient']), 0) + r['quantity']
        return total

    def snapshot(self):
        h = self.holds(); s = self.s
        stock = [dict(warehouse=w, ingredient=i, on_hand=q, held=h.get((w, i), 0), available=q - h.get((w, i), 0)) for (w, i), q in sorted(s['stock'].items())]
        return copy.deepcopy(dict(clock=s['clock'], stock=stock, baskets=[s['baskets'][k] for k in sorted(s['baskets'])], history=s['history']))

    def initialize(self, catalog):
        normal = copy.deepcopy(catalog); normal['stock'] = sorted(normal['stock'], key=lambda r: (r['warehouse'], r['ingredient']))
        if self.s is not None:
            if canon(self.s['catalog']) != canon(normal):
                raise Rejected('catalog changed')
        else:
            self.s = dict(catalog=normal, clock=0, stock={(r['warehouse'], r['ingredient']): r['quantity'] for r in normal['stock']}, baskets={}, ops={}, history=[])
        return self.snapshot()

    def plan(self, requests, excluded):
        cat = self.s['catalog']; h = self.holds(excluded)
        available = {k: q - h.get(k, 0) for k, q in self.s['stock'].items()}
        best = exhaustive(cat, requests, available)
        if best is None:
            return None
        plans = {}
        for bid in requests:
            rows = [v for v in best[1] if v[0] == bid]; units = []; ingredients = {}; cost = 0
            for _, product, ordinal, recipe, w in rows:
                desc = cat['recipes'][product][recipe]; units.append(dict(product=product, ordinal=ordinal, recipe=recipe, warehouse=w))
                cost += desc['cost'] + cat['warehouses'][w]['unit_fee']
                for ing, q in desc['ingredients'].items():
                    ingredients[(w, ing)] = ingredients.get((w, ing), 0) + q
            cost += sum(cat['warehouses'][w]['activation_fee'] for w in sorted({r[4] for r in rows}))
            plans[bid] = dict(units=units, ingredients=[dict(warehouse=w, ingredient=i, quantity=q) for (w, i), q in sorted(ingredients.items()) if q], cost=cost)
        return plans

    def apply(self, command):
        saved = copy.deepcopy(self.s)
        try:
            return self._apply(copy.deepcopy(command))
        except Rejected:
            self.s = saved; raise

    def _apply(self, q):
        s = self.s; op = q['operation_id']
        if op in s['ops']:
            payload, response = s['ops'][op]
            if payload != canon(q):
                raise Rejected('operation reused')
            return copy.deepcopy(response)
        if q['at'] < s['clock']:
            raise Rejected('clock')
        for b in s['baskets'].values():
            if b['status'] == 'held' and b['expires'] <= q['at']:
                b['status'] = 'expired'; b['version'] += 1
        kind = q['kind']; chosen = []
        if kind == 'reserve':
            if q['basket'] in s['baskets'] or q['until'] <= q['at']:
                raise Rejected('reserve')
            check_request(s['catalog'], q['request'])
            plans = self.plan({q['basket']: q['request']}, ())
            if plans is None:
                result = 'unavailable'
            else:
                s['baskets'][q['basket']] = dict(id=q['basket'], version=1, status='held', expires=q['until'], request=q['request'], **plans[q['basket']])
                chosen = [q['basket']]; result = 'reserved'
        elif kind == 'exchange':
            entries = q['entries']; ids = [e['basket'] for e in entries]
            if not entries or len(set(ids)) != len(ids):
                raise Rejected('entries')
            for e in entries:
                b = s['baskets'].get(e['basket'])
                if b is None or b['status'] != 'held' or b['version'] != e['expected_version'] or e['until'] <= q['at']:
                    raise Rejected('exchange basket')
                check_request(s['catalog'], e['request'])
            plans = self.plan({e['basket']: e['request'] for e in entries}, set(ids)); chosen = sorted(ids)
            if plans is None:
                result = 'unavailable'
            else:
                for e in entries:
                    old = s['baskets'][e['basket']]
                    s['baskets'][e['basket']] = dict(id=e['basket'], version=old['version'] + 1, status='held', expires=e['until'], request=e['request'], **plans[e['basket']])
                result = 'exchanged'
        elif kind in ('commit', 'release'):
            b = s['baskets'].get(q['basket'])
            if b is None or b['status'] != 'held' or b['version'] != q['expected_version']:
                raise Rejected('terminal')
            if kind == 'commit':
                for r in b['ingredients']:
                    s['stock'][(r['warehouse'], r['ingredient'])] -= r['quantity']
            b['status'] = 'committed' if kind == 'commit' else 'released'; b['version'] += 1; chosen = [b['id']]; result = b['status']
        elif kind == 'tick':
            result = 'ticked'
        else:
            raise Rejected('kind')
        s['clock'] = q['at']
        response = dict(operation_id=op, result=result, baskets=[copy.deepcopy(s['baskets'][k]) for k in sorted(chosen)])
        s['ops'][op] = (canon(q), copy.deepcopy(response)); s['history'].append(copy.deepcopy(response))
        return copy.deepcopy(response)


def run_ops(ops):
    store = Store(); outputs = []
    for op in ops:
        try:
            kind = op['op']
            if kind == 'init':
                out = store.initialize(op['catalog'])
            elif kind in ('apply', 'apply_mutate'):
                out = store.apply(op['command'])
            elif kind == 'snapshot':
                out = store.snapshot()
            elif kind == 'subprocess_replay':
                out = dict(replay=store.apply(op['command']), snapshot=store.snapshot())
            elif kind == 'concurrent':
                responses = {}
                for i in op['order']:
                    try:
                        responses[i] = store.apply(op['commands'][i])
                    except Rejected:
                        responses[i] = {'error': 'ValueError'}
                out = [responses[i] for i in range(len(op['commands']))]
            else:
                raise KeyError(kind)
        except Rejected:
            out = {'error': 'ValueError'}
        outputs.append(out)
    return outputs


def expected_outputs(ops, actual):
    choices = [list(itertools.permutations(range(len(op['commands'])))) if op['op'] == 'concurrent' else [None] for op in ops]
    first = None
    for combo in itertools.product(*choices):
        outputs = run_ops([dict(op, order=list(order)) if order is not None else op for op, order in zip(ops, combo)])
        if outputs == actual:
            return outputs
        first = first or outputs
    return first


def expected_document(data):
    store = Store(); store.initialize(data['catalog'])
    responses = [store.apply(c) for c in data['commands']]
    return {'customer': data.get('customer'), 'responses': responses, 'state': store.snapshot()}


# ---------------------------------------------------------------- nearby scenarios

def catalog():
    return dict(warehouses={'east': dict(unit_fee=0, activation_fee=1), 'west': dict(unit_fee=0, activation_fee=1)},
                recipes={'alpha': {'a': dict(ingredients={'red': 2}, cost=0), 'b': dict(ingredients={'blue': 1}, cost=4)},
                         'beta': {'a': dict(ingredients={'red': 1}, cost=4), 'b': dict(ingredients={'blue': 2}, cost=0)},
                         'red': {'only': dict(ingredients={'red': 1}, cost=0)}, 'blue': {'only': dict(ingredients={'blue': 1}, cost=0)}},
                stock=[dict(warehouse=w, ingredient=i, quantity=q) for w, i, q in [('east', 'red', 1), ('east', 'blue', 2), ('west', 'red', 2), ('west', 'blue', 1)]])


def reserve(op, basket, needs, warehouses, at=1, until=100):
    return dict(op='apply', command=dict(operation_id=op, at=at, kind='reserve', basket=basket, until=until, request=dict(needs=needs, warehouses=warehouses)))


def exchange(entries, op='joint', at=2):
    return dict(operation_id=op, at=at, kind='exchange', entries=entries)


def entry(basket, needs, warehouses, version=1, until=200):
    return dict(basket=basket, expected_version=version, until=until, request=dict(needs=needs, warehouses=warehouses))


def base():
    return [dict(op='init', catalog=catalog()), reserve('hold-red', 'third-red', {'red': 1}, ['east']), reserve('hold-blue', 'third-blue', {'blue': 1}, ['west']),
            reserve('old-a', 'a', {'alpha': 1}, ['west']), reserve('old-b', 'b', {'beta': 1}, ['east'])]


def joint():
    return exchange([entry('a', {'beta': 1}, ['east']), entry('b', {'alpha': 1}, ['west'])])


def scenarios(customer):
    snap = dict(op='snapshot')
    yield 'customer_update', [dict(op='init', catalog=customer['catalog'])] + [dict(op='apply', command=c) for c in customer['commands']] + [snap]
    yield 'joint_exchange_after_single_attempts', base() + [dict(op='apply', command=exchange([entry('a', {'beta': 1}, ['east'])], op='alone0')),
                                                             dict(op='apply', command=exchange([entry('b', {'alpha': 1}, ['west'])], op='alone1')),
                                                             dict(op='apply', command=joint()), snap]
    roomy = catalog(); roomy['stock'] = [dict(r, quantity=4) for r in roomy['stock']]
    yield 'sequential_reserves_least_cost', [dict(op='init', catalog=roomy)] + [reserve('r%d' % i, str(i), needs, ['west', 'east'], at=i + 1, until=50)
                                                                               for i, needs in enumerate([{'alpha': 1, 'beta': 1}, {'alpha': 2}, {'beta': 2}])] + [snap]
    starve = catalog(); starve['warehouses'] = {'west': dict(unit_fee=0, activation_fee=0)}
    starve['stock'] = [dict(warehouse='west', ingredient='red', quantity=2), dict(warehouse='west', ingredient='blue', quantity=1)]
    yield 'locally_cheapest_recipe_starves_later_unit', [dict(op='init', catalog=starve), reserve('r', 'x', {'alpha': 1, 'red': 1}, ['west'], until=10)]
    yield 'failed_exchange_retains_old_holds', base() + [snap, dict(op='apply', command=exchange([entry('a', {'beta': 1}, ['east'])])), snap]
    yield 'expiry_rolls_back_on_error_commits_on_unavailable', [dict(op='init', catalog=catalog()), reserve('r', 'a', {'alpha': 1}, ['west'], until=3), snap,
                                                                dict(op='apply', command=dict(operation_id='bad', at=3, kind='commit', basket='a', expected_version=1)), snap,
                                                                reserve('bad', 'x', {'alpha': 6}, ['west'], at=3, until=9), snap]
    yield 'replay_before_clock_and_no_aliases', base() + [dict(op='apply_mutate', command=joint()), dict(op='apply', command=dict(operation_id='later', at=4, kind='tick')),
                                                          dict(op='apply', command=joint()), dict(op='apply', command=dict(joint(), at=4)), snap]
    yield 'commit_release_terminal_ids', base() + [dict(op='apply', command=dict(operation_id='commit', at=2, kind='commit', basket='a', expected_version=1)),
                                                   dict(op='apply', command=dict(operation_id='release', at=2, kind='release', basket='b', expected_version=1)), snap,
                                                   reserve('reuse', 'a', {'alpha': 1}, ['west'], at=2), snap]
    changed = catalog(); changed['warehouses']['east']['unit_fee'] = 1; reordered = catalog(); reordered['stock'].reverse()
    yield 'catalog_identity_and_unknown_route', [dict(op='init', catalog=catalog()), dict(op='init', catalog=reordered), dict(op='init', catalog=changed),
                                                 reserve('bad', 'b', {'red': 1}, ['east', 'unknown']), reserve('bad2', 'b', {'red': 1}, ['east', 'east']), snap]
    yield 'fresh_interpreter_replay', base() + [dict(op='apply', command=joint()), dict(op='subprocess_replay', command=joint())]
    one = catalog(); one['stock'] = [dict(r, quantity=1 if (r['warehouse'], r['ingredient']) == ('east', 'red') else 0) for r in one['stock']]
    yield 'competing_reservations', [dict(op='init', catalog=one),
                                     dict(op='concurrent', commands=[dict(operation_id=str(i), at=1, kind='reserve', basket=str(i), until=10, request=dict(needs={'red': 1}, warehouses=['east'])) for i in range(3)]),
                                     snap]
    fees = catalog(); fees['warehouses'] = {'east': dict(unit_fee=0, activation_fee=3), 'west': dict(unit_fee=1, activation_fee=0)}
    fees['stock'] = [dict(r, quantity=4) for r in fees['stock']]
    yield 'activation_fee_needs_joint_unit_choice', [dict(op='init', catalog=fees), reserve('plan', 'b', {'red': 4}, ['west', 'east'], until=10)]
    third = dict(warehouses={'east': dict(unit_fee=0, activation_fee=0)}, recipes=catalog()['recipes'],
                 stock=[dict(warehouse='east', ingredient='red', quantity=3), dict(warehouse='east', ingredient='blue', quantity=1)])
    yield 'exchange_keeps_unrelated_holds_until_they_expire', [dict(op='init', catalog=third), reserve('t', 'third', {'red': 1}, ['east'], until=5),
                                                               reserve('o', 'a', {'alpha': 1}, ['east']),
                                                               dict(op='apply', command=exchange([entry('a', {'alpha': 1, 'red': 1}, ['east'])], op='x1', at=2)),
                                                               dict(op='apply', command=exchange([entry('a', {'alpha': 1, 'red': 1}, ['east'], version=2)], op='x2', at=5)), snap]
    yield 'invalid_exchange_rolls_back_expiry', [dict(op='init', catalog=roomy), reserve('old-a', 'a', {'alpha': 1}, ['west']),
                                                 reserve('short', 'c', {'blue': 1}, ['east'], until=3), snap,
                                                 dict(op='apply', command=exchange([entry('a', {'beta': 1}, ['east']), entry('a', {'beta': 1}, ['east'])], op='dup', at=3)),
                                                 dict(op='apply', command=exchange([entry('a', {'beta': 1}, ['east'], version=2)], op='stale', at=3)),
                                                 dict(op='apply', command=exchange([entry('c', {'blue': 1}, ['east'])], op='expired', at=3)), snap,
                                                 dict(op='apply', command=exchange([entry('a', {'alpha': 2}, ['east', 'west'])], op='big', at=3)), snap]
    rng = random.Random(4302)
    for i in range(6):
        cat = catalog()
        for w in cat['warehouses'].values():
            w['activation_fee'] = rng.randrange(5); w['unit_fee'] = rng.randrange(3)
        for row in cat['stock']:
            row['quantity'] = rng.randrange(5)
        needs = {'alpha': rng.randrange(1, 3), 'beta': rng.randrange(1, 3)}
        yield 'generated_catalog_%d' % i, [dict(op='init', catalog=cat), reserve('hold', 'h', {'red': 1}, ['west', 'east']), reserve('plan', 'b', needs, ['west', 'east'], until=10),
                                          dict(op='apply', command=exchange([entry('b', {'beta': needs['beta'], 'alpha': 1}, ['east', 'west']), entry('h', {'blue': 1}, ['west'])], at=3)), snap]


def swap(data):
    text = json.dumps(data).replace('"east"', '"@@"').replace('"west"', '"east"').replace('"@@"', '"west"')
    return json.loads(text)


def cli_inputs(customer):
    nearby = swap(customer); nearby['customer'] = 'Nearby Provisions (fictional)'
    nearby['commands'].append(dict(operation_id='commit-a', at=3, kind='commit', basket='a', expected_version=2))
    failing = copy.deepcopy(customer); failing['commands'][-1]['entries'][0]['expected_version'] = 2
    return {'customer': customer, 'nearby': nearby, 'failing': failing}


def read_customer(data_dir):
    return json.loads((Path(data_dir) / 'customer_update.json').read_text())
