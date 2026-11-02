import copy,json
from pathlib import Path
from vault import audit

def test_real_restore_route_and_owner_input():
    spec=json.loads(Path('data/input.json').read_text()); old=copy.deepcopy(spec)
    assert audit(spec)==json.loads(Path('/grader/expected_report.json').read_text())
    assert spec==old

def test_owner_key_makes_target_available():
    spec=json.loads(Path('data/input.json').read_text())
    spec['key_inventory'].append({'id':'key-legacy','tenant':'vale-retail','restore_allowed':True})
    out=audit(spec)
    assert out['complete'] and out['recoverable_through']==128
    assert out['available_path']==['full-100','inc-108','inc-116','inc-128'] and out['missing_keys']==[]

def test_gap_is_not_a_chain():
    spec=json.loads(Path('data/input.json').read_text());spec['catalog']=[r for r in spec['catalog'] if r['id']!='inc-128']
    out=audit(spec)
    assert out['recovery_path']==[] and not out['complete']

def test_order_independence():
    spec=json.loads(Path('data/input.json').read_text());spec['catalog'].reverse();spec['key_inventory'].reverse()
    assert audit(spec)==json.loads(Path('/grader/expected_report.json').read_text())


def test_generated_vault_graphs():
    import random,hashlib
    rng=random.Random(328)
    for case in range(18):
        spec=dict(tenant='tenant',timeline='live',target=24,allowed_regions=['east'],key_inventory=[dict(id='k0',tenant='tenant',restore_allowed=True),dict(id='k1',tenant='foreign',restore_allowed=True)],objects={},catalog=[])
        for i in range(10):
            parent=rng.choice(spec['catalog']) if i>1 else None
            start=(parent['end']+rng.choice([1,1,2])) if parent else rng.choice([5,10])
            end=start+rng.randint(0,4) if parent else start
            rid='b'+str(i);raw='object-'+str(case)+'-'+rid;spec['objects'][rid]=raw
            record=dict(id=rid,parent=parent['id'] if parent else None,start=start,end=end,key=rng.choice(['k0','k0','k1']),region=rng.choice(['east','east','west']),timeline='live',tenant='tenant',object=rid,sha256=hashlib.sha256(raw.encode()).hexdigest())
            if rng.random()<.12:record['sha256']='0'*64
            spec['catalog'].append(record)
        index={r['id']:r for r in spec['catalog']}; paths=[]
        for leaf in spec['catalog']:
            current=leaf; chain=[];seen=set();okay=True
            while current:
                if current['id'] in seen:okay=False;break
                seen.add(current['id']);chain.append(current)
                if current['region']!='east' or current['end']>24 or current['start']>current['end'] or current['sha256']!=hashlib.sha256(spec['objects'][current['object']].encode()).hexdigest():okay=False;break
                parent=index.get(current['parent'])
                if current['parent'] is None:
                    if current['start']!=current['end']:okay=False
                    break
                if not parent or current['start']!=parent['end']+1:okay=False;break
                current=parent
            if okay:
                ids=[r['id'] for r in chain[::-1]]; missing={r['key'] for r in chain if r['key']!='k0'};paths.append((leaf['end'],ids,missing))
        available=[p for p in paths if not p[2]];best=min(available,key=lambda p:(-p[0],len(p[1]),p[1])) if available else None
        routes=[p for p in paths if p[0]==24];route=min(routes,key=lambda p:(len(p[2]),len(p[1]),p[1])) if routes else None
        expected={'target':24,'complete':bool(best and best[0]==24),'recoverable_through':best[0] if best else None,'available_path':best[1] if best else [],'recovery_path':route[1] if route else [],'missing_keys':sorted(route[2]) if route else []}
        rng.shuffle(spec['catalog'])
        assert audit(spec)==expected
