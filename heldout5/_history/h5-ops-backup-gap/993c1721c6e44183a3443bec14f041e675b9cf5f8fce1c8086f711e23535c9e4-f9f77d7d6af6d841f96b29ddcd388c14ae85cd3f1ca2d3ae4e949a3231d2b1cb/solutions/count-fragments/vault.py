import json,sys,hashlib,itertools
from gf256 import mul,inv
IGNORE_GENERATION=False
COUNT_ROWS=True
TRUST_DIGEST=False

def reduce_rows(rows,n):
    rows=[r[:] for r in rows]; pivots=[];k=0
    for col in range(n):
        found=next((i for i in range(k,len(rows)) if rows[i][col]),None)
        if found is None:continue
        rows[k],rows[found]=rows[found],rows[k]
        factor=inv(rows[k][col]);rows[k]=[mul(x,factor) for x in rows[k]]
        for i in range(len(rows)):
            if i!=k and rows[i][col]:
                q=rows[i][col];rows[i]=[a^mul(q,b) for a,b in zip(rows[i],rows[k])]
        pivots.append(col);k+=1
    return rows,pivots

def audit(spec):
    n=spec['width'];w=spec['block_bytes'];records={};rejected={};selected=[]
    for f in spec['fragments']:
        if f['id'] in records and records[f['id']]!=f:raise ValueError('conflicting fragment ID')
        records[f['id']]=f
    grants={g['id']:g for g in spec['grants']}
    for fid,f in sorted(records.items()):
        g=grants.get(f['grant']);reason=None
        if not IGNORE_GENERATION and f['generation']!=spec['generation']:reason='generation'
        elif f['tenant']!=spec['tenant']:reason='tenant'
        elif f['region'] not in spec['allowed_regions']:reason='region'
        elif not g or g['tenant']!=spec['tenant'] or g['generation']!=f['generation'] or f['region'] not in g['regions'] or not(g['start']<=spec['at']<g['expires']):reason='grant'
        elif not TRUST_DIGEST and hashlib.sha256(json.dumps({k:v for k,v in f.items() if k!='sha256'},sort_keys=True,separators=(',',':')).encode()).hexdigest()!=f['sha256']:reason='digest'
        if reason:rejected[fid]=reason
        else:selected.append(f)
    matrix=[f['coefficients']+list(bytes.fromhex(f['payload'])) for f in selected]
    reduced,pivots=reduce_rows(matrix,n)
    if any(not any(row[:n]) and any(row[n:]) for row in reduced):raise ValueError('inconsistent fragments')
    rank=len(pivots);free=[i for i in range(n) if i not in pivots]
    nullspace=[]
    for col in free:
        v=[0]*n;v[col]=1
        for j,pivot in enumerate(pivots):v[pivot]=reduced[j][col]
        nullspace.append(v)
    decoded=[None]*n
    for j,pivot in enumerate(pivots):
        if all(reduced[j][f]==0 for f in free):decoded[pivot]=bytes(reduced[j][n:]).hex()
    requests=sorted((q for q in spec['requests'] if q['region'] in spec['allowed_regions']),key=lambda q:q['id'])
    choices=[]
    for bits in itertools.product((0,1),repeat=len(requests)):
        subset=[q for q,b in zip(requests,bits) if b]
        _,ps=reduce_rows([f['coefficients'] for f in selected]+[q['coefficients'] for q in subset],n)
        if len(ps)==n:choices.append((sum(q['cost'] for q in subset),len(subset),[q['id'] for q in subset]))
    best=min(choices) if choices else None
    remedy={'requests':best[2],'cost':best[0]} if best else None
    if COUNT_ROWS:rank=min(n,len(selected))
    complete=rank==n
    blocker=None if complete else dict(kind='underdetermined',generation=spec['generation'],rank=rank,required=n,owner_requests=remedy['requests'] if remedy else [])
    return dict(generation=spec['generation'],rank=rank,complete=complete,used_fragments=sorted(f['id'] for f in selected),rejected=rejected,decoded=decoded,nullspace=nullspace,remedy=remedy,blocker=blocker)

if __name__=='__main__':print(json.dumps(audit(json.load(open(sys.argv[1]))),sort_keys=True))
