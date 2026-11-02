import json,sys

def assess(spec):
    nodes=sorted((n for n in spec['nodes'] if n['rack']!=spec['maintenance_rack']),key=lambda n:n['id'])
    pods=sorted(spec['pods'],key=lambda p:p['id'])
    used={n['id']:[0,0] for n in nodes}; by={}; groups=set(); best=[]
    def search(index):
        nonlocal best
        if len(by)+len(pods)-index<len(best): return
        if index==len(pods):
            candidate=sorted(by.items())
            if len(candidate)>len(best) or (len(candidate)==len(best) and candidate<best): best=candidate
            return
        pod=pods[index]
        for node in nodes:
            pair=(pod['service'],node['rack']); use=used[node['id']]
            if node['zone'] not in pod['zones'] or pair in groups: continue
            if use[0]+pod['cpu']>node['cpu']: continue
            use[0]+=pod['cpu'];use[1]+=pod['memory'];groups.add(pair);by[pod['id']]=node['id']
            search(index+1)
            del by[pod['id']];groups.remove(pair);use[0]-=pod['cpu'];use[1]-=pod['memory']
        search(index+1)
    search(0); chosen=dict(best)
    return {'feasible':len(best)==len(pods),'required':len(pods),'maximum_placed':len(best),'placement':chosen,'unplaced':[p['id'] for p in pods if p['id'] not in chosen],'maintenance_rack':spec['maintenance_rack']}

if __name__=='__main__':
    print(json.dumps(assess(json.load(open(sys.argv[1]))),sort_keys=True))
