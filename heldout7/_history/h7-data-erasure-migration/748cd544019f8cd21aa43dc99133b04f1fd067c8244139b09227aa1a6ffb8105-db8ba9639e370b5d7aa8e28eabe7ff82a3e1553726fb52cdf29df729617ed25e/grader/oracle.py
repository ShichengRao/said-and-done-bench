"""Trusted oracle for h7-data-erasure-migration.

`transform` is the h6-data-erasure-ledger grader oracle (topological overlays and an
exhaustive separator search), and the case builders come from that grader. Both are
independent of the workspace code. Owner-review output is not used.
"""
import copy,itertools

def transform(bundle):
 b=copy.deepcopy(bundle);c=b['catalog'];store={}
 def add(row):
  if row['id'] in store and store[row['id']]!=row:raise ValueError('immutable conflict')
  store[row['id']]=row
 for row in c['nodes']:add(row)
 roots=dict(c['heads'])
 for obj,n in roots.items():
  if n not in store or store[n]['object']!=obj:raise ValueError('snapshot head')
 changes=[x for x in b['changes'] if x['seq']<=c['cutover']]
 for x,y in itertools.combinations(changes,2):
  if x['seq']==y['seq'] and x!=y:raise ValueError('CDC conflict')
 last=None
 for event in sorted(changes,key=lambda x:x['seq']):
  if event['seq']<=c['watermark'] or event['seq']==last:continue
  last=event['seq'];obj=event['object']
  if event['op']=='delete':roots.pop(obj,None);continue
  if event['op']=='put':add(event['value']);node=event['value']['id']
  else:node=event['node']
  if node not in store or store[node]['object']!=obj:raise ValueError('CDC head')
  roots[obj]=node
 ordered=[];remaining=set(store)
 while remaining:
  ready=sorted(n for n in remaining if all(p in ordered for p in store[n]['parents']))
  if not ready:raise ValueError('invalid DAG')
  ordered+=ready;remaining-=set(ready)
 mappings={}
 for row in b['identity']:mappings.setdefault((row['tenant'],row['alias']),[]).append(row)
 def requests(row):
  if row['deleted']:return []
  matches=[x for x in mappings.get((row['tenant'],row['alias']),[]) if x['from']<=row['at'] and (x['until'] is None or x['until']>row['at'])]
  names=set(x['subject'] for x in matches)
  if len(names)!=1:raise ValueError('historical identity')
  name=names.pop();return sorted(x['id'] for x in b['requests'] if (x['tenant'],x['subject'])==(row['tenant'],name) and x['through']>=row['at'])
 bad=[]
 for name,node in store.items():
  for r in node['rows']:
   hits=requests(r)
   if hits:bad.append(dict(node=name,key=r['key'],requests=hits))
 original={};snapshots={}
 for name in ordered:
  value={}
  for parent in store[name]['parents']:
   for key,row in original[parent].items():value[key]=copy.deepcopy(row)
  for row in store[name]['rows']:value[row['key']]=copy.deepcopy(row)
  original[name]=value;snapshots[name]={k:(dict(key=k,deleted=True) if requests(r) else copy.deepcopy(r)) for k,r in value.items()}
 holds={}
 for row in b['holds']:
  if not(row['from']<=c['at'] and (row['until'] is None or c['at']<row['until'])):continue
  if row['node'] not in store:raise ValueError('active hold missing')
  reach={row['node']}
  while True:
   expanded=reach|{p for n in reach for p in store[n]['parents']}
   if expanded==reach:break
   reach=expanded
  for n in reach:holds.setdefault(n,[]).append(row['id'])
 visible=[r for r in b['policies'] if r['known']<=c['at']]
 for x,y in itertools.combinations(visible,2):
  if (x['node'],x['revision'])==(y['node'],y['revision']) and x!=y:raise ValueError('policy conflict')
 policy={}
 for n in store:
  rows=[r for r in visible if r['node']==n and r['approved'] and r['effective_at']<=c['at']]
  policy[n]=max(rows,key=lambda r:r['revision'])
 safe=[]
 for count in range(len(store)+1):
  for combination in itertools.combinations(sorted(store),count):
   chosen=set(combination);missing=sorted(n for n in chosen if not policy[n]['allow'])
   if not set(missing)<=set(b['reviewable_nodes']):continue
   live=set(roots.values())-chosen
   while True:
    expanded=live|{p for n in live for p in store[n]['parents'] if p not in chosen}
    if expanded==live:break
    live=expanded
   if live&{r['node'] for r in bad}:continue
   rewritten={}
   for n in ordered:
    if n in chosen:rewritten[n]=copy.deepcopy(snapshots[n]);continue
    out={}
    for p in store[n]['parents']:out.update(rewritten[p])
    out.update({r['key']:r for r in store[n]['rows']});rewritten[n]=out
   if any({k:v for k,v in rewritten[n].items() if not v['deleted']}!={k:v for k,v in snapshots[n].items() if not v['deleted']} for n in roots.values()):continue
   cost=sum(policy[n]['cost'] for n in chosen)
   plan=dict(cost=cost,rewrites=[dict(original=n,clone='rewrite:'+n,cost=policy[n]['cost'],parents=[],rows=[snapshots[n][k] for k in sorted(snapshots[n])]) for n in combination],live_roots=[dict(object=o,node='rewrite:'+n if n in chosen else n) for o,n in sorted(roots.items())],live_originals=sorted(live),purge_nodes=sorted(set(store)-live-set(holds)),logical_views=[dict(object=o,rows=[rewritten[n][k] for k in sorted(rewritten[n]) if not rewritten[n][k]['deleted']]) for o,n in sorted(roots.items())])
   safe.append((missing,cost,list(combination),plan))
 current=[s for s in safe if not s[0]];possible=[s for s in safe if s[0]]
 plan=min(current,key=lambda s:(s[1],len(s[2]),s[2]))[3] if current else None
 owner=None
 if plan is None and possible:
  m,_,_,p=min(possible,key=lambda s:(len(s[0]),s[1],len(s[2]),s[0],s[2]));owner=dict(approval_nodes=m,plan=p)
 return dict(ready=plan is not None,blocker_codes=[] if plan else ['rewrite_authority_missing'],current_heads=[dict(object=o,node=n) for o,n in sorted(roots.items())],policies=[dict(node=n,allow=policy[n]['allow'],cost=policy[n]['cost']) for n in sorted(policy)],erased_payloads=sorted(bad,key=lambda r:(r['node'],r['key'])),retained_for_hold=[dict(node=n,holds=sorted(v)) for n,v in sorted(holds.items())],plan=plan,owner_review=owner)

