from itertools import combinations,product
from copy import deepcopy

def transform(bundle):
    p=bundle['placement'];nodes={n['id']:n for n in p['nodes']};templates={t['id']:t['nodes'] for t in p['templates']};datasets=sorted(p['datasets'],key=lambda d:d['id']);scenarios=sorted(p['scenarios'],key=lambda s:s['id'])
    if len(nodes)!=len(p['nodes']) or len(templates)!=len(p['templates']) or len({d['id'] for d in datasets})!=len(datasets):raise ValueError('duplicate identity')
    if any(t not in templates for d in datasets for t in d['templates']):raise ValueError('unknown template')
    eligible={d['id']:sorted(t for t in set(d['templates']) if all(nodes[n]['region'] in d['regions'] and d['key'] in nodes[n]['keys'] for n in templates[t])) for d in datasets}
    def solve(ds,ss,props=()):
        limits={s['id']:dict(s['capacity']) for s in ss}
        for prop in props:
            if prop['scenario'] in limits:limits[prop['scenario']][prop['node']]+=prop['units']
        usage={s['id']:{n:0 for n in nodes} for s in ss};answer={}
        def visit(i):
            if i==len(ds):return dict(answer)
            d=ds[i]
            for t in eligible[d['id']]:
                active={s['id']:[n for n in templates[t] if n not in s['down']] for s in ss}
                if any(len(active[s['id']])<d['survivors'] for s in ss):continue
                if any(usage[s['id']][n]+d['units']>limits[s['id']][n] for s in ss for n in active[s['id']]):continue
                for s in ss:
                    for n in active[s['id']]:usage[s['id']][n]+=d['units']
                answer[d['id']]=t;result=visit(i+1)
                if result is not None:return result
                for s in ss:
                    for n in active[s['id']]:usage[s['id']][n]-=d['units']
                answer.pop(d['id'])
            return None
        return visit(0)
    local={}
    for d in datasets:
        local[d['id']]=[t for t in eligible[d['id']] if all(sum(n not in s['down'] for n in templates[t])>=d['survivors'] and all(d['units']<=s['capacity'][n] for n in templates[t] if n not in s['down']) for s in scenarios)]
    witnesses={s['id']:solve(datasets,[s]) for s in scenarios};assignment=solve(datasets,scenarios)
    cores=[]
    if assignment is None:
        for nd in range(1,len(datasets)+1):
            for ns in range(1,len(scenarios)+1):
                for ds in combinations(datasets,nd):
                    for ss in combinations(scenarios,ns):
                        if solve(ds,ss) is None:
                            dn=[d['id'] for d in ds];sn=[s['id'] for s in ss];cores.append(((nd+ns,nd,dn,sn),{'datasets':dn,'scenarios':sn}))
    obstruction=min(cores,key=lambda x:x[0])[1] if cores else None
    props=sorted(bundle['proposals'],key=lambda x:x['id']);requests=[]
    for n in range(len(props)+1):
        for chosen in combinations(props,n):
            witness=solve(datasets,scenarios,chosen)
            if witness is not None:
                ids=[q['id'] for q in chosen];cost=sum(q['cost'] for q in chosen);requests.append(((cost,len(ids),ids),{'proposal_ids':ids,'cost':cost,'assignment':witness}))
    return {'ready':assignment is not None,'eligible_templates':eligible,'robust_options':local,'scenario_witnesses':witnesses,'assignment':assignment,'obstruction':obstruction,'owner_request':min(requests,key=lambda x:x[0])[1] if requests else None,'blocker_codes':[] if assignment is not None else ['robust_placement_authority_required']}

import argparse,json,os,tempfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',default='data');p.add_argument('--output',default='output/report.json');a=p.parse_args()
    bundle={f.stem:json.loads(f.read_text()) for f in sorted(Path(a.input).glob('*.json'))}
    report=transform(bundle)
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=target.parent)
    try:
        with os.fdopen(fd,'w') as stream:json.dump(report,stream,sort_keys=True,indent=2);stream.write('\n')
        os.replace(name,target)
    finally:
        if os.path.exists(name):os.unlink(name)
if __name__=='__main__':main()
