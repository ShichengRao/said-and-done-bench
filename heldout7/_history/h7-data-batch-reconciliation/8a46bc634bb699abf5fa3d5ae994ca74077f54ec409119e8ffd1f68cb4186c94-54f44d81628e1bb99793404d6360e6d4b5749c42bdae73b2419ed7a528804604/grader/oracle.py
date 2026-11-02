"""Trusted oracle for h7-data-batch-reconciliation (adapted from the h6-data-service-scope grader oracle).

Independent of the workspace: groups visible ledger facts per reservation instead of
replaying in order, and enumerates complete Cartesian products of local options.
"""
import copy
import json
from itertools import product
from pathlib import Path


def read_data(root):
    root = Path(root)
    return {'batch': json.loads((root / 'batch.json').read_text()), 'ledger': json.loads((root / 'ledger.json').read_text())}


def write_data(root, data):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    for name in ('batch', 'ledger'):
        (root / ('%s.json' % name)).write_text(json.dumps(data[name], indent=2) + '\n')


def facts(data):
    """(availability, options) under current authority; raises ValueError for invalid records."""
    s = data['batch']; l = data['ledger']; c = {x['id']: x for x in s['credentials']}; slots = sorted(s['slots'])
    if len(c) != len(s['credentials']) or len({r['id'] for r in s['routes']}) != len(s['routes']):
        raise ValueError('duplicate authority ID')

    def records(rows):
        result = {}
        for name in {r['id'] for r in rows}:
            matching = [r for r in rows if r['id'] == name]
            if any(r != matching[0] for r in matching):
                raise ValueError('conflicting record ID')
            result[name] = matching[0]
        return result
    attempts = records(l['attempts']); receipts = records(l['receipts'])
    for row in c.values():
        if row['pool'] not in s['budgets'] or row['parent'] is not None and row['parent'] not in c:
            raise ValueError('unknown credential edge')
    for chain in [r['credentials'] for r in s['routes']] + [a['credentials'] for a in attempts.values()]:
        if not set(chain) <= set(c):
            raise ValueError('unknown chain node')
    declared = {r['reservation'] for r in receipts.values() if r['kind'] == 'reserve'}
    for row in receipts.values():
        if row['kind'] in ('reserve', 'reject') and row['attempt'] not in attempts:
            raise ValueError('unknown attempt')
        if row['kind'] in ('commit', 'release') and row['reservation'] not in declared:
            raise ValueError('unknown reservation')
    visible = [r for r in receipts.values() if r['at'] <= s['as_of']]
    for r in visible:
        if r['kind'] in ('reserve', 'reject') and attempts[r['attempt']]['at'] > r['at']:
            raise ValueError('receipt predates attempt')
    resolved = {}; key_owners = {}
    for name in sorted({r['reservation'] for r in visible if r['kind'] != 'reject'}):
        rows = [r for r in visible if r.get('reservation') == name]
        reserves = [r for r in rows if r['kind'] == 'reserve']
        if not reserves:
            raise ValueError('no visible binding')
        first = min(reserves, key=lambda r: (r['at'], r['id'])); a = attempts[first['attempt']]
        if len({(r['attempt'], r['expires']) for r in reserves}) != 1 or first['expires'] <= first['at']:
            raise ValueError('conflicting or expired binding')
        if a['key'] in key_owners:
            raise ValueError('one key bound twice')
        key_owners[a['key']] = name
        terminals = [r for r in rows if r['kind'] in ('commit', 'release')]
        if any((r['at'], r['id']) < (first['at'], first['id']) for r in terminals):
            raise ValueError('terminal before reserve')
        kinds = {r['kind'] for r in terminals}
        if len(kinds) > 1:
            raise ValueError('contradictory terminal facts')
        if 'commit' in kinds and min(r['at'] for r in terminals) >= first['expires']:
            raise ValueError('expired commit')
        state = 'committed' if 'commit' in kinds else 'released' if 'release' in kinds else 'expired' if first['expires'] <= s['as_of'] else 'held'
        resolved[name] = {'units': a['units'], 'pools': {c[n]['pool'] for n in a['credentials']}, 'expires': first['expires'], 'state': state}
    availability = {p: {t: s['budgets'][p] - sum(v['units'] for v in resolved.values() if p in v['pools'] and
                                                  (v['state'] == 'committed' or v['state'] == 'held' and t < v['expires'])) for t in slots}
                    for p in s['budgets']}
    options = {}
    for q in s['requests']:
        found = []
        for r in s['routes']:
            names = r['credentials']
            if r['request'] != q['id'] or not names or c[names[0]]['parent'] is not None or names[-1] not in q['leaves']:
                continue
            if any(c[names[i]]['parent'] != names[i - 1] for i in range(1, len(names))):
                continue
            if any(not set(q['scopes']) <= set(c[n]['scopes']) for n in names):
                continue
            for t in slots:
                if q['earliest'] <= t and t + q['duration'] <= q['latest'] and all(c[n]['start'] <= t and t + q['duration'] <= c[n]['end'] for n in names):
                    found.append((r['id'], t, frozenset(c[n]['pool'] for n in names)))
        options[q['id']] = found
    return availability, options