def override(b,node,allow):
 b['policies'].append(dict(node=node,revision=50,known=b['catalog']['at'],effective_at=b['catalog']['at'],approved=True,allow=allow,cost=next(p['cost'] for p in b['policies'] if p['node']==node and p['revision']==1)))

def tiny():
 row=dict(key='x',deleted=False,tenant='t',alias='a',at=1,payload={'x':1})
 return dict(catalog=dict(watermark=0,cutover=0,at=2,nodes=[dict(id='N',object='o',parents=[],rows=[row])],heads={'o':'N'}),changes=[],identity=[dict(tenant='t',alias='a',subject='s',**{'from':0,'until':None})],requests=[dict(id='r',tenant='t',subject='s',through=1)],holds=[],policies=[dict(node='N',revision=1,known=0,effective_at=0,approved=True,allow=True,cost=2)],reviewable_nodes=['N'])

import json
import random
from pathlib import Path

FILES = ('catalog', 'changes', 'holds', 'identity', 'policies', 'requests')
KEYS = ('current_heads', 'erased_payloads', 'retained_for_hold', 'plan')


def read_data(root):
    return {name: json.loads((Path(root) / ('%s.json' % name)).read_text()) for name in FILES}


def write_data(root, bundle):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        (root / ('%s.json' % name)).write_text(json.dumps(bundle[name], indent=2) + '\n')


def expected(bundle):
    """The migration document the command must write, or None when it must refuse."""
    try:
        result = transform({**copy.deepcopy({k: bundle[k] for k in FILES}), 'reviewable_nodes': []})
    except ValueError:
        return None
    return {key: result[key] for key in KEYS} if result['ready'] else None


