"""Least-cost recipe/warehouse planning across one or more baskets (docs/planning.md)."""
from .store import held, stock_key


def validate_request(s, request):
    if set(request['warehouses']) - set(s['catalog']['warehouses']) or not request['warehouses'] or len(set(request['warehouses'])) != len(request['warehouses']):
        raise ValueError('warehouse scope')
    if not request['needs'] or set(request['needs']) - set(s['catalog']['recipes']):
        raise ValueError('unknown product')


def optimize(s, entries, excluded):
    """Plan the entries; holds of `excluded` baskets are credited, all other holds kept."""
    h = held(s, excluded); available = {k: v - h[k] for k, v in s['stock'].items()}; slots = []
    for e in sorted(entries, key=lambda x: x['basket']):
        validate_request(s, e['request'])
        for product, n in sorted(e['request']['needs'].items()):
            for ordinal in range(n):
                slots.append((e['basket'], product, ordinal, e['request']['warehouses']))
    assignment = []; consumed = {k: 0 for k in available}; opened = set()
    for bid, product, ordinal, warehouses in slots:
        options = []
        for recipe, desc in sorted(s['catalog']['recipes'][product].items()):
            for wh in sorted(warehouses):
                if any(consumed[stock_key(wh, i)] + q > available[stock_key(wh, i)] for i, q in desc['ingredients'].items()):
                    continue
                w = s['catalog']['warehouses'][wh]
                options.append((desc['cost'] + w['unit_fee'] + (w['activation_fee'] if (bid, wh) not in opened else 0), recipe, wh, desc))
        if not options:
            return None
        extra, recipe, wh, desc = min(options, key=lambda o: o[:3])
        opened.add((bid, wh)); assignment.append(dict(basket=bid, product=product, ordinal=ordinal, recipe=recipe, warehouse=wh))
        for i, q in desc['ingredients'].items():
            consumed[stock_key(wh, i)] += q
    return {e['basket']: basket_plan(s, [r for r in assignment if r['basket'] == e['basket']]) for e in entries}


def basket_plan(s, rows):
    units = [{k: v for k, v in row.items() if k != 'basket'} for row in rows]; ingredients = {}; cost = 0; warehouses = set()
    for row in units:
        recipe = s['catalog']['recipes'][row['product']][row['recipe']]; w = s['catalog']['warehouses'][row['warehouse']]
        cost += recipe['cost'] + w['unit_fee']; warehouses.add(row['warehouse'])
        for i, q in recipe['ingredients'].items():
            key = (row['warehouse'], i); ingredients[key] = ingredients.get(key, 0) + q
    cost += sum(s['catalog']['warehouses'][w]['activation_fee'] for w in warehouses)
    return dict(units=units, ingredients=[dict(warehouse=w, ingredient=i, quantity=q) for (w, i), q in sorted(ingredients.items())], cost=cost)
