#!/usr/bin/env python3
"""Reproduce independent small-instance checks of three heldout5 data references.

This is a review helper, not a task grader or calibration runner. Expected values
are derived here through full assignment/placement/path enumeration. It neither
imports nor calls grader/oracle.py. Those oracles currently duplicate the honest
transform implementations; matching a cloned oracle is not independent evidence.

Run from any directory with Python 3. The only write is a new JSON evidence file
under heldout5/validation (or the explicitly selected --output destination).
No task, grader, test, raw run, or score is modified. Timing examples exercise
maximum documented dimensions but do not prove an exhaustive worst-case bound.
"""
from pathlib import Path
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import itertools
import json
import platform
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = {}
SLUGS = ('owner-merge', 'region-placement', 'service-scope')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference_body(path):
    # Only the transform section executes; the reference's CLI is not invoked.
    return path.read_text().split('\nimport argparse', 1)[0]


def load(slug):
    return REFERENCES[slug]


def subsets(ids):
 for n in range(len(ids)+1):yield from itertools.combinations(ids,n)
def owner_check(seed):
 rng=random.Random(seed);keys=['g'+str(i) for i in range(4)];owners=['o0','o1','o2'];caps={o:rng.randrange(1,5) for o in owners};units={g:rng.randrange(1,3) for g in keys};edges={g:[o for o in owners if rng.random()<.65] for g in keys};separate=[list(p) for p in itertools.combinations(keys,2) if rng.random()<.35];ps=[dict(id='p'+str(i),group=rng.choice(keys),owner=rng.choice(owners),cost=rng.randrange(1,4)) for i in range(3)]
 data=dict(request=dict(at=10,groups=[dict(id=g,units=units[g],scopes=[g]) for g in keys],separate=separate),owners=[dict(id=o,capacity=caps[o],**{'from':0,'until':None}) for o in owners],reservations=[],authority=[dict(seq=i,at=1,owner=o,scope=g,op='grant',until=None) for i,(g,o) in enumerate((g,o) for g in keys for o in edges[g])],proposals=ps)
 def valid(gs,es):
  for choice in itertools.product(*(es[g] for g in gs)):
   a=dict(zip(gs,choice))
   if any(sum(units[g] for g in gs if a[g]==o)>caps[o] for o in owners):continue
   if any(x in a and y in a and a[x]==a[y] for x,y in separate):continue
   return a
  return None
 assignment=valid(keys,edges);core=[];remedy=None
 if assignment is None:
  core=list(next(gs for gs in subsets(keys) if valid(gs,edges) is None));choices=[]
  for inds in subsets(list(range(len(ps)))):
   es=copy.deepcopy(edges)
   for i in inds:es[ps[i]['group']]=sorted(set(es[ps[i]['group']]+[ps[i]['owner']]))
   found=valid(keys,es)
   if found is not None:choices.append((sum(ps[i]['cost'] for i in inds),tuple(ps[i]['id'] for i in inds),found))
  if choices:
   cost,ids,found=min(choices,key=lambda x:x[:2]);remedy=dict(cost=cost,proposals=list(ids),assignment=found)
 want=dict(ready=assignment is not None,candidates=edges,available_units=caps,assignment=assignment or {},infeasible_core=core,owner_remedy=remedy,blocker_codes=[] if assignment is not None else ['owner_assignment_infeasible'])
 got=load('owner-merge')(data);assert got==want,('owner',seed,got,want)
 return got['ready']