def compare(document, bundle):
    want = expected(bundle)
    if want is None:
        return ['no migration should be written for these records']
    if not isinstance(document, dict):
        return ['migration is not an object']
    return ['%s differs' % key for key in KEYS if document.get(key) != want[key]]


def nearby_cases(source):
    b = copy.deepcopy(source)
    for k in ['changes', 'identity', 'requests', 'holds', 'policies']:
        b[k].reverse()
    b['catalog']['nodes'].reverse(); b['catalog']['nodes'] += copy.deepcopy(b['catalog']['nodes'][:1]); b['identity'] += copy.deepcopy(b['identity'][:1])
    yield 'order-and-duplicates', b
    b = copy.deepcopy(source); override(b, 'S', False); yield 'shared-rewrite-denied', b
    b = copy.deepcopy(source); override(b, 'S', False); override(b, 'R1', False); yield 'no-permitted-plan', b
    b = copy.deepcopy(source); b['changes'] = [e for e in b['changes'] if e['seq'] != 12]; yield 'profile-head-unchanged', b
    b = copy.deepcopy(source); b['holds'] = []; yield 'hold-released', b
    b = copy.deepcopy(source); b['requests'] = []; yield 'no-erasure', b
    b = copy.deepcopy(source); next(n for n in b['catalog']['nodes'] if n['id'] == 'S')['rows'].append(dict(key='x', deleted=True)); yield 'existing-tombstone', b
    b = copy.deepcopy(source); b['changes'].append(dict(seq=10, object='different', op='delete')); yield 'covered-conflict', b
    b = copy.deepcopy(source); b['changes'].append(dict(seq=99, object='ignored', op='head', node='absent')); yield 'future-event-ignored', b
    b = copy.deepcopy(source); next(n for n in b['catalog']['nodes'] if n['id'] == 'B')['parents'] = ['S']; yield 'lineage-cycle', b
    b = copy.deepcopy(source); b['identity'].append({'tenant': 't', 'alias': 'reused', 'subject': 'conflict', 'from': 1, 'until': 3}); yield 'ambiguous-history', b
    b = copy.deepcopy(source); b['holds'].append({'id': 'inactive', 'node': 'absent', 'from': 100, 'until': None}); yield 'inactive-missing-hold', b
    b = copy.deepcopy(source); q = copy.deepcopy(next(p for p in b['policies'] if p['node'] == 'S' and p['revision'] == 3)); q['cost'] += 1; b['policies'].append(q); yield 'draft-policy-conflict', b
    b = copy.deepcopy(source); next(p for p in b['policies'] if p['node'] == 'S' and p['revision'] == 3)['approved'] = True; yield 'draft-approved', b
    b = copy.deepcopy(source); b['catalog']['at'] = 30; yield 'later-evaluation-time', b
    yield 'tiny', {k: v for k, v in tiny().items() if k in FILES}
    rng = random.Random(67235)
    for case in range(10):
        b = tiny(); b['catalog']['nodes'] = []; b['catalog']['heads'] = {}; b['policies'] = []
        for i in range(5):
            n = 'N' + str(i); parents = rng.sample(['N' + str(j) for j in range(i)], min(i, rng.randrange(3)))
            rows = [dict(key='k' + str(rng.randrange(3)), deleted=False, tenant='t', alias='a', at=rng.choice([1, 3]), payload={'node': n})]
            if rng.randrange(4) == 0:
                rows = [dict(key='k' + str(rng.randrange(3)), deleted=True)]
            b['catalog']['nodes'].append(dict(id=n, object='o' + str(i), parents=parents, rows=rows))
            b['policies'].append(dict(node=n, revision=1, known=0, effective_at=0, approved=True, allow=bool(rng.randrange(2)), cost=rng.randrange(5)))
        b['catalog']['heads'] = {'o3': 'N3', 'o4': 'N4'}
        if case % 2:
            b['holds'] = [dict(id='h', node='N2', **{'from': 0, 'until': None})]
        yield 'random-dag-%d' % case, {k: v for k, v in b.items() if k in FILES}
