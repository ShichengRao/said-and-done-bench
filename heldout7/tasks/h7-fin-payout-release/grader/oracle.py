"""Trusted independent payout-release oracle; never imports candidate code.

Resolution and a priority-queue state scan adapted from the h6 independent checker,
plus an independent replay validator for delivered release schedules.
"""
import copy
import heapq
import itertools
import json
from pathlib import Path

STREAMS = {'owner': 'owners', 'payout': 'payouts', 'bridge': 'leases'}


def read_batch(root):
    root = Path(root); header = json.loads((root / 'batch.json').read_text())
    b = dict(batch=header['batch'], as_of=header['as_of'], wallets=header['accounts'], owners=[], payouts=[], leases=[])
    for line in (root / 'instructions.jsonl').read_text().splitlines():
        if line.strip():
            row = json.loads(line); b[STREAMS[row.pop('stream')]].append(row)
    return b


def write_batch(root, b):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    header = {'customer': 'Kestrel Marketplace Ltd (fictional)', 'batch': b['batch'], 'as_of': b['as_of'], 'accounts': b['wallets']}
    (root / 'batch.json').write_text(json.dumps(header, indent=2) + '\n')
    rows = [{'stream': s, **r} for s, k in STREAMS.items() for r in b[k]]
    (root / 'instructions.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))


def resolve(b):
    result = {}
    for kind in ['owners', 'payouts', 'leases']:
        rows = [r for r in b[kind] if r['known'] <= b['as_of']]
        for x, y in itertools.combinations(rows, 2):
            if (x['id'], x['revision']) == (y['id'], y['revision']) and x != y:
                raise ValueError('conflict')
        selected = []
        for name in sorted(set(r['id'] for r in rows)):
            signed = [r for r in rows if r['id'] == name and r['signed']]
            if not signed:
                continue
            r = max(signed, key=lambda r: r['revision'])
            if not r['void']:
                selected.append({k: (sorted(v) if isinstance(v, list) else v) for k, v in r.items() if k not in ['revision', 'known', 'signed', 'void']})
        result[kind] = {r['id']: r['wallet'] for r in selected} if kind == 'owners' else selected
    return result


def scan(wallets, a):
    jobs = {r['id']: r for r in a['payouts']}; loans = {r['id']: r for r in a['leases']}; names = sorted(jobs); owner = a['owners']
    initial = tuple([0] * len(names)); queue = [(0, (), initial, '')]; seen = {}
    def cash(state, loan):
        balances = {w['id']: w['balance'] for w in wallets}
        for name, status in zip(names, state):
            r = jobs[name]
            if status >= 1:
                balances[owner[r['source_owner']]] -= r['cents']
            if status == 2:
                balances[owner[r['destination_owner']]] += r['cents']
        if loan:
            balances[owner[loans[loan]['owner']]] += loans[loan]['cents']
        return balances
    while queue:
        length, path, statuses, active = heapq.heappop(queue); state = (statuses, active)
        if state in seen:
            continue
        seen[state] = path; balances = cash(statuses, active); states = dict(zip(names, statuses)); successors = []
        for i, name in enumerate(names):
            row = jobs[name]; status = statuses[i]; updated = list(statuses)
            if status == 0 and balances[owner[row['source_owner']]] >= row['cents']:
                updated[i] = 1; successors.append(('dispatch:' + name, tuple(updated), active))
            if status == 1 and all(states[p] >= 1 for p in row['receipt_after']):
                updated[i] = 2; successors.append(('receipt:' + name, tuple(updated), active))
        if active:
            row = loans[active]
            if balances[owner[row['owner']]] >= row['cents'] and all(states[p] == 2 for p in row['release_after']):
                successors.append(('repay:' + active, statuses, ''))
        else:
            for name, row in loans.items():
                if all(states[p] == 2 for p in row['activate_after']):
                    successors.append(('draw:' + name, statuses, name))
        for action, ss, ll in successors:
            if (ss, ll) not in seen:
                heapq.heappush(queue, (length + 1, path + (action,), ss, ll))
    complete = [s for s in seen if all(x == 2 for x in s[0]) and not s[1]]
    best = max((sum(jobs[n]['cents'] for n, x in zip(names, s[0]) if x == 2) for s in seen), default=0)
    return dict(complete=bool(complete), reachable_states=len(seen), max_settled_cents=best,
                requested_cents=sum(r['cents'] for r in jobs.values()),
                plan=list(min((seen[s] for s in complete), key=lambda p: (len(p), p))) if complete else None)


def releasable(b):
    return scan(b['wallets'], resolve(b))['complete']


def validate_release(doc, b):
    """Independently replay a delivered release schedule; return a list of errors."""
    try:
        a = resolve(b)
    except ValueError as error:
        return ['instructions invalid: ' + str(error)]
    if not isinstance(doc, dict) or not isinstance(doc.get('plan'), list):
        return ['release schedule lacks a plan']
    errors = []
    if doc.get('batch') != b['batch'] or doc.get('as_of') != b['as_of']:
        errors.append('batch or cutoff differs')
    jobs = {r['id']: r for r in a['payouts']}; loans = {r['id']: r for r in a['leases']}; owner = a['owners']
    cash = {w['id']: w['balance'] for w in b['wallets']}; sent = set(); got = set(); active = None
    for number, step in enumerate(doc['plan']):
        if not isinstance(step, str) or ':' not in step:
            return errors + ['malformed step %d' % number]
        kind, name = step.split(':', 1)
        if kind == 'dispatch' and name in jobs and name not in sent and cash[owner[jobs[name]['source_owner']]] >= jobs[name]['cents']:
            cash[owner[jobs[name]['source_owner']]] -= jobs[name]['cents']; sent.add(name)
        elif kind == 'receipt' and name in sent and name not in got and set(jobs[name]['receipt_after']) <= sent:
            cash[owner[jobs[name]['destination_owner']]] += jobs[name]['cents']; got.add(name)
        elif kind == 'draw' and name in loans and active is None and set(loans[name]['activate_after']) <= got:
            cash[owner[loans[name]['owner']]] += loans[name]['cents']; active = name
        elif kind == 'repay' and name == active and cash[owner[loans[name]['owner']]] >= loans[name]['cents'] and set(loans[name]['release_after']) <= got:
            cash[owner[loans[name]['owner']]] -= loans[name]['cents']; active = None
        else:
            return errors + ['step %d (%s) is not allowed by the signed instructions' % (number, step)]
    if got != set(jobs) or active is not None:
        errors.append('plan does not settle every payout with all bridges repaid')
    if doc.get('settled') != sorted(got):
        errors.append('settled list differs from replay')
    if doc.get('final_balances') != cash:
        errors.append('final balances differ from replay')
    return sorted(set(errors))


def signed(b, stream, **payload):
    b = copy.deepcopy(b); b[stream].append(dict(revision=50, known=b['as_of'], signed=True, void=False, **payload)); return b


def variants(b):
    yield 'customer_batch', copy.deepcopy(b)
    bridge = signed(b, 'leases', id='LD', owner='desk-D', cents=1, activate_after=[], release_after=['P2'])
    yield 'signed_early_D_bridge', bridge
    provider = copy.deepcopy(b); provider['as_of'] = 30
    yield 'provider_release_received_by_cutoff', provider
    x = copy.deepcopy(bridge)
    for key in ('owners', 'payouts', 'leases', 'wallets'):
        x[key].reverse()
    x['payouts'] += copy.deepcopy(x['payouts'][:2])
    yield 'early_bridge_reordered_redelivered', x
    x = copy.deepcopy(b)
    for w in x['wallets']:
        if w['id'] == 'A':
            w['balance'] = 8
    yield 'higher_opening_balance_A', x
    x = copy.deepcopy(b)
    x['payouts'] = [r for r in x['payouts'] if r['id'] not in ('P4', 'P5')]
    x['leases'] = [r for r in x['leases'] if r['id'] != 'LA']
    yield 'batch_without_P4_P5', x
