"""Joint persistent cash/collateral planning over signed exposure routes."""
import itertools,json,sys

def _routes(bundle):
    seen={};selected={}
    for r in bundle['routes']:
        if r['known']>bundle['as_of']:continue
        key=r['id'],r['revision']
        if key in seen and seen[key]!=r:raise ValueError('conflicting visible route')
        seen[key]=r
        if (r['id'] not in selected or r['revision']>selected[r['id']]['revision']):selected[r['id']]=r
    return [r for r in selected.values() if not r['void']]

def _validate(routes,obligations):
    needs={o['id']:o for o in obligations}
    for r in routes:
        o=needs[r['obligation']];windows=sorted(r['windows'],key=lambda w:w['from_day'])
        if r['pledge_cents']<o['cents'] or not windows:raise ValueError('insufficient pledge')
        cursor=o['pay_day']
        for w in windows:
            if w['from_day']!=cursor or w['until_day']<=w['from_day']:raise ValueError('nonpartitioned collateral coverage')
            cursor=w['until_day']
        if cursor!=o['repaid_day']:raise ValueError('incomplete collateral coverage')

def _solve(obligations,routes,facility_caps,pool_caps):
    obligations=sorted(obligations,key=lambda o:o['id']);_validate(routes,obligations)
    days=sorted({d for o in obligations for d in (o['pay_day'],o['repaid_day'])}|{d for r in routes for w in r['windows'] for d in (w['from_day'],w['until_day'])})
    dimensions=[('f',i,d) for i in sorted(facility_caps) for d in days]+[('p',i,d) for i in sorted(pool_caps) for d in days]
    cap=[(facility_caps if kind=='f' else pool_caps)[identity] for kind,identity,d in dimensions]
    options={o['id']:sorted([r for r in routes if r['obligation']==o['id']],key=lambda r:r['id']) for o in obligations}
    vectors={}
    for o in obligations:
        for r in options[o['id']]:
            vectors[r['id']]=[o['cents'] if kind=='f' and identity==r['facility'] and o['pay_day']<=d<o['repaid_day'] else
                sum(r['pledge_cents'] for w in r['windows'] if kind=='p' and identity==w['pool'] and w['from_day']<=d<w['until_day']) for kind,identity,d in dimensions]
    best=None;chosen=None
    def search(index,used,assignment,value,count):
        nonlocal best,chosen
        if index==len(obligations):
            key=(-value,-count,tuple(r['id'] if r else '~' for r in assignment))
            if best is None or key<best:best=key;chosen=(list(assignment),list(used))
            return
        o=obligations[index]
        for r in options[o['id']]:
            after=[a+b for a,b in zip(used,vectors[r['id']])]
            if all(a<=b for a,b in zip(after,cap)):search(index+1,after,assignment+[r],value+o['cents'],count+1)
        search(index+1,used,assignment+[None],value,count)
    search(0,[0]*len(dimensions),[],0,0)
    selected,used=chosen;assignment=[dict(obligation=o['id'],route=r['id'],facility=r['facility']) for o,r in zip(obligations,selected) if r]
    usage=dict(days=days,facilities={i:[] for i in sorted(facility_caps)},collateral={i:[] for i in sorted(pool_caps)})
    for (kind,i,d),value in zip(dimensions,used):usage['facilities' if kind=='f' else 'collateral'][i].append(value)
    return dict(funded_cents=-best[0],assignment=assignment,unfunded=[o['id'] for o,r in zip(obligations,selected) if not r],usage=usage)

def analyze(bundle):
    obligations=bundle['obligations'];routes=_routes(bundle);facilities={r['id']:r['cap'] for r in bundle['facilities']};pools={r['id']:r['cap'] for r in bundle['collateral']}
    current=_solve(obligations,routes,facilities,pools);requested=sum(o['cents'] for o in obligations)
    owner=None;proposals=sorted(bundle['proposals'],key=lambda p:p['id'])
    subsets=[tuple(proposals[i] for i in range(len(proposals)) if mask>>i&1) for mask in range(1<<len(proposals))]
    subsets.sort(key=lambda ps:(sum(p['cost'] for p in ps),len(ps),[p['id'] for p in ps]))
    for selected in subsets:
        fs=facilities.copy();cs=pools.copy();rs=list(routes)
        for p in selected:
            for i,v in p['facility_delta'].items():fs[i]+=v
            for i,v in p['collateral_delta'].items():cs[i]+=v
            rs.extend(p['routes'])
        result=_solve(obligations,rs,fs,cs)
        if not result['unfunded']:
            owner=dict(cost=sum(p['cost'] for p in selected),proposals=[p['id'] for p in selected],assignment=result['assignment']);break
    return dict(requested_cents=requested,funded_cents=current['funded_cents'],complete=not current['unfunded'],
                eligible_routes={o['id']:sorted(r['id'] for r in routes if r['obligation']==o['id']) for o in sorted(obligations,key=lambda o:o['id'])},
                assignment=current['assignment'],unfunded=current['unfunded'],usage=current['usage'],owner_review=owner)

if __name__=='__main__':
    print(json.dumps(analyze(json.load(open(sys.argv[1]))),sort_keys=True))
