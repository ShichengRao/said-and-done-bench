import copy,itertools

def transform(bundle):
 b=copy.deepcopy(bundle);cat=b['catalog'];nodes={};heads=cat['heads'].copy()
 def insert(n):
  if n['id'] in nodes and nodes[n['id']]!=n:raise ValueError('conflicting immutable node')
  nodes[n['id']]=n
 for n in cat['nodes']:insert(n)
 for obj,n in heads.items():
  if n not in nodes or nodes[n]['object']!=obj:raise ValueError('invalid snapshot head')
 events={}
 for e in b['changes']:
  if e['seq']>cat['cutover']:continue
  if e['seq'] in events and events[e['seq']]!=e:raise ValueError('conflicting visible CDC sequence')
  events[e['seq']]=e
 for seq,e in sorted(events.items()):
  if seq<=cat['watermark']:continue
  if e['op']=='delete':heads.pop(e['object'],None)
  else:
   if e['op']=='put':insert(e['value']);n=e['value']['id']
   else:n=e['node']
   if n not in nodes or nodes[n]['object']!=e['object']:raise ValueError('invalid CDC head')
   heads[e['object']]=n
 for obj,n in heads.items():
  if n not in nodes or nodes[n]['object']!=obj:raise ValueError('invalid snapshot head')
 views={};visiting=set()
 def original(n):
  if n in views:return views[n]
  if n not in nodes or n in visiting:raise ValueError('missing node or cycle')
  visiting.add(n);view={}
  for parent in nodes[n]['parents']:view.update(original(parent))
  view.update({r['key']:r for r in nodes[n]['rows']});visiting.remove(n);views[n]=view;return view
 for n in nodes:original(n)
 def erased(row):
  if row['deleted']:return []
  subjects={i['subject'] for i in b['identity'] if i['tenant']==row['tenant'] and i['alias']==row['alias'] and i['from']<=row['at'] and (i['until'] is None or row['at']<i['until'])}
  if len(subjects)!=1:raise ValueError('ambiguous or absent historical identity')
  subject=next(iter(subjects));return sorted(r['id'] for r in b['requests'] if r['tenant']==row['tenant'] and r['subject']==subject and row['at']<=r['through'])
 dirty={};erased_rows=[]
 for n,node in sorted(nodes.items()):
  for row in node['rows']:
   requests=erased(row)
   if requests:dirty[n]=True;erased_rows.append(dict(node=n,key=row['key'],requests=requests))
 erased_rows.sort(key=lambda r:(r['node'],r['key']))
 def closure(start):
  found=set()
  def visit(n):
   if n not in nodes:raise ValueError('missing hold node')
   if n in found:return
   found.add(n)
   for p in nodes[n]['parents']:visit(p)
  visit(start);return found
 held={}
 for h in b['holds']:
  if h['from']<=cat['at'] and (h['until'] is None or cat['at']<h['until']):
   for n in closure(h['node']):held.setdefault(n,[]).append(h['id'])
 policies={};seen={}
 for p in b['policies']:
  if p['known']>cat['at']:continue
  key=p['node'],p['revision']
  if key in seen and seen[key]!=p:raise ValueError('conflicting policy revision')
  seen[key]=p
  if p['approved'] and p['effective_at']<=cat['at'] and (p['node'] not in policies or p['revision']>policies[p['node']]['revision']):policies[p['node']]=p
 policy_rows=[dict(node=n,allow=p['allow'],cost=p['cost']) for n,p in sorted(policies.items())]
 clean={n:{k:(dict(key=k,deleted=True) if erased(row) else row) for k,row in view.items()} for n,view in views.items()}
 def materialize(selected):
  live=set();memo={}
  def rewritten(n):
   if n in memo:return memo[n]
   if n in selected:memo[n]=clean[n];return memo[n]
   live.add(n);v={}
   for p in nodes[n]['parents']:v.update(rewritten(p))
   v.update({r['key']:r for r in nodes[n]['rows']});memo[n]=v;return v
  logical=[]
  for obj,n in sorted(heads.items()):
   actual={k:r for k,r in rewritten(n).items() if not r['deleted']};wanted={k:r for k,r in clean[n].items() if not r['deleted']}
   if actual!=wanted:return None
   logical.append(dict(object=obj,rows=[actual[k] for k in sorted(actual)]))
  if any(n in dirty for n in live):return None
  return dict(cost=sum(policies[n]['cost'] for n in selected),rewrites=[dict(original=n,clone='rewrite:'+n,cost=policies[n]['cost'],parents=[],rows=[clean[n][k] for k in sorted(clean[n])]) for n in sorted(selected)],live_roots=[dict(object=o,node=('rewrite:'+n if n in selected else n)) for o,n in sorted(heads.items())],live_originals=sorted(live),purge_nodes=sorted(set(nodes)-live-set(held)),logical_views=logical)
 names=sorted(nodes);candidates=[];owner_candidates=[]
 for mask in range(1<<len(names)):
  selected={n for i,n in enumerate(names) if mask>>i&1};
  if not selected<=set(heads.values()):continue
  missing=sorted(n for n in selected if not policies[n]['allow'])
  if any(n not in b['reviewable_nodes'] for n in missing):continue
  plan=materialize(selected)
  if plan is None:continue
  ids=sorted(selected)
  if not missing:candidates.append(((plan['cost'],len(ids),ids),plan))
  else:owner_candidates.append(((len(missing),plan['cost'],len(ids),missing,ids),dict(approval_nodes=missing,plan=plan)))
 plan=min(candidates,key=lambda x:x[0])[1] if candidates else None
 owner=min(owner_candidates,key=lambda x:x[0])[1] if plan is None and owner_candidates else None
 return dict(ready=plan is not None,blocker_codes=[] if plan is not None else ['rewrite_authority_missing'],current_heads=[dict(object=o,node=n) for o,n in sorted(heads.items())],policies=policy_rows,erased_payloads=erased_rows,retained_for_hold=[dict(node=n,holds=sorted(ids)) for n,ids in sorted(held.items())],plan=plan,owner_review=owner)

import argparse,json,os,tempfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',default='data');p.add_argument('--output',default='output/report.json');a=p.parse_args()
    bundle={f.stem:json.loads(f.read_text()) for f in sorted(Path(a.input).glob('*.json'))}
    report=transform(bundle)
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=target.parent)
    try:
        with os.fdopen(fd,'w') as stream:json.dump(report,stream,sort_keys=True,indent=2);stream.write('\n')
        os.replace(name,target)
    finally:
        if os.path.exists(name):os.unlink(name)
if __name__=='__main__':main()
