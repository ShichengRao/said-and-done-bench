import copy,fnmatch,itertools,json,sys
IGNORE_CAPACITY=True
GREEDY=False
LAST_RECORD=False

def selected(records,at):
    seen={};result={}
    for record in records:
        key=(record['id'],record['revision'])
        if key in seen and seen[key]!=record:raise ValueError('conflicting revision')
        seen[key]=record
        if record['recorded_at']<=at and (record['id'] not in result or LAST_RECORD or record['revision']>result[record['id']]['revision']):result[record['id']]=record
    return result

def graph(spec):
    grants=selected(spec['grants'],spec['as_of']);receipts=selected(spec['receipts'],spec['as_of']);edges={}
    for d in spec['deployments']:
        allowed=[]
        for rid,r in receipts.items():
            g=grants.get(r['grant'])
            active=lambda t:g['start']<=t<g['expires'] and (g['revoked_at'] is None or t<g['revoked_at'])
            if r['principal']==d['principal'] or not any(fnmatch.fnmatchcase(d['service'],p) for p in r['services']) or d['region'] not in r['regions'] or d['artifact'] not in r['artifacts'] or not r['start']<=d['commit']<r['expires']:continue
            if not g or g['role']!='approve' or g['principal']!=r['principal'] or not any(fnmatch.fnmatchcase(d['service'],p) for p in g['services']) or d['region'] not in g['regions'] or not active(r['start']) or not active(d['commit']):continue
            allowed.append(rid)
        edges[d['id']]=sorted(allowed)
    return edges,{rid:(len(edges) if IGNORE_CAPACITY else r['capacity']) for rid,r in receipts.items()}

def size(ids,edges,capacity):
    slots=[(r,i) for r in sorted(capacity) for i in range(capacity[r])];owner={}
    def augment(d,seen):
        for slot in slots:
            if slot[0] not in edges[d] or slot in seen:continue
            seen.add(slot)
            if slot not in owner or augment(owner[slot],seen):owner[slot]=d;return True
        return False
    for d in ids:augment(d,set())
    return len(owner)

def matching(ids,edges,capacity):
    ids=sorted(ids);left=capacity.copy();result=[]
    if GREEDY:
        for d in ids:
            for r in edges[d]:
                if left[r]:result.append([d,r]);left[r]-=1;break
        return result
    count=size(ids,edges,left)
    while count:
        found=False
        for index,d in enumerate(ids):
            for r in edges[d]:
                if not left[r]:continue
                remaining=left.copy();remaining[r]-=1
                if size(ids[index+1:],edges,remaining)>=count-1:
                    result.append([d,r]);left=remaining;ids=ids[index+1:];count-=1;found=True;break
            if found:break
    return result

def audit(spec):
    edges,capacity=graph(spec);ids=sorted(edges);assignment=matching(ids,edges,capacity);maximum=len(assignment);deficiency=None
    if maximum<len(ids):
        for n in range(1,len(ids)+1):
            for subset in itertools.combinations(ids,n):
                neighbors=sorted({r for d in subset for r in edges[d]});cap=sum(capacity[r] for r in neighbors)
                if n>cap:deficiency=dict(deployments=list(subset),receipts=neighbors,demand=n,capacity=cap,deficit=n-cap);break
            if deficiency:break
    proposals=sorted(spec['amendments'],key=lambda p:p['id']);choices=[]
    for mask in range(1<<len(proposals)):
        qs=[q for i,q in enumerate(proposals) if mask>>i&1];excluded=sorted({d for q in qs for d in q['exclude']});remaining=[d for d in ids if d not in excluded];witness=matching(remaining,edges,capacity)
        if len(witness)==len(remaining):choices.append((sum(q['cost'] for q in qs),len(qs),[q['id'] for q in qs],excluded,witness))
    best=min(choices) if choices else None
    remedy=dict(requests=best[2],cost=best[0],excluded=best[3],assignment=best[4]) if best else None
    blocker=None if maximum==len(ids) else dict(kind='approval_capacity',deployments=deficiency['deployments'] if deficiency else [],demand=deficiency['demand'] if deficiency else len(ids),capacity=deficiency['capacity'] if deficiency else maximum,owner_requests=remedy['requests'] if remedy else [])
    return dict(eligible=edges,maximum=maximum,required=len(ids),assignment=assignment,certifiable=maximum==len(ids),deficiency=deficiency,remedy=remedy,blocker=blocker)
if __name__=='__main__':print(json.dumps(audit(json.load(open(sys.argv[1]))),sort_keys=True))
