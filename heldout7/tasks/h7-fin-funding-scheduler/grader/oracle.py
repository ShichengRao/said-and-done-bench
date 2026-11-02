"""Trusted independent oracle for the funding scheduler; never imports candidate code.

Reconstructs signed authority separately, enumerates complete per-scenario route
profiles, rebuilds the endogenous observation histories each profile produces, and
keeps only profiles whose actions agree on identical histories.
"""
import copy
import itertools
import json
from pathlib import Path


def read_bundle(root):
    root = Path(root)
    agreement = json.loads((root / 'agreement.json').read_text())
    book = json.loads((root / 'obligations.json').read_text())
    return dict(agreement=agreement.get('agreement', ''), as_of=agreement['as_of'], horizon=agreement['horizon'],
                facilities=agreement['facilities'], collateral=agreement['collateral'], scenarios=agreement['scenarios'],
                obligations=book['obligations'], commitments=book['commitments'],
                routes=[json.loads(s) for s in (root / 'offers.jsonl').read_text().splitlines() if s.strip()],
                inspections=json.loads((root / 'inspections.json').read_text()))


def write_bundle(root, b):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    agreement = {'customer': 'Brightwater Cold Chain Ltd (fictional)', 'agreement': b.get('agreement', ''), 'as_of': b['as_of'],
                 'horizon': b['horizon'], 'facilities': b['facilities'], 'collateral': b['collateral'], 'scenarios': b['scenarios']}
    (root / 'agreement.json').write_text(json.dumps(agreement, indent=2) + '\n')
    (root / 'obligations.json').write_text(json.dumps({'obligations': b['obligations'], 'commitments': b['commitments']}, indent=2) + '\n')
    (root / 'offers.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in b['routes']))
    (root / 'inspections.json').write_text(json.dumps(b['inspections'], indent=2) + '\n')


def authority(b):
    records = [r for r in b['routes'] if r['known'] <= b['as_of']]
    for left, right in itertools.combinations(records, 2):
        if (left['id'], left['revision']) == (right['id'], right['revision']) and left != right:
            raise ValueError('conflicting deliveries')
    obligations = {o['id']: o for o in b['obligations'] + b['commitments']}
    def payload(row):
        if row['obligation'] not in obligations or row['facility'] not in b['facilities']:
            raise ValueError('unknown route reference')
        item = {k: copy.deepcopy(row[k]) for k in ['id', 'revision', 'obligation', 'facility', 'pledge_cents', 'windows']}
        o = obligations[row['obligation']]
        windows = sorted(item['windows'], key=lambda w: (w['from_stage'], w['until_stage'], w['pool'])); item['windows'] = windows
        starts = [o['pay_stage']] + [w['until_stage'] for w in windows[:-1]]
        if not windows or windows[-1]['until_stage'] != o['repay_stage'] or row['pledge_cents'] < o['cents']:
            raise ValueError('invalid exposure')
        if any(w['from_stage'] != a or w['until_stage'] <= a or w['pool'] not in b['collateral'] for a, w in zip(starts, windows)):
            raise ValueError('invalid window')
        lookup = {i['id']: i['stage'] for i in b.get('inspections', [])}
        item['inspection_ids'] = sorted(set(row.get('inspection_ids', [])))
        for identity in item['inspection_ids']:
            if identity not in lookup or lookup[identity] <= o['pay_stage']:
                raise ValueError('unavailable or retroactive inspection')
        return item
    offers = []
    for identity in sorted({r['id'] for r in records}):
        signed = [r for r in records if r['id'] == identity and r['signed']]
        if signed:
            chosen = max(signed, key=lambda r: r['revision'])
            if not chosen['void']:
                offers.append(payload(chosen))
    commitments = []
    for c in sorted(b['commitments'], key=lambda c: c['id']):
        matches = [r for r in records if r['id'] == c['route'] and r['revision'] == c['revision'] and r['signed'] and not r['void'] and r['obligation'] == c['id']]
        if not matches:
            raise ValueError('unknown accepted revision')
        commitments.append(dict(id=c['id'], cents=c['cents'], pay_stage=c['pay_stage'], repay_stage=c['repay_stage'], route=payload(matches[0])))
    return dict(offers=offers, commitments=commitments)


def context(b):
    auth = authority(b)
    return {'b': b, 'auth': auth, 'worlds': {w['id']: w for w in b['scenarios']}, 'routes': {r['id']: r for r in auth['offers']}}


def history(ctx, world, stage, plan):
    frames = []
    for t in range(stage + 1):
        entitled = set()
        for c in ctx['auth']['commitments']:
            entitled.update(c['route']['inspection_ids'])
        for o in ctx['b']['obligations']:
            if o['pay_stage'] < t and o['id'] in plan:
                entitled.update(ctx['routes'][plan[o['id']]].get('inspection_ids', []))
        arrived = tuple(sorted((i['id'], i['results'][world['id']]) for i in ctx['b'].get('inspections', []) if i['stage'] == t and i['id'] in entitled))
        frames.append((world['signals'][t], world['id'] if t >= world['reveal_stage'] else '', arrived))
    return tuple(frames)


def use(ctx, plan, stage):
    loans = [(c, c['route']) for c in ctx['auth']['commitments']] + [(o, ctx['routes'][plan[o['id']]]) for o in ctx['b']['obligations'] if o['id'] in plan]
    cash = {n: sum(o['cents'] for o, r in loans if r['facility'] == n and o['pay_stage'] <= stage < o['repay_stage']) for n in ctx['b']['facilities']}
    pools = {n: sum(r['pledge_cents'] for o, r in loans for w in r['windows'] if w['pool'] == n and o['pay_stage'] <= stage < o['repay_stage'] and w['from_stage'] <= stage < w['until_stage']) for n in ctx['b']['collateral']}
    return dict(facilities=cash, collateral=pools)


def fits(ctx, world, plan, stage):
    used = use(ctx, plan, stage)
    return all(n <= ctx['worlds'][world][cat][key][stage] for cat in used for key, n in used[cat].items())


def policy_count(b):
    """Number of distinct reachable binding decision tables (0 when no schedule exists)."""
    ctx = context(b); obs = sorted(b['obligations'], key=lambda o: o['id']); worlds = sorted(ctx['worlds'])
    vectors = list(itertools.product(*(sorted(r['id'] for r in ctx['routes'].values() if r['obligation'] == o['id']) for o in obs)))
    choices = []
    for w in worlds:
        choices.append([dict(zip([o['id'] for o in obs], v)) for v in vectors
                         if all(fits(ctx, w, dict(zip([o['id'] for o in obs], v)), k) for k in range(b['horizon']))])
    tables = set()
    for profile in itertools.product(*choices):
        table = {}; conflict = False
        for w, plan in zip(worlds, profile):
            for stage in range(b['horizon']):
                actions = tuple((o['id'], plan[o['id']]) for o in obs if o['pay_stage'] == stage)
                if not actions:
                    continue
                key = (stage, history(ctx, ctx['worlds'][w], stage, plan))
                if key in table and table[key] != actions:
                    conflict = True; break
                table[key] = actions
            if conflict:
                break
        if not conflict:
            tables.add(tuple(sorted(table.items())))
    return len(tables)


def validate_schedule(schedule, b):
    """Independent executable check of a delivered schedule document."""
    try:
        ctx = context(b)
    except ValueError as error:
        return ['records invalid: ' + str(error)]
    if not isinstance(schedule, dict) or not isinstance(schedule.get('decisions'), list):
        return ['schedule is not an object with decisions']
    nodes = {}; errors = []
    for node in schedule['decisions']:
        try:
            key = (node['stage'], tuple((f[0], f[1], tuple(tuple(p) for p in f[2])) for f in node['history']))
            value = {a['obligation']: a['route'] for a in node['assignment']}
        except (KeyError, TypeError, IndexError):
            return ['malformed decision node']
        if key in nodes and nodes[key] != value:
            errors.append('two decisions for one observed history')
        nodes[key] = value
    for world in sorted(ctx['worlds']):
        plan = {}
        for stage in range(b['horizon']):
            due = sorted(o['id'] for o in b['obligations'] if o['pay_stage'] == stage)
            if due:
                key = (stage, history(ctx, ctx['worlds'][world], stage, plan))
                chosen = nodes.get(key)
                if chosen is None:
                    errors.append('no decision for observed history in %s at stage %d' % (world, stage)); break
                if sorted(chosen) != due or any(r not in ctx['routes'] or ctx['routes'][r]['obligation'] != o for o, r in chosen.items()):
                    errors.append('invalid assignment in %s at stage %d' % (world, stage)); break
                plan.update(chosen)
            if not fits(ctx, world, plan, stage):
                errors.append('cash or collateral limit exceeded in %s at stage %d' % (world, stage)); break
    return sorted(set(errors))


# Nearby agreement variants used both for diagnostics and author proofs.
def entitle(b, route, report):
    b = copy.deepcopy(b)
    for row in b['routes']:
        if row['id'] == route and row['known'] <= b['as_of']:
            row['inspection_ids'] = sorted(set(row.get('inspection_ids', [])) | {report})
    return b


def variants(b):
    yield 'customer_records', copy.deepcopy(b)
    yield 'first_route_entitled_to_X_report', entitle(b, 'O1-P', 'inspect-X')
    yield 'alternate_route_entitled_to_Y_report', entitle(b, 'O1-Q', 'inspect-Y')
    x = copy.deepcopy(b)
    for s in x['scenarios']:
        s['collateral']['P'][3] += 100
    yield 'extra_P_collateral_at_stage_3', x
    for dropped in ('X-cash', 'Y-pledge'):
        x = copy.deepcopy(b); x['scenarios'] = [s for s in x['scenarios'] if s['id'] != dropped]
        for i in x['inspections']:
            i['results'] = {k: v for k, v in i['results'].items() if k != dropped}
        yield 'agreement_without_' + dropped, x
    x = entitle(b, 'O1-P', 'inspect-X')
    for key in ('routes', 'scenarios', 'obligations', 'inspections'):
        x[key].reverse()
    for r in x['routes']:
        r['windows'].reverse()
    yield 'entitled_unordered_ledger', x
    x = copy.deepcopy(b)
    for s in x['scenarios']:
        s['reveal_stage'] = min(s['reveal_stage'], 2)
    yield 'scenario_confirmed_at_stage_2', x
