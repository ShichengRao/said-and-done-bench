"""Author-only proof for h7-data-checkpoint-publish, independent of grader/oracle.py and workspace code.

Hand table from data/transactions.json and deliveries.json (shard order archive, crm, tickets):
every offset 1..4 is delivered on all three shards, so the reach is 4/4/4 (= upper).
"""
import json
from itertools import product
from pathlib import Path

# id: (order, decision, {shard_index: offset}, depends)
TXNS = {'m41': (1, 'commit', {0: 1, 1: 1}, ()), 'm58': (2, 'commit', {1: 2, 2: 1}, ('m41',)),
        'm63': (3, 'abort', {0: 2, 2: 2}, ('m41',)), 'm77': (4, 'unresolved', {0: 3, 1: 3}, ('m58',)),
        'm82': (5, 'commit', {1: 4, 2: 3}, ('m77',)), 'm96': (6, 'commit', {0: 4, 2: 4}, ('m82',))}
MINIMUM = (2, 2, 2)


def valid(cut):
    whole = {t for t, (_, _, parts, _) in TXNS.items() if all(cut[s] >= o for s, o in parts.items())}
    partial = any(0 < sum(cut[s] >= o for s, o in parts.items()) < len(parts) for _, _, parts, _ in TXNS.values())
    return not partial and all(TXNS[t][1] != 'unresolved' and set(TXNS[t][3]) <= whole for t in whole), whole


def greatest():
    cuts = [c for c in product(range(5), repeat=3) if valid(c)[0]]
    top = tuple(max(c[i] for c in cuts) for i in range(3))
    assert top in cuts and all(all(c[i] <= top[i] for i in range(3)) for c in cuts)
    return top, len(cuts)


def snapshot(whole):
    """Hand replay: m41 adjusts cedar/team (c1) +3 and sets tier plus; m58 binds team->c2 and adjusts -2."""
    seats = {'cedar/c1': 10, 'cedar/c2': 6, 'larch/c1': 2}; tiers = {'cedar/c1': 'basic', 'cedar/c2': 'plus', 'larch/c1': 'basic'}
    team = 'cedar/c1'
    if 'm41' in whole:
        seats[team] += 3; tiers[team] = 'plus'
    if 'm58' in whole:
        team = 'cedar/c2'; seats[team] -= 2
    return {'seats': seats, 'tiers': tiers, 'cedar_team': team}


if __name__ == '__main__':
    top, count = greatest()
    whole = sorted(valid(top)[1], key=lambda t: TXNS[t][0])
    result = {'greatest_cut': dict(zip(('archive', 'crm', 'tickets'), top)), 'valid_cut_count': count,
              'meets_minimum': all(a >= b for a, b in zip(top, MINIMUM)), 'included': whole,
              'applied': [t for t in whole if TXNS[t][1] == 'commit'], 'snapshot': snapshot(set(whole)),
              'starter_single_pass_cut': {'archive': 2, 'crm': 2, 'tickets': 4},
              'starter_single_pass_valid': valid((2, 2, 4))[0]}
    Path(__file__).with_name('proof_result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
