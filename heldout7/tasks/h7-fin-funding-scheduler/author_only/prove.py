"""Author proof for h7-fin-funding-scheduler (private; not part of the workspace).

1. Literal arithmetic over the 8 route vectors, using neither implementation.
2. The trusted grader oracle (per-scenario profile enumeration) and the honest
   reference engine (backward history search) agree on the customer records and
   on every nearby variant, including the feasible counterparts.
3. Inclusion-minimal core: the four scenarios together; every triple feasible.
Writes author_only/proof_result.json.
"""
import copy
import importlib.util
import itertools
import json
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


oracle = load(TASK / 'grader/oracle.py', 'proof_oracle')
sys.path.insert(0, str(TASK / 'workspace'))
reference = load(TASK / 'solutions/honest-implemented/files/funding_scheduler/scheduler.py', 'funding_scheduler.reference_scheduler')


def literal():
    # x,y,z = 1 for the P route of O1,O2,O3. Stage-3 loads in units of 100 cents.
    limits = {'X-cash': dict(A=2, B=2, P=3, Q=2), 'X-pledge': dict(A=3, B=2, P=2, Q=2),
              'Y-cash': dict(A=3, B=1, P=3, Q=2), 'Y-pledge': dict(A=3, B=2, P=3, Q=1)}
    ok = {}
    for name, lim in limits.items():
        ok[name] = {(x, y, z) for x, y, z in itertools.product((0, 1), repeat=3)
                    if 2 + x - y <= lim['A'] and 1 - x + y <= lim['B'] and 1 + x + y + z <= lim['P'] and 3 - x - y - z <= lim['Q']}
    counts = {n: len(v) for n, v in ok.items()}
    # O1 blind; with x=1 only Y family is split by inspect-Y, X family must share y; with x=0 the reverse.
    def family_ok(x, a, b):
        return any(any((x, y, z1) in ok[a] for z1 in (0, 1)) and any((x, y, z2) in ok[b] for z2 in (0, 1)) for y in (0, 1))
    def split_ok(x, a, b):
        return any((x, y, z) in ok[a] for y in (0, 1) for z in (0, 1)) and any((x, y, z) in ok[b] for y in (0, 1) for z in (0, 1))
    feasible = [x for x in (0, 1) if (family_ok(x, 'X-cash', 'X-pledge') if x == 1 else split_ok(x, 'X-cash', 'X-pledge'))
                and (family_ok(x, 'Y-cash', 'Y-pledge') if x == 0 else split_ok(x, 'Y-cash', 'Y-pledge'))]
    return counts, feasible


def main():
    base = oracle.read_bundle(TASK / 'workspace/data')
    counts, feasible_roots = literal()
    assert counts == {'X-cash': 4, 'X-pledge': 3, 'Y-cash': 4, 'Y-pledge': 3}, counts
    assert feasible_roots == [], feasible_roots
    variants = {}
    for name, b in oracle.variants(base):
        independent = oracle.policy_count(b)
        before = copy.deepcopy(b)
        result = reference.analyze(b)
        assert b == before
        assert result['policy_count'] == independent, (name, result, independent)
        if independent:
            schedule = reference.build_schedule(b)
            assert oracle.validate_schedule(schedule, b) == [], name
        variants[name] = independent
    assert variants['customer_records'] == 0 and variants['first_route_entitled_to_X_report'] == 6
    cores = reference.analyze(base)['infeasible_cores']
    assert cores == [['X-cash', 'X-pledge', 'Y-cash', 'Y-pledge']]
    triples = {}
    for dropped in ['X-cash', 'X-pledge', 'Y-cash', 'Y-pledge']:
        b = copy.deepcopy(base); b['scenarios'] = [s for s in b['scenarios'] if s['id'] != dropped]
        triples[dropped] = oracle.policy_count(b)
    assert all(v == 6 for v in triples.values()), triples
    ablations = {}
    b = copy.deepcopy(base); b['commitments'][0]['revision'] = 2; ablations['accepted_F_reresolved_to_revision_2'] = oracle.policy_count(b)
    b = copy.deepcopy(base)
    for r in b['routes']:
        if r['obligation'] == 'O1':
            r['inspection_ids'] = ['inspect-X', 'inspect-Y']
    ablations['both_reports_on_every_O1_route'] = oracle.policy_count(b)
    b = copy.deepcopy(base)
    for s in b['scenarios']:
        s['reveal_stage'] = 0
    ablations['scenario_known_up_front'] = oracle.policy_count(b)
    b = oracle.entitle(base, 'O1-P', 'inspect-X')
    for i in b['inspections']:
        i['stage'] = 3
    ablations['entitled_but_reports_at_stage_3'] = oracle.policy_count(b)
    expected_ablations = {'accepted_F_reresolved_to_revision_2': 3, 'both_reports_on_every_O1_route': 12,
                          'scenario_known_up_front': 144, 'entitled_but_reports_at_stage_3': 0}
    assert ablations == expected_ablations, ablations
    result = dict(literal_plan_counts=counts, literal_feasible_root_choices=feasible_roots, variant_policy_counts=variants,
                  infeasible_cores=cores, triple_policy_counts=triples, ablations=ablations)
    (TASK / 'author_only/proof_result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