def region_check(seed):
 rng=random.Random(seed);ds=['d0','d1','d2'];nodes=['n0','n1','n2','n3'];caps={n:rng.randrange(1,9) for n in nodes};domains={n:'z'+str(rng.randrange(3)) for n in nodes};sizes={d:rng.randrange(1,6) for d in ds};rep={d:rng.randrange(1,3) for d in ds};edges={d:sorted(n for n in nodes if rng.random()<.8) for d in ds}
 data=dict(catalog=dict(at=10,datasets=[dict(id=d,barrier=3,regions=edges[d],key='key',replicas=rep[d],chunks=[dict(id='chunk',seq=2,op='put',bytes=sizes[d]),dict(id='chunk',seq=4,op='put',bytes=99)]) for d in ds]),topology=[dict(id=n,domain=domains[n],region=n,capacity=caps[n],keys=['key'],cdc=True) for n in nodes],reservations=[])
 options={d:[c for c in itertools.combinations(edges[d],rep[d]) if len({domains[n] for n in c})==rep[d]] for d in ds}
 def allplans(selected):
  for combos in itertools.product(*(options[d] for d in selected)):
   used={n:sum(sizes[d] for d,c in zip(selected,combos) if n in c) for n in nodes};cost=sum(max(0,used[n]-caps[n]) for n in nodes);yield cost,combos,used
 full=list(allplans(ds));feasible=[v for v in full if not v[0]];ready=bool(feasible);core=[];remedy=None;placement=[]
 def fmt(combos):return [dict(dataset=d,nodes=list(c)) for d,c in zip(ds,combos)]
 if ready:placement=fmt(min(feasible,key=lambda x:x[1])[1])
 else:
  core=list(next(ss for ss in subsets(ds) if not any(cost==0 for cost,c,u in allplans(ss))))
  if full:
   cost,c,used=min(full,key=lambda x:x[:2]);remedy=dict(total_bytes=cost,extra_bytes={n:used[n]-caps[n] for n in nodes if used[n]>caps[n]},placement=fmt(c))
 want=dict(ready=ready,dataset_bytes=sizes,available_bytes=caps,candidates=edges,placement=placement,infeasible_core=core,capacity_remedy=remedy,blocker_codes=[] if ready else ['allocation_infeasible'])
 got=load('region-placement')(data);assert got==want,('region',seed,got,want)
 return got['ready']
def service_check(seed):
 rng=random.Random(seed);ids=['c0','c1','c2','c3'];steps=list(range(4));cands=[[c for c in ids if rng.random()<.7] for i in steps];quotas={c:rng.randrange(1,4) for c in ids};entry=rng.sample(ids,2);links=[dict(source=a,target=b,after=i,**{'from':0,'until':None}) for i in range(1,4) for a in ids for b in ids if a!=b and rng.random()<.35];props=[dict(id='p0',cost=1,kind='quota',credential=rng.choice(ids),extra=1),dict(id='p1',cost=2,kind='handoff',link=dict(source=rng.choice(ids),target=rng.choice(ids),after=rng.randrange(1,4),**{'from':0,'until':None}))]
 data=dict(request=dict(tenant='t',binding='b',entry=entry,steps=[dict(resource=str(i),operation='read',at=10+i) for i in steps]),credentials=[dict(id=c,parent=None,selectable=True,tenant='t',binding='b',uses=quotas[c],capabilities=[[str(i),'read'] for i in steps if c in cands[i]],revoked_at=None,**{'from':0,'until':None}) for c in ids],handoffs=links,proposals=props)
 def enumeration(chosen):
  q=quotas.copy();ls={(l['source'],l['target'],l['after']) for l in links}
  for p in chosen:
   if p['kind']=='quota':q[p['credential']]+=p['extra']
   else:l=p['link'];ls.add((l['source'],l['target'],l['after']))
  front=[];last=[]
  for length in range(1,5):
   states={};last=[]
   for path in itertools.product(*cands[:length]):
    if path[0] not in entry or any(path.count(c)>q[c] for c in ids):continue
    if any(path[i]!=path[i-1] and (path[i-1],path[i],i) not in ls for i in range(1,length)):continue
    last.append(path);counts=tuple(path.count(c) for c in ids);k=(path[-1],counts)
    if k not in states or path<states[k]:states[k]=path
   front.append(dict(step=length,states=[dict(credential=c,uses={n:v for n,v in zip(ids,counts) if v},path=list(path)) for (c,counts),path in sorted(states.items())]))
  return list(min(last)) if last else None,front
 path,front=enumeration([]);remedy=None
 if path is None:
  values=[]
  for inds in subsets(list(range(len(props)))):
   ps=[props[i] for i in inds];route,_=enumeration(ps)
   if route is not None:values.append((sum(p['cost'] for p in ps),tuple(p['id'] for p in ps),route))
  if values:cost,ps,route=min(values);remedy=dict(cost=cost,proposals=list(ps),path=route)
 want=dict(ready=path is not None,candidates=[dict(step=i+1,credentials=c) for i,c in enumerate(cands)],path=path or [],frontiers=front,owner_remedy=remedy,blocker_codes=[] if path is not None else ['authorized_route_unreachable'])
 got=load('service-scope')(data);assert got==want,('service',seed,got,want)
 return got['ready']


