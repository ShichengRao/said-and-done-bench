"""Independent full copy-state BFS and grouped-revision authority reconstruction."""
import copy,hashlib,itertools,json
from collections import deque

def authority(d):
 result=set()
 for name in {r['id'] for r in d['links']}:
  rows=[r for r in d['links'] if r['id']==name]
  for revision in {r['revision'] for r in rows}:
   same=[r for r in rows if r['revision']==revision]
   if any(r!=same[0] for r in same):raise ValueError('conflicting link revision')
  latest=max(rows,key=lambda r:r['revision'])
  if latest['enabled'] and latest['valid_from']<=d['at']<latest['valid_to']:result.add((latest['source'],latest['target']))
 return result

def final_valid(d):
 pos=d['target']
 if len(set(pos.values()))!=len(pos):return False
 if any(n not in d['units'][u]['allowed_final'] or d['units'][u]['size']>d['nodes'][n]['capacity'] for u,n in pos.items()):return False
 if any(sum(d['units'][u]['size'] for u,n in pos.items() if d['nodes'][n]['rack']==r)>cap for r,cap in d['rack_capacity'].items()):return False
 for group,policy in d['groups'].items():
  nodes=[n for u,n in pos.items() if d['units'][u]['group']==group]
  if len(nodes)<policy['quorum'] or len({d['nodes'][n]['zone'] for n in nodes})<policy['min_zones']:return False
 return True

def full_search(d,edges,return_states=False):
 # Independent full copy-state BFS: unlike the reference's stable-state expansion,
 # copying, ready and commit each enter the queue as distinct states.
 us=sorted(d['units']);ns=sorted(d['nodes']);start=(tuple(d['initial']['positions'][u] for u in us),tuple(d['initial']['images'][u] for u in us),None);queue=deque([start]);paths={start:[]};enc=[];goal=None;stable=0
 def valid(pos,shadow):
  occupied=list(pos)+([] if shadow is None else [shadow[1]])
  if len(set(occupied))!=len(occupied):return False
  costs={r:0 for r in d['rack_capacity']}
  for u,node in list(zip(us,pos))+([] if shadow is None else [(shadow[0],shadow[1])]):
   size=d['units'][u]['size']
   if size>d['nodes'][node]['capacity']:return False
   costs[d['nodes'][node]['rack']]+=size
  for group,policy in d['groups'].items():
   places=[pos[i] for i,u in enumerate(us) if d['units'][u]['group']==group]
   if len(places)<policy['quorum'] or len({d['nodes'][n]['zone'] for n in places})<policy['min_zones']:return False
  return all(costs[r]<=v for r,v in d['rack_capacity'].items())
 while queue:
  state=queue.popleft();pos,im,shadow=state;enc.append(json.dumps([dict(zip(us,pos)),dict(zip(us,im)),None if shadow is None else list(shadow)],sort_keys=True,separators=(',',':')));nexts=[]
  if shadow is None:
   stable+=1
   if dict(zip(us,pos))==d['target'] and all(x=='new' for x in im) and final_valid(d) and goal is None:goal=paths[state]
   for i,u in enumerate(us):
    for dest in ns:
     sh=(u,dest,'copying')
     if (pos[i],dest) in edges and valid(pos,sh):nexts.append((['start',u,dest],(pos,im,sh)))
  elif shadow[2]=='copying':nexts.append((['ready',shadow[0],shadow[1]],(pos,im,(shadow[0],shadow[1],'ready'))))
  else:
   i=us.index(shadow[0]);new=list(pos);new[i]=shadow[1];images=list(im);images[i]='new'
   if valid(new,None):nexts.append((['commit',shadow[0],shadow[1]],(tuple(new),tuple(images),None)))
  for action,nxt in sorted(nexts):
   if nxt not in paths:paths[nxt]=paths[state]+[action];queue.append(nxt)
 result=dict(reachable_count=len(paths),stable_count=stable,reachable_sha256=hashlib.sha256(json.dumps(sorted(enc),sort_keys=True,separators=(',',':')).encode()).hexdigest(),plan=goal)

 return (result,set(paths)) if return_states else result

def audit(d):
 edges=authority(d);actual=full_search(d,edges);static=final_valid(d)
 proposals=sorted(d['owner_requests'],key=lambda q:q['id']);choices=[]
 for n in range(len(proposals)+1):
  for chosen in itertools.combinations(proposals,n):
   choices.append((sum(q['cost'] for q in chosen),[q['id'] for q in chosen],chosen))
 owner=None
 for cost,ids,chosen in sorted(choices,key=lambda row:row[:2]):
  result=actual if not chosen else full_search(d,edges|{tuple(e) for q in chosen for e in q['edges']})
  if static and result['plan'] is not None:
   owner={'cost':cost,'requests':ids,'plan':result['plan']};break
 certified=static and actual['plan'] is not None
 return {'static_final_valid':static,'active_links':[list(e) for e in sorted(edges)],**actual,'certifiable':certified,'owner_plan':owner,'blocker':None if certified else {'kind':'unreachable_authorized_cutover','owner_requests':None if owner is None else owner['requests']}}
