import copy,hashlib,itertools,json,sys
from crypto import canonical,verify_signature
INDEPENDENT_ONLY=True
IGNORE_REALTIME=False
IGNORE_FAILED=False
LATEST_ARRIVAL=False

def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def latest(rows,key):
 out={};seen={}
 for r in rows:
  b=r[key] if key else r;k=(b['id'],b['revision'])
  if k in seen and seen[k]!=r:raise ValueError('revision conflict')
  seen[k]=r
  if b['id'] not in out or LATEST_ARRIVAL or b['revision']>(out[b['id']][key] if key else out[b['id']])['revision']:out[b['id']]=r
 return out

def history(ops,initial):
 names=sorted(ops);resources=sorted(initial);pre={k:{j for j in names if j!=k and ops[j]['respond']<=ops[k]['invoke']} for k in names};start=(frozenset(),tuple(initial[k] for k in resources));paths={start:()};queue=[start]
 for state in queue:
  done,values=state;current=dict(zip(resources,values))
  for k in names:
   if k in done or (not IGNORE_REALTIME and not pre[k]<=done):continue
   op=ops[k];success=all(current[r]==v for r,v in op['expected'].items())
   if not IGNORE_FAILED and success!=op['success']:continue
   if IGNORE_FAILED and op['success'] and not success:continue
   nxt=dict(current)
   if op['success']:nxt.update(op['writes'])
   ns=(done|{k},tuple(nxt[r] for r in resources));path=paths[state]+(k,)
   if ns not in paths:paths[ns]=path;queue.append(ns)
   elif path<paths[ns]:paths[ns]=path
 full=sorted(p for (done,v),p in paths.items() if len(done)==len(names));maximum=max(len(p) for p in paths.values());prefix=min(p for p in paths.values() if len(p)==maximum)
 encoded=sorted(json.dumps([sorted(done),dict(zip(resources,values))],sort_keys=True,separators=(',',':')) for done,values in paths)
 return dict(legal=bool(full),history=list(full[0]) if full else None,max_prefix=list(prefix),reachable_count=len(paths),reachable_sha256=digest(encoded))

def audit(data):
 d=copy.deepcopy(data);grants=latest(d['grants'],None);ops=latest(d['operations'],'signed');valid={};invalid=[]
 for name in sorted(d['scope']):
  e=ops.get(name)
  if e is None:invalid.append({'id':name,'reason':'missing'});continue
  b=e['signed'];resources=set(b['expected'])|set(b['writes']);eligible=[g for g in grants.values() if g['principal']==b['principal'] and not g['revoked'] and g['valid_from']<=b['invoke'] and b['respond']<=g['valid_to'] and resources<=set(g['resources'])]
  if not eligible:invalid.append({'id':name,'reason':'grant'});continue
  keys={g['keyid'] for g in eligible}
  if not any(sig['keyid'] in keys and sig['keyid'] in d['keys'] and verify_signature(b,sig,d['keys'][sig['keyid']]) for sig in e['signatures']):invalid.append({'id':name,'reason':'signature'});continue
  valid[name]=b
 bad={r['id'] for r in invalid}
 def evaluate(scope):
  if bad&set(scope):return None
  return history({k:valid[k] for k in scope},d['initial'])
 full=evaluate(d['scope']);legal=full is not None and full['legal'];projections={}
 for r in sorted(d['initial']):
  projected={k:{**v,'expected':{r:v['expected'][r]} if r in v['expected'] else {},'writes':{r:v['writes'][r]} if r in v['writes'] else {}} for k,v in valid.items() if r in v['expected'] or r in v['writes']}
  projections[r]=history(projected,{r:d['initial'][r]})['legal']
 if INDEPENDENT_ONLY:legal=not bad and all(projections.values())
 core=[]
 if not legal:
  for n in range(1,len(d['scope'])+1):
   found=False
   for subset in itertools.combinations(sorted(d['scope']),n):
    result=evaluate(subset)
    if result is None or not result['legal']:core=list(subset);found=True;break
   if found:break
 best=None;requests=sorted(d['owner_requests'],key=lambda q:q['id'])
 for bits in range(1<<len(requests)):
  chosen=[q for i,q in enumerate(requests) if bits>>i&1];withdraw=set().union(*(set(q['withdraw']) for q in chosen));scope=sorted(set(d['scope'])-withdraw);result=evaluate(scope)
  if result is None or not result['legal']:continue
  candidate={'cost':sum(q['cost'] for q in chosen),'requests':[q['id'] for q in chosen],'remaining_scope':scope,'history':result['history']}
  if best is None or (candidate['cost'],candidate['requests'])<(best['cost'],best['requests']):best=candidate
 blocker=None if legal else {'kind':'inconsistent_authorization_history' if not bad else 'unauthenticated_history','core':core,'owner_requests':None if best is None else best['requests']}
 return dict(authenticated=sorted(valid),invalid=invalid,projections=projections,history=full,certifiable=legal,minimal_core=core,owner_plan=best,blocker=blocker)
if __name__=='__main__':print(json.dumps(audit(json.load(open(sys.argv[1]))),sort_keys=True))
