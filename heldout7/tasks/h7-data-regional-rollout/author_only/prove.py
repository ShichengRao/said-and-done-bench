"""Author-only deduction for h7-data-regional-rollout, independent of grader/oracle.py.

Hand tables from data/: eligible links (f is us/'other' key, so link af is never
eligible) and the current leases of the three outage profiles.
"""
import json
from itertools import product
from pathlib import Path

ELIGIBLE = {'accounts': ['ab', 'bd', 'be'], 'contacts': ['ad', 'cd'], 'events': ['ae', 'cd'], 'tickets': ['ac', 'ae', 'bd', 'be']}
LEASES = {'alpha-outage': ('a', {'b': 3, 'c': 1, 'd': 3, 'e': 3}),
          'beta-outage': ('b', {'a': 1, 'c': 3, 'd': 2, 'e': 2}),
          'gamma-outage': ('c', {'a': 1, 'b': 2, 'd': 1, 'e': 3})}


def node_load(choice, down):
    load = {}
    for link in choice.values():
        for node in link:
            if node != down:
                load[node] = load.get(node, 0) + 1   # every surviving replica carries the full 1 unit
    return load


def ok(choice, profiles, extra=None):
    extra = extra or {}
    for name in profiles:
        down, leases = LEASES[name]
        for node, units in node_load(choice, down).items():
            if units > leases[node] + extra.get((name, node), 0):
                return False
    return True   # every link has two distinct nodes and one is down, so one replica always survives


def plans(profiles=tuple(LEASES), extra=None):
    names = sorted(ELIGIBLE)
    return [dict(zip(names, c)) for c in product(*(ELIGIBLE[n] for n in names)) if ok(dict(zip(names, c)), profiles, extra)]


def deduction():
    """gamma: d<=1 and contacts always uses d => events=ae, accounts/tickets avoid bd;
    a<=1 and events=ae uses a => contacts=cd, accounts!=ab, tickets not ac/ae => accounts=be, tickets=be.
    beta: e then carries ae+be+be = 3 > lease 2."""
    forced = {'accounts': 'be', 'contacts': 'cd', 'events': 'ae', 'tickets': 'be'}
    return {'gamma_forced': forced, 'gamma_unique': plans(('gamma-outage',)) == [forced],
            'beta_e_load': node_load(forced, 'b')['e'], 'beta_e_lease': LEASES['beta-outage'][1]['e']}


if __name__ == '__main__':
    result = {'products': len(list(product(*ELIGIBLE.values()))), 'deduction': deduction(), 'current_plans': plans(),
              'per_profile_plan_counts': {p: len(plans((p,))) for p in LEASES},
              'gamma_d_plus1': plans(extra={('gamma-outage', 'd'): 1}),
              'beta_e_plus1': plans(extra={('beta-outage', 'e'): 1}),
              'alpha_c_plus1': plans(extra={('alpha-outage', 'c'): 1})}
    Path(__file__).with_name('proof_result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in result.items()}))
