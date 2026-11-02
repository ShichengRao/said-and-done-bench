import hashlib,json,sys

def audit(spec):
    records={r['id']:r for r in spec['catalog']}; target=spec['target']; valid={}
    usable_keys={k['id'] for k in spec['key_inventory'] if k['tenant']==spec['tenant'] and k['restore_allowed']}
    for rid,r in records.items():
        payload=spec['objects'].get(r['object'])
        if r['tenant']!=spec['tenant'] or r['region'] not in spec['allowed_regions'] or r['timeline']!=spec['timeline']: continue
        if payload is None or hashlib.sha256(payload.encode()).hexdigest()!=r['sha256']: continue
        if r['end']>target or r['start']>r['end']: continue
        if r['parent'] is None and r['start']!=r['end']: continue
        valid[rid]=r
    paths=[]
    def extend(rid,path,missing):
        r=valid[rid]; path=path+[rid]; missing=missing|({r['key']} if r['key'] not in usable_keys else set())
        paths.append((r['end'],path,missing))
        for child,c in sorted(valid.items()):
            if child not in path and c['parent']==rid and c['start']==r['end']+1:
                extend(child,path,missing)
    for rid,r in sorted(valid.items()):
        if r['parent'] is None: extend(rid,[],set())
    available=[p for p in paths if not p[2]]
    best=min(available,key=lambda p:(-p[0],len(p[1]),p[1])) if available else None
    routes=[p for p in paths if p[0]==target]
    route=min(routes,key=lambda p:(len(p[2]),len(p[1]),p[1])) if routes else None
    return {'target':target,'complete':best is not None and best[0]==target,'recoverable_through':best[0] if best else None,'available_path':best[1] if best else [],'recovery_path':route[1] if route else [],'missing_keys':sorted(route[2]) if route else []}

if __name__=='__main__': print(json.dumps(audit(json.load(open(sys.argv[1]))),sort_keys=True))
