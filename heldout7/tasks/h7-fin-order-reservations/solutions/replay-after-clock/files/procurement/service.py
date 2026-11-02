"""Procurement reservation service API (docs/service.md)."""
import copy
from .planner import optimize, validate_request
from .store import canonical, held, load, save, stock_key, tx


def view(s):
    h = held(s); rows = []
    for key, value in sorted(s['stock'].items()):
        w, i = key.split(':'); rows.append(dict(warehouse=w, ingredient=i, on_hand=value, held=h[key], available=value - h[key]))
    return dict(clock=s['clock'], stock=rows, baskets=[copy.deepcopy(s['baskets'][k]) for k in sorted(s['baskets'])], history=copy.deepcopy(s['history']))


def initialize(path, catalog):
    normalized = copy.deepcopy(catalog); normalized['stock'] = sorted(normalized['stock'], key=lambda r: (r['warehouse'], r['ingredient']))
    with tx(path) as db:
        row = db.execute('SELECT value FROM store WHERE id=1').fetchone()
        if row:
            s = load(db)
            if s['catalog'] != normalized:
                raise ValueError('different catalog')
        else:
            s = dict(catalog=normalized, clock=0, stock={stock_key(r['warehouse'], r['ingredient']): r['quantity'] for r in normalized['stock']},
                     baskets={}, requests={}, history=[])
            save(db, s)
        return view(s)


def snapshot(path):
    with tx(path) as db:
        return view(load(db))


def _check_held(b, version):
    if b is None or b['status'] != 'held' or b['version'] != version:
        raise ValueError('stale/terminal basket')


def apply(path, command):
    with tx(path) as db:
        s = load(db); q = copy.deepcopy(command); op = q['operation_id']; payload = canonical(q)
        if q['at'] < s['clock']:
            raise ValueError('time rollback')
        if op in s['requests']:
            old = s['requests'][op]
            if old['payload'] != payload:
                raise ValueError('operation conflict')
            return copy.deepcopy(old['response'])
        if q['at'] < s['clock']:
            raise ValueError('time rollback')
        for b in s['baskets'].values():
            if b['status'] == 'held' and b['expires'] <= q['at']:
                b['status'] = 'expired'; b['version'] += 1
        kind = q['kind']; selected = []
        if kind in ('reserve', 'exchange'):
            entries = [dict(basket=q['basket'], until=q['until'], request=q['request'])] if kind == 'reserve' else q['entries']
            if not entries or len({e['basket'] for e in entries}) != len(entries):
                raise ValueError('duplicate or empty exchange')
            for e in entries:
                if e['until'] <= q['at']:
                    raise ValueError('expiry')
                validate_request(s, e['request']); b = s['baskets'].get(e['basket'])
                if kind == 'reserve' and b is not None:
                    raise ValueError('basket exists')
                if kind == 'exchange':
                    _check_held(b, e['expected_version'])
            excluded = [e['basket'] for e in entries] if kind == 'exchange' else []
            plans = optimize(s, entries, excluded)
            if plans is None:
                result = 'unavailable'; selected = [s['baskets'][e['basket']] for e in entries] if kind == 'exchange' else []
            else:
                for e in entries:
                    old = s['baskets'].get(e['basket'])
                    b = dict(id=e['basket'], version=1 if old is None else old['version'] + 1, status='held', expires=e['until'],
                             request=copy.deepcopy(e['request']), **plans[e['basket']])
                    s['baskets'][e['basket']] = b; selected.append(b)
                result = 'reserved' if kind == 'reserve' else 'exchanged'
        elif kind in ('commit', 'release'):
            b = s['baskets'].get(q['basket']); _check_held(b, q['expected_version'])
            if kind == 'commit':
                for r in b['ingredients']:
                    s['stock'][stock_key(r['warehouse'], r['ingredient'])] -= r['quantity']
            b['status'] = 'committed' if kind == 'commit' else 'released'; b['version'] += 1; selected = [b]; result = b['status']
        elif kind == 'tick':
            result = 'ticked'
        else:
            raise ValueError('unknown kind')
        s['clock'] = q['at']
        response = dict(operation_id=op, result=result, baskets=copy.deepcopy(sorted(selected, key=lambda b: b['id'])))
        s['requests'][op] = dict(payload=payload, response=copy.deepcopy(response)); s['history'].append(copy.deepcopy(response))
        save(db, s)
        return response