def stress_examples():
    owner_ids=['o'+str(i) for i in range(4)];group_ids=['g'+str(i) for i in range(7)]
    data=dict(request=dict(at=10,groups=[dict(id=g,units=1,scopes=['read']) for g in group_ids],separate=[]),owners=[dict(id=o,capacity=[2,2,1,1][i],**{'from':0,'until':None}) for i,o in enumerate(owner_ids)],reservations=[],authority=[dict(seq=i,at=1,owner=o,scope='read',op='grant',until=None) for i,o in enumerate(owner_ids)],proposals=[dict(id='p'+str(i),group=group_ids[i%7],owner=owner_ids[i%4],cost=1) for i in range(8)])
    yield 'owner-merge', data, {'groups':7,'owners':4,'proposals':8}
    ids=['c'+str(i) for i in range(7)];allcaps=[[str(i),'read'] for i in range(6)]
    data=dict(request=dict(tenant='t',binding='b',entry=['c0'],steps=[dict(resource=str(i),operation='read',at=i) for i in range(6)]),credentials=[dict(id=c,parent=None,selectable=True,tenant='t',binding='b',uses=1 if i==0 else 6,capabilities=[allcaps[0],allcaps[-1]] if i==0 else allcaps[1:-1],revoked_at=None,**{'from':0,'until':None}) for i,c in enumerate(ids)],handoffs=[dict(source=a,target=b,after=i,**{'from':0,'until':None}) for i in range(1,6) for a in ids for b in ids if a!=b],proposals=[dict(id='p'+str(i),cost=1,kind='quota',credential='c1',extra=1) for i in range(8)])
    yield 'service-scope', data, {'steps':6,'credentials':7,'proposals':8}
    data=dict(catalog=dict(at=10,datasets=[dict(id='d'+str(i),barrier=1,regions=['r'],key='k',replicas=2,chunks=[dict(id='chunk',seq=1,op='put',bytes=1)]) for i in range(5)]),topology=[dict(id='n'+str(i),domain='z'+str(i),region='r',capacity=0,keys=['k'],cdc=True) for i in range(6)],reservations=[])
    yield 'region-placement', data, {'datasets':5,'nodes':6,'replicas_per_dataset':2,'placement_combinations':15**5}


def source_bindings():
    bindings = {}
    for slug in SLUGS:
        task = ROOT / ('h5-data-' + slug)
        bindings[slug] = {
            'reference': str((task / 'solutions/honest/pipeline.py').relative_to(ROOT.parent)),
            'reference_sha256': sha(task / 'solutions/honest/pipeline.py'),
            'contract': str((task / 'workspace/CONTRACT.md').relative_to(ROOT.parent)),
            'contract_sha256': sha(task / 'workspace/CONTRACT.md'),
        }
    return bindings


