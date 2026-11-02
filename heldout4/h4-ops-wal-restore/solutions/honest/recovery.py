import copy, hashlib, json

def digest(events):
    return hashlib.sha256(json.dumps(events,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def restore(bundle, target):
    state=copy.deepcopy(bundle['snapshot']['rows'])
    base=bundle['snapshot']['sequence']
    if target < base: raise ValueError('target predates snapshot')
    grouped={}
    for shard,events in bundle['segments'].items():
        by_lsn={}
        for event in events:
            lsn=event['lsn']
            if lsn in by_lsn and by_lsn[lsn]!=event: raise ValueError('conflicting replay')
            by_lsn[lsn]=event
        ordered=[by_lsn[k] for k in sorted(by_lsn)]
        for event in ordered:
            grouped.setdefault(event['tx'],{}).setdefault(shard,[]).append(event)
    applied=[]
    seals={}
    for seal in bundle['commits']:
        seq=seal['sequence']
        if seq in seals and seals[seq]!=seal: raise ValueError('conflicting commit')
        seals[seq]=seal
    for seq in range(base+1,target+1):
        if seq not in seals: raise ValueError('missing commit')
        seal=seals[seq]; tx=seal['tx']; parts=grouped.get(tx,{})
        if set(parts)!=set(seal['parts']): raise ValueError('transaction coverage')
        operations=[]
        for shard,proof in seal['parts'].items():
            events=parts[shard]
            if [e['lsn'] for e in events]!=list(range(proof['first'],proof['last']+1)): raise ValueError('missing log range')
            if digest(events)!=proof['sha256']: raise ValueError('digest')
            operations.extend(events)
        operations.sort(key=lambda e:e['ordinal'])
        if [e['ordinal'] for e in operations]!=list(range(len(operations))): raise ValueError('ordinal coverage')
        pending=copy.deepcopy(state)
        for op in operations:
            key=op['key']
            if pending.get(key)!=op['before']: raise ValueError('precondition')
            if op['after'] is None: pending.pop(key,None)
            else: pending[key]=op['after']
        state=pending; applied.append(tx)
    return {'sequence':target,'rows':state,'transactions':applied}
