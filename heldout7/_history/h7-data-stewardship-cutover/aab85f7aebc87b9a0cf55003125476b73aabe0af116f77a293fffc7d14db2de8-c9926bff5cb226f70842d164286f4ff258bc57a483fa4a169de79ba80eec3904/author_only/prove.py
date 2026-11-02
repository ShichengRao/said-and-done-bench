"""Author-only proof for h7-data-stewardship-cutover, independent of grader/oracle.py.

Tables below were derived by hand from data/ledger.json (AUTHOR_PROOF.md):
loads per phase, qualified owners, and the effective handoffs at cutoff 10.
"""
import json
from fractions import Fraction
from itertools import product
from pathlib import Path

LOAD = {'accounts': (2, 2, 1), 'contacts': (2, 1, 2), 'tickets': (1, 2, 2)}
CAP = {'A': [3, 3, 3], 'B': [3, 3, 3]}            # warehouse uses gamma only (1 of 1) and is independent
PATHS = {'accounts': ['AAB', 'BBB'], 'contacts': ['AAA', 'BBB'], 'tickets': ['BAA', 'BBB']}


def fits(choice, cap=CAP):
    for k in range(3):
        for owner in 'AB':
            if sum(LOAD[g][k] for g, path in choice.items() if path[k] == owner) > cap[owner][k]:
                return False
    return True


def solutions(paths=PATHS, cap=CAP):
    names = sorted(paths)
    return [dict(zip(names, combo)) for combo in product(*(paths[n] for n in names)) if fits(dict(zip(names, combo)), cap)]


def pigeonhole():
    """A0 != C (phase0: 2+2 > 3), T2 != C (phase2: 2+2 > 3) => A0 == T2; A1 == A0, T1 == T2 => phase1 load 4 > 3."""
    checks = []
    for a, c, t in product(PATHS['accounts'], PATHS['contacts'], PATHS['tickets']):
        checks.append({'a0_ne_c': a[0] != c[0], 't2_ne_c': t[2] != c[2], 'a1_eq_a0': a[1] == a[0], 't1_eq_t2': t[1] == t[2]})
    return all(r['a1_eq_a0'] and r['t1_eq_t2'] for r in checks)


def fractional():
    usage = {o: [Fraction(0)] * 3 for o in 'AB'}
    for g, paths in PATHS.items():
        for path in paths:
            for k, o in enumerate(path):
                usage[o][k] += Fraction(LOAD[g][k], 2)
    return {o: [str(x) for x in row] for o, row in usage.items()}, all(usage[o][k] <= CAP[o][k] for o in 'AB' for k in range(3))


if __name__ == '__main__':
    result = {
        'path_products': len(list(product(*PATHS.values()))),
        'current_solutions': solutions(),
        'proper_subsets_feasible': {','.join(s): bool(solutions({g: PATHS[g] for g in s}))
                                    for s in (('accounts',), ('contacts',), ('tickets',), ('accounts', 'contacts'),
                                              ('accounts', 'tickets'), ('contacts', 'tickets'))},
        'continuity_forced_by_handoff_boundaries': pigeonhole(),
        'fractional_half_half': fractional(),
        'counterpart_reapproval_cutoff12': solutions({**PATHS, 'tickets': ['BAA', 'BBA', 'BBB']}),
        'counterpart_accounts_boundary0': solutions({**PATHS, 'accounts': ['AAB', 'ABB', 'BBB']}),
        'counterpart_alpha_phase1_capacity4': solutions(cap={'A': [3, 4, 3], 'B': [3, 3, 3]}),
    }
    Path(__file__).with_name('proof_result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in result.items()}))