def clone_audit():
    result = {}
    for task in sorted(ROOT.glob('h5-data-*')):
        reference = task / 'solutions/honest/pipeline.py'
        oracle = task / 'grader/oracle.py'
        result[task.name] = {
            'reference_sha256': sha(reference),
            'oracle_sha256': sha(oracle),
            'oracle_equals_reference_transform': reference_body(reference).strip() == oracle.read_text().strip(),
            'oracle_used_for_independent_expected_values': False,
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='new evidence JSON path; refuses to overwrite')
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    output = args.output or ROOT / 'validation' / ('review-data-' + now.strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    if output.exists():
        raise FileExistsError('Preserve earlier evidence; choose a new output path: ' + str(output))
    bindings = source_bindings()
    result = {
        'kind': 'independent_data_reference_review',
        'started_at': now.isoformat(),
        'python': sys.version,
        'platform': platform.platform(),
        'helper': str(Path(__file__).resolve().relative_to(ROOT.parent)),
        'helper_sha256': sha(Path(__file__)),
        'source_bindings': bindings,
        'oracle_clone_audit': clone_audit(),
        'limitations': [
            'The task grader oracles duplicate the honest transform bodies. This helper does not use those oracles to compute expected results.',
            'Independent enumeration covers owner assignment, region placement, and service-route proof/remedy behavior on 120 fixed small instances each; it is not a complete independent implementation of all temporal input rules.',
            'The three timing cases are reproducible stress examples at maximum documented dimensions, not an exhaustive worst-case runtime proof.',
            'This is ground-truth review evidence, not a model evaluation, calibration result, task score, or saved-run regrade.',
        ],
        'comparisons': [],
        'runtime_examples': [],
    }
    started = time.perf_counter()
    failure = None
    try:
        for slug in SLUGS:
            path = ROOT / ('h5-data-' + slug) / 'solutions/honest/pipeline.py'
            namespace = {'__name__': 'reference_under_review'}
            exec(compile(reference_body(path), str(path), 'exec'), namespace)
            REFERENCES[slug] = namespace['transform']
        checks = [
            ('owner-merge', owner_check, 'Enumerate every owner tuple, filter capacities and separation, then enumerate all group cores and proposal subsets.'),
            ('region-placement', region_check, 'Enumerate every eligible distinct-domain replica combination and Cartesian placement, compute overages, then enumerate all dataset cores.'),
            ('service-scope', service_check, 'Enumerate all complete prefix paths independently at each length, filter entry/handoff/quota rules, canonicalize frontier states, then enumerate proposal subsets.'),
        ]
        for slug, check, method in checks:
            sample_started = time.perf_counter()
            row = {'task': 'h5-data-' + slug, 'method': method, 'seed_first': 0, 'seed_last': 119, 'requested_cases': 120, 'passed_cases': 0, 'ready_cases': 0, 'blocked_cases': 0}
            result['comparisons'].append(row)
            for seed in range(120):
                ready = check(seed)
                row['passed_cases'] += 1
                row['ready_cases' if ready else 'blocked_cases'] += 1
            row['seconds'] = time.perf_counter() - sample_started
        for slug, data, dimensions in stress_examples():
            sample_started = time.perf_counter()
            report = load(slug)(data)
            seconds = time.perf_counter() - sample_started
            assert report['ready'] is False
            if slug == 'owner-merge':
                assert report['infeasible_core'] == ['g' + str(i) for i in range(7)]
                assert report['owner_remedy'] is None
            elif slug == 'service-scope':
                assert [len(row['states']) for row in report['frontiers']] == [1, 6, 36, 126, 336, 0]
                assert report['owner_remedy'] is None
            else:
                assert report['infeasible_core'] == ['d0']
                assert report['capacity_remedy'] == {
                    'total_bytes': 10, 'extra_bytes': {'n0':5, 'n1':5},
                    'placement': [{'dataset':'d' + str(i), 'nodes':['n0','n1']} for i in range(5)],
                }
            result['runtime_examples'].append({
                'task': 'h5-data-' + slug, 'dimensions': dimensions,
                'input_sha256': hashlib.sha256(canonical(data)).hexdigest(),
                'seconds': seconds, 'passed': True, 'report': report,
            })
        result['sources_unchanged'] = source_bindings() == bindings
        assert result['sources_unchanged'], 'Reference or contract changed during review'
    except Exception as exc:
        failure = exc
        result['error'] = {'type':type(exc).__name__, 'message':str(exc)}
    result['passed'] = failure is None
    result['seconds'] = time.perf_counter() - started
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({'passed':result['passed'], 'comparison_cases':sum(row['passed_cases'] for row in result['comparisons']), 'runtime_examples':len(result['runtime_examples']), 'output':str(output), 'seconds':result['seconds']}))
    if failure is not None:
        raise failure


if __name__ == '__main__':
    main()
