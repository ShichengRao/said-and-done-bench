"""Temporal funding allocation and hypothetical owner review."""
from copy import deepcopy
from itertools import combinations

def _latest(rows, cutoff):
    seen, winners = {}, {}
    for row in rows:
        if row['known'] > cutoff:
            continue
        key = row['id'], row['revision']
        if key in seen and seen[key] != row:
            raise ValueError('conflicting delivery')
        seen[key] = row
        if row['id'] not in winners or row['revision'] > winners[row['id']]['revision']:
            winners[row['id']] = row
    return list(winners.values())

def _solve(bundle, selected=()):
    facilities = {x['id']: deepcopy(x) for x in bundle['facilities']}
    groups = dict(bundle['groups'])
    grants = []
    for proposal in selected:
        for fid, delta in proposal['facility_delta'].items():
            facilities[fid]['limit'] += delta
        for gid, delta in proposal['group_delta'].items():
            groups[gid] += delta
        grants += proposal['grants']
    obligations = sorted(bundle['obligations'], key=lambda x:x['id'])
    holds = [x for x in _latest(bundle['holds'], bundle['as_of']) if not x['void']]
    approvals = [x for x in _latest(bundle['approvals'], bundle['as_of']) if not x['revoked']]
    days = sorted({d for o in obligations for d in (o['pay_day'],o['repaid_day'])} | {d for h in holds for d in (h['from_day'],h['until_day'])})
    used = {fid:[sum(h['cents'] for h in holds if h['facility']==fid and h['from_day']<=day<h['until_day']) for day in days] for fid in facilities}
    gused = {gid:[sum(used[fid][i] for fid,f in facilities.items() if f['group']==gid) for i in range(len(days))] for gid in groups}
    choices = []
    for o in obligations:
        ids=[]
        for fid,f in sorted(facilities.items()):
            if f['currency']!=o['currency'] or o['beneficiary'] not in f['beneficiaries']:
                continue
            permitted = any(a['facility']==fid and a['obligation']==o['id'] and a['cap']>=o['cents'] and a['from_day']<=o['pay_day']<a['until_day'] for a in approvals)
            permitted |= any(g['facility']==fid and g['obligation']==o['id'] and g['cap']>=o['cents'] for g in grants)
            if permitted:ids.append(fid)
        choices.append(ids)
    best=None; best_vector=None
    def visit(index,total,count,vector):
        nonlocal best,best_vector
        if index==len(obligations):
            key=(-total,-count,tuple(vector))
            if best is None or key<best:best,best_vector=key,list(vector)
            return
        o=obligations[index]
        active=[i for i,d in enumerate(days) if o['pay_day']<=d<o['repaid_day']]
        for fid in choices[index]:
            gid=facilities[fid]['group'];n=o['cents']
            if any(used[fid][i]+n>facilities[fid]['limit'] for i in active):continue
            for i in active:used[fid][i]+=n;gused[gid][i]+=n
            visit(index+1,total+n,count+1,vector+[fid])
            for i in active:used[fid][i]-=n;gused[gid][i]-=n
        visit(index+1,total,count,vector+['~'])
    visit(0,0,0,[])
    schedule=[];unfunded=[]
    for o,fid in zip(obligations,best_vector):
        if fid=='~':unfunded.append(o['id']);continue
        schedule.append({'obligation':o['id'],'facility':fid})
        gid=facilities[fid]['group']
        for i,day in enumerate(days):
            if o['pay_day']<=day<o['repaid_day']:
                used[fid][i]+=o['cents'];gused[gid][i]+=o['cents']
    return {'funded_cents':-best[0],'schedule':schedule,'unfunded':unfunded,
            'usage':{'days':days,'facilities':{fid:used[fid] for fid in sorted(used)},'groups':{gid:gused[gid] for gid in sorted(gused)}}}

def analyze(bundle):
    current=_solve(bundle)
    requested=sum(o['cents'] for o in bundle['obligations'])
    repairs=[]
    proposals=sorted(bundle['proposals'],key=lambda x:x['id'])
    for size in range(len(proposals)+1):
        for selected in combinations(proposals,size):
            trial=_solve(bundle,selected)
            if trial['funded_cents']==requested:
                ids=[p['id'] for p in selected];cost=sum(p['cost'] for p in selected)
                repairs.append(((cost,size,ids),{'cost':cost,'proposals':ids,'schedule':trial['schedule']}))
    repair=min(repairs,key=lambda x:x[0])[1] if repairs else None
    return {'requested_cents':requested,'complete':not current['unfunded'],**current,'owner_review':repair}

if __name__=='__main__':
    import json,sys
    print(json.dumps(analyze(json.load(open(sys.argv[1]))),sort_keys=True))