def _fits(data, availability, chosen):
    s = data['batch']; units = {q['id']: q['units'] for q in s['requests']}
    for t in s['slots']:
        if sum(units[q] for q, o in chosen.items() if o[1] == t) > s['workers'][str(t)]:
            return False
        for p, row in availability.items():
            if sum(units[q] for q, o in chosen.items() if p in o[2] and o[1] <= t) > row[t]:
                return False
    return True


def all_schedules(data):
    """Every complete assignment {request: (route, start)} that fits current authority."""
    availability, options = facts(data); ids = sorted(options)
    result = []
    for combo in product(*(options[q] for q in ids)):
        chosen = dict(zip(ids, combo))
        if _fits(data, availability, chosen):
            result.append({q: (o[0], o[1]) for q, o in chosen.items()})
    return result


def validate_schedule(doc, data):
    """Problems with a schedule document; [] when it is a valid full schedule for `data`."""
    try:
        availability, options = facts(data)
    except ValueError as error:
        return ['data rejected: %s' % error]
    s = data['batch']
    if not isinstance(doc, dict) or not isinstance(doc.get('calls'), list):
        return ['schedule has no calls list']
    errors = []
    if doc.get('batch') != s['batch'] or doc.get('customer') != s.get('customer') or doc.get('as_of') != s['as_of']:
        errors.append('batch/customer/as_of header mismatch')
    chosen = {}
    for call in doc['calls']:
        if not isinstance(call, dict) or call.get('request') not in options or call.get('request') in chosen:
            errors.append('unknown or repeated call %r' % (call,)); continue
        match = [o for o in options[call['request']] if o[0] == call.get('route') and o[1] == call.get('start')]
        if not match:
            errors.append('%s: route/start not permitted' % call['request']); continue
        if 'pools' in call and sorted(call['pools']) != sorted(match[0][2]):
            errors.append('%s: pools misreported' % call['request'])
        chosen[call['request']] = match[0]
    missing = sorted(set(options) - set(chosen))
    if missing:
        errors.append('requests not scheduled: %s' % missing)
    if not errors and not _fits(data, availability, chosen):
        errors.append('worker or allowance limit exceeded at some start')
    return errors


# ---- nearby variants used by functional cases ----
def with_budget(data, pool, delta):
    d = copy.deepcopy(data); d['batch']['budgets'][pool] += delta; return d


def with_worker(data, slot, delta):
    d = copy.deepcopy(data); d['batch']['workers'][str(slot)] += delta; return d


def without_request(data, request_id):
    d = copy.deepcopy(data); s = d['batch']
    s['requests'] = [q for q in s['requests'] if q['id'] != request_id]
    s['routes'] = [r for r in s['routes'] if r['request'] != request_id]
    return d


def with_receipt(data, receipt):
    d = copy.deepcopy(data); d['ledger']['receipts'].append(receipt); return d


def unordered(data):
    d = copy.deepcopy(data)
    for key in ('attempts', 'receipts'):
        d['ledger'][key].reverse()
    for key in ('credentials', 'requests', 'routes', 'slots'):
        d['batch'][key].reverse()
    d['ledger']['attempts'] += copy.deepcopy(d['ledger']['attempts'][:2])
    d['ledger']['receipts'] += copy.deepcopy(d['ledger']['receipts'][:3])
    return d


def shifted(data, delta):
    d = copy.deepcopy(data); s = d['batch']
    s['as_of'] += delta; s['slots'] = [t + delta for t in s['slots']]
    s['workers'] = {str(int(k) + delta): v for k, v in s['workers'].items()}
    for c in s['credentials']:
        c['start'] += delta; c['end'] += delta
    for q in s['requests']:
        q['earliest'] += delta; q['latest'] += delta
    for a in d['ledger']['attempts']:
        a['at'] += delta
    for r in d['ledger']['receipts']:
        r['at'] += delta
        if 'expires' in r:
            r['expires'] += delta
    return d
