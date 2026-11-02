import copy,hashlib,itertools,json,sys
from collections import deque
SKIP_READINESS=False
STATIC_IS_READY=False
IGNORE_SHADOW_RESOURCES=False

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'))
def solve(spec):
    nodes={n['id']:n for n in spec['nodes']};reps=sorted(spec['replicas'],key=lambda r:r['id']);by={r['id']:r for r in reps};ids=[r['id'] for r in reps]
    initial=(tuple((r['initial']['node'],r['initial']['image']) for r in reps),None)
    destinations={r['id']:sorted(n for n,node in nodes.items() if node['rack']!=spec['maintenance_rack'] and node['zone'] in r['zones']) for r in reps}
    def valid(state):
        active,shadow=state;copies=[]
        for rid,(node,image) in zip(ids,active):
            if node is not None:copies.append((rid,node,True,False))
        if shadow:copies.append((shadow[0],shadow[1],shadow[2],True))
        for node,n in nodes.items():
            cs=[by[r] for r,x,ready,sh in copies if x==node and not(IGNORE_SHADOW_RESOURCES and sh)]
            if sum(r['cpu'] for r in cs)>n['cpu'] or sum(r['memory'] for r in cs)>n['memory']:return False
        pairs=[(by[r]['service'],nodes[n]['rack']) for r,n,ready,sh in copies]
        if len(pairs)!=len(set(pairs)):return False
        if not SKIP_READINESS:
            for service,policy in spec['policy'].items():
                ready=[(r,n) for r,n,isready,sh in copies if isready and by[r]['service']==service]
                if len({r for r,n in ready})<policy['min_ready'] or len({nodes[n]['zone'] for r,n in ready})<policy['min_zones']:return False
        return True
    def goal(state):return state[1] is None and all(image=='new' and node in destinations[rid] for rid,(node,image) in zip(ids,state[0]))
    def encode(state):return canonical(dict(active=[[rid,node,image] for rid,(node,image) in zip(ids,state[0])],shadow=list(state[1]) if state[1] else None))
    q=deque([initial]);paths={initial:[]};goalpath=None
    while q:
        state=q.popleft();active,shadow=state;path=paths[state]
        if goal(state) and goalpath is None:goalpath=path
        candidates=[]
        if shadow:
            rid,node,ready=shadow;i=ids.index(rid)
            if not ready:candidates.append((('ready',rid,node),(active,(rid,node,True))))
            else:
                changed=list(active);changed[i]=(node,'new');candidates.append((('commit',rid,node),(tuple(changed),None)))
        else:
            for i,rid in enumerate(ids):
                for node in destinations[rid]:
                    if node!=active[i][0]:candidates.append((('start',rid,node),(active,(rid,node,False))))
        for i,rid in enumerate(ids):
            if active[i][0] is not None and (not shadow or shadow[0]!=rid):
                changed=list(active);changed[i]=(None,None);candidates.append((('stop',rid,active[i][0]),(tuple(changed),shadow)))
        for action,nxt in sorted(candidates):
            if nxt not in paths and valid(nxt):
                paths[nxt]=path+[dict(zip(('op','replica','node'),action))];q.append(nxt)
    static=None
    for places in itertools.product(*(destinations[rid] for rid in ids)):
        state=(tuple((node,'new') for node in places),None)
        if valid(state):static=[[rid,node] for rid,node in zip(ids,places)];break
    strings=sorted(encode(s) for s in paths);sha=hashlib.sha256(canonical(strings).encode()).hexdigest()
    if STATIC_IS_READY and static is not None and goalpath is None:goalpath=[]
    return dict(static_placement=static,reachable_count=len(paths),reachable_sha256=sha,plan=goalpath)

def assess(spec):
    original=solve(spec);requests=sorted(spec['requests'],key=lambda q:q['id']);choices=[]
    for bits in itertools.product((False,True),repeat=len(requests)):
        qs=[q for q,b in zip(requests,bits) if b];changed=copy.deepcopy(spec);by={n['id']:n for n in changed['nodes']}
        for request in qs:
            by[request['node']]['cpu']+=request['delta_cpu'];by[request['node']]['memory']+=request['delta_memory']
        result=original if not qs else solve(changed)
        if result['plan'] is not None:choices.append((sum(q['cost'] for q in qs),len(qs),[q['id'] for q in qs],result['plan']))
    best=min(choices,key=lambda x:x[:3]) if choices else None
    remedy=dict(requests=best[2],cost=best[0],plan=best[3]) if best else None
    blocker=None if original['plan'] is not None else dict(kind='transition_unreachable',reachable_count=original['reachable_count'],reachable_sha256=original['reachable_sha256'],owner_requests=remedy['requests'] if remedy else [])
    return dict(**original,remedy=remedy,blocker=blocker)
if __name__=='__main__':print(json.dumps(assess(json.load(open(sys.argv[1]))),sort_keys=True))
