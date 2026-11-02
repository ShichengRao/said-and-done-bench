"""Least-cost recipe/warehouse planning across one or more baskets (docs/planning.md)."""
import copy
from .store import held, stock_key


def validate_request(s, request):
    if set(request['warehouses']) - set(s['catalog']['warehouses']) or not request['warehouses'] or len(set(request['warehouses'])) != len(request['warehouses']):
        raise ValueError('warehouse scope')
    if not request['needs'] or set(request['needs']) - set(s['catalog']['recipes']):
        raise ValueError('unknown product')


def optimize(s, entries, excluded):
    """Jointly plan every entry; holds of `excluded` baskets are credited, all other holds kept."""
    h = held(s); available = {k: v - h[k] for k, v in s['stock'].items()}; slots = []
    for e in sorted(entries, key=lambda x: x['basket']):
        validate_request(s, e['request'])
        for product, n in sorted(e['request']['needs'].items()):
            for ordinal in range(n):
                slots.append((e['basket'], product, ordinal, e['request']['warehouses']))
    best = None; assignment = []; consumed = {k: 0 for k in available}; opened = set()

    def recurse(index, cost):
        nonlocal best
        if best is not None and cost > best[0]:
            return
        if index == len(slots):
            key = (cost, tuple((r['basket'], r['product'], r['ordinal'], r['recipe'], r['warehouse']) for r in assignment))
            if best is None or key < best[:2]:
                best = (cost, key[1], copy.deepcopy(assignment))
            return
        bid, product, ordinal, warehouses = slots[index]; options = []
        for recipe, desc in sorted(s['catalog']['recipes'][product].items()):
            for wh in sorted(warehouses):
                if any(consumed[stock_key(wh, i)] + q > available[stock_key(wh, i)] for i, q in desc['ingredients'].items()):
                    continue
                w = s['catalog']['warehouses'][wh]
                extra = desc['cost'] + w['unit_fee'] + (w['activation_fee'] if (bid, wh) not in opened else 0)
                options.append((extra, recipe, wh, desc))
        for extra, recipe, wh, desc in options:
            isnew = (bid, wh) not in opened; opened.add((bid, wh))
            assignment.append(dict(basket=bid, product=product, ordinal=ordinal, recipe=recipe, warehouse=wh))
            for i, q in desc['ingredients'].items():
                consumed[stock_key(wh, i)] += q
            recurse(index + 1, cost + extra)
            for i, q in desc['ingredients'].items():
                consumed[stock_key(wh, i)] -= q
            assignment.pop()
            if isnew:
                opened.remove((bid, wh))

    recurse(0, 0)
    if best is None:
        return None
    return {e['basket']: basket_plan(s, [r for r in best[2] if r['basket'] == e['basket']]) for e in entries}


def basket_plan(s, rows):
    units = [{k: v for k, v in row.items() if k != 'basket'} for row in rows]; ingredients = {}; cost = 0; warehouses = set()
    for row in units:
        recipe = s['catalog']['recipes'][row['product']][row['recipe']]; w = s['catalog']['warehouses'][row['warehouse']]
        cost += recipe['cost'] + w['unit_fee']; warehouses.add(row['warehouse'])
        for i, q in recipe['ingredients'].items():
            key = (row['warehouse'], i); ingredients[key] = ingredients.get(key, 0) + q
    cost += sum(s['catalog']['warehouses'][w]['activation_fee'] for w in warehouses)
    return dict(units=units, ingredients=[dict(warehouse=w, ingredient=i, quantity=q) for (w, i), q in sorted(ingredients.items())], cost=cost)
