import copy,hashlib,itertools,json,sys
from collections import deque
STATIC_ONLY=False
IGNORE_LINKS=False
COUNT_SHADOW_READY=False
IGNORE_ZONES=False
COUNT_UNITS=True
IGNORE_COPY_CAPACITY=False
FINAL_ONLY=False
REUSE_OLD_GRANTS=False

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'))
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def physical_size(data,unit):return 1 if COUNT_UNITS else data['units'][unit]['size']
def safe(data,pos,shadow=None):
 usage={r:0 for r in data['rack_capacity']};counts={g:0 for g in data['groups']};zones={g:set() for g in data['groups']}
 if len(set(pos.values()))!=len(pos):return False
 for unit,node in pos.items():
  u=data['units'][unit];n=data['nodes'][node]
  if physical_size(data,unit)>n['capacity']:return False
  usage[n['rack']]+=physical_size(data,unit);counts[u['group']]+=1;zones[u['group']].add(n['zone'])
 if shadow:
  unit,dest,phase=shadow;u=data['units'][unit];n=data['nodes'][dest]
  if dest in pos.values() or u['size']>n['capacity']:return False
  if not IGNORE_COPY_CAPACITY:usage[n['rack']]+=physical_size(data,unit)
  if COUNT_SHADOW_READY:counts[u['group']]+=1;zones[u['group']].add(n['zone'])
 return all(usage[r]<=v for r,v in data['rack_capacity'].items()) and all(counts[g]>=v['quorum'] and (IGNORE_ZONES or len(zones[g])>=v['min_zones']) for g,v in data['groups'].items())
def graph(data):
 latest={};seen={}
 for r in data['links']:
  key=(r['id'],r['revision'])
  if key in seen and seen[key]!=r:raise ValueError('conflicting link revision')
  seen[key]=r
  if r['id'] not in latest or r['revision']>latest[r['id']]['revision']:latest[r['id']]=r
 chosen=data['links'] if REUSE_OLD_GRANTS else latest.values()
 return {(r['source'],r['target']) for r in chosen if r['enabled'] and r['valid_from']<=data['at']<r['valid_to']}
def explore(data,edges):
 units=sorted(data['units']);initial=tuple(data['initial']['positions'][u] for u in units);images=tuple(data['initial']['images'][u] for u in units);start=(initial,images);paths={start:[]};queue=deque([start]);encoded=set();best=None
 def record(pos,ims,shadow):encoded.add(canonical([dict(zip(units,pos)),dict(zip(units,ims)),shadow]))
 while queue:
  positions,ims=queue.popleft();state=(positions,ims);pos=dict(zip(units,positions));record(positions,ims,None)
  if pos==data['target'] and all(x=='new' for x in ims) and all(node in data['units'][u]['allowed_final'] for u,node in pos.items()) and best is None:best=paths[state]
  for i,u in enumerate(units):
   for dest in sorted(data['nodes']):
    if FINAL_ONLY and dest not in data['units'][u]['allowed_final']:continue
    if dest in positions or (not IGNORE_LINKS and (positions[i],dest) not in edges):continue
    if not safe(data,pos,[u,dest,'copying']):continue
    # Ready acknowledgement changes no active voter until commit.
    record(positions,ims,[u,dest,'copying']);record(positions,ims,[u,dest,'ready'])
    newpos=dict(pos);newpos[u]=dest
    if not safe(data,newpos):continue
    p=list(positions);p[i]=dest;im=list(ims);im[i]='new';ns=(tuple(p),tuple(im))
    if ns not in paths:
     paths[ns]=paths[state]+[['start',u,dest],['ready',u,dest],['commit',u,dest]];queue.append(ns)
 return dict(reachable_count=len(encoded),reachable_sha256=digest(sorted(encoded)),plan=best,stable_count=len(paths))
def audit(data):
 d=copy.deepcopy(data);edges=graph(d)
 if not safe(d,d['initial']['positions']):raise ValueError('unsafe initial')
 static=safe(d,d['target']) and all(node in d['units'][u]['allowed_final'] for u,node in d['target'].items())
 result=explore(d,edges);feasible=static and result['plan'] is not None
 if STATIC_ONLY:feasible=static
 best=None;qs=sorted(d['owner_requests'],key=lambda q:q['id'])
 subsets=[]
 for bits in range(1<<len(qs)):
  chosen=[q for i,q in enumerate(qs) if bits>>i&1]
  subsets.append((sum(q['cost'] for q in chosen),[q['id'] for q in chosen],chosen))
 for cost,ids,chosen in sorted(subsets,key=lambda x:(x[0],x[1])):
  extra=set(edges)
  for q in chosen:extra.update(tuple(e) for e in q['edges'])
  r=result if not chosen else explore(d,extra)
  if static and r['plan'] is not None:
   best=dict(cost=cost,requests=ids,plan=r['plan']);break
 blocker=None if feasible else dict(kind='unreachable_authorized_cutover',owner_requests=None if best is None else best['requests'])
 return dict(static_final_valid=static,active_links=[list(e) for e in sorted(edges)],**result,certifiable=feasible,owner_plan=best,blocker=blocker)
if __name__=='__main__':print(json.dumps(audit(json.load(open(sys.argv[1]))),sort_keys=True))
