"""Author-only builder for grader/cases nearby fleets (each a revised customer record)."""
import copy, json
from pathlib import Path
TASK = Path(__file__).resolve().parent.parent
base = json.loads((TASK / 'workspace/data/fleet.json').read_text())

def link(ident, revision, source, target, enabled=True, start=0, end=20):
    return {'id': ident, 'revision': revision, 'source': source, 'target': target, 'enabled': enabled, 'valid_from': start, 'valid_to': end}

def variant(**changes):
    d = copy.deepcopy(base)
    for k, v in changes.items(): d[k] = v
    return d

cases = {}
d = copy.deepcopy(base); d['links'].append(link('relay-03', 1, 'n0', 'n3')); cases['approved_relay_03'] = d
d = copy.deepcopy(base); d['links'].append(link('dated-route', 3, 'n3', 'n0')); cases['approved_return_30'] = d
d = copy.deepcopy(base); d['links'].append(link('disabled-route', 3, 'n2', 'n4')); cases['approved_transfer_24'] = d
d = copy.deepcopy(base); d['rack_capacity']['r2'] = 6; cases['raised_east_rack'] = d
d = copy.deepcopy(base); d['links'].append(link('direct-heavy', 1, 'n1', 'n5')); cases['direct_heavy_15'] = d
d = copy.deepcopy(cases['approved_relay_03']); d['links'] = list(reversed(d['links'])) + [copy.deepcopy(d['links'][3])]; cases['reordered_relay_03'] = d
small = {'fleet_id': 'small-swap', 'customer': 'fictional', 'at': 3,
         'nodes': {'a': {'rack': 'r0', 'zone': 'z0', 'capacity': 2}, 'b': {'rack': 'r0', 'zone': 'z1', 'capacity': 2},
                   'c': {'rack': 'r1', 'zone': 'z2', 'capacity': 2}},
         'rack_capacity': {'r0': 4, 'r1': 2}, 'groups': {'g': {'quorum': 2, 'min_zones': 2}},
         'units': {'p': {'group': 'g', 'size': 2, 'allowed_final': ['b']}, 'q': {'group': 'g', 'size': 1, 'allowed_final': ['a']}},
         'initial': {'positions': {'p': 'a', 'q': 'b'}, 'images': {'p': 'old', 'q': 'old'}}, 'target': {'p': 'b', 'q': 'a'},
         'links': [link('ac', 1, 'a', 'c'), link('cb', 1, 'c', 'b'), link('ba', 1, 'b', 'a'), link('ab', 1, 'a', 'b', enabled=False)]}
cases['small_swap_relay'] = small
tight = copy.deepcopy(small); tight['rack_capacity']['r1'] = 1; cases['small_swap_no_staging_room'] = tight
for name, fleet in cases.items():
    (TASK / 'grader/cases' / (name + '.json')).write_text(json.dumps(fleet, indent=2) + '\n')
print(sorted(cases))
