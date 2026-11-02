import copy,hashlib,itertools,json,random
from pathlib import Path
import pytest
from vault import audit
# Independent field multiplication via polynomial convolution and reduction.
def times(a,b):
    product=0
    for bit in range(8):
        if b>>bit&1:product^=a<<bit
    for bit in range(14,7,-1):
        if product>>bit&1:product^=0x11b<<(bit-8)
    return product

def binary_rank(matrix):
    # Expand each GF coefficient to its 8x8 binary linear map.
    rows=[]
    for row in matrix:
        for output in range(8):
            packed=0
            for col,c in enumerate(row):
                for bit in range(8):
                    if times(c,1<<bit)>>output&1:packed|=1<<(8*col+bit)
            rows.append(packed)
    basis={}
    for row in rows:
        while row:
            pivot=row.bit_length()-1
            if pivot in basis:row^=basis[pivot]
            else:basis[pivot]=row;break
    assert len(basis)%8==0
    return len(basis)//8

def seal(record):
    record['sha256']=hashlib.sha256(json.dumps({k:v for k,v in record.items() if k!='sha256'},sort_keys=True,separators=(',',':')).encode()).hexdigest()

def encode(coefficients,blocks):
    return bytes([__import__('functools').reduce(int.__xor__,[times(c,blocks[j][i]) for j,c in enumerate(coefficients)],0) for i in range(len(blocks[0]))]).hex()

def generated(seed,full=False):
    rng=random.Random(seed);n=4+seed%3;w=3;blocks=[bytes(rng.randrange(256) for _ in range(w)) for _ in range(n)]
    # Invertible triangular change of basis with nonbinary coefficients.
    base=[[rng.randrange(1,256) if j==i else (rng.randrange(256) if j>i else 0) for j in range(n)] for i in range(n)]
    rows=base if full else base[:-1]
    rows=rows+[ [a^b for a,b in zip(rows[0],rows[1])] ]
    s=dict(generation='g'+str(seed),tenant='t'+str(seed),at=20,width=n,block_bytes=w,allowed_regions=['local'],grants=[dict(id='access',generation='g'+str(seed),tenant='t'+str(seed),regions=['local'],start=10,expires=30)],fragments=[],requests=[])
    for i,row in enumerate(rows):
        f=dict(id='f'+str(i),generation=s['generation'],tenant=s['tenant'],region='local',grant='access',coefficients=row,payload=encode(row,blocks));seal(f);s['fragments'].append(f)
    s['requests']=[dict(id='r0',region='local',coefficients=base[-1],cost=6),dict(id='r1',region='local',coefficients=base[0],cost=1),dict(id='r2',region='remote',coefficients=base[-1],cost=1)]
    rng.shuffle(s['fragments']);return s,blocks

def check(spec,blocks):
    before=copy.deepcopy(spec);out=audit(spec);assert spec==before
    assert set(out)=={'generation','rank','complete','used_fragments','rejected','decoded','nullspace','remedy','blocker'}
    assert out['generation']==spec['generation']
    trusted={f['id']:f for f in spec['fragments']}
    assert out['used_fragments']==sorted(trusted) and out['rejected']=={}
    used=list(trusted.values())
    matrix=[f['coefficients'] for f in used];rank=binary_rank(matrix);n=spec['width']
    assert out['rank']==rank and out['complete']==(rank==n)
    assert len(out['nullspace'])==n-rank
    pivots=[j for j in range(n) if binary_rank([row[:j+1] for row in matrix])>binary_rank([row[:j] for row in matrix])]
    free=[j for j in range(n) if j not in pivots]
    for index,vector in enumerate(out['nullspace']):assert [vector[j] for j in free]==[int(i==index) for i in range(len(free))]
    assert binary_rank(out['nullspace'])==n-rank
    for vector in out['nullspace']:
        for row in matrix:assert __import__('functools').reduce(int.__xor__,[times(a,b) for a,b in zip(row,vector)],0)==0
    for i,value in enumerate(out['decoded']):
        known=all(v[i]==0 for v in out['nullspace'])
        assert value==(blocks[i].hex() if known else None)
    eligible=[q for q in spec['requests'] if q['region'] in spec['allowed_regions']];valid=[]
    for mask in range(1<<len(eligible)):
        qs=[q for i,q in enumerate(eligible) if mask>>i&1]
        if binary_rank(matrix+[q['coefficients'] for q in qs])==n:valid.append((sum(q['cost'] for q in qs),len(qs),sorted(q['id'] for q in qs)))
    best=min(valid) if valid else None
    assert out['remedy']==({'requests':best[2],'cost':best[0]} if best else None)
    assert out['blocker']==(None if rank==n else dict(kind='underdetermined',generation=spec['generation'],rank=rank,required=n,owner_requests=best[2] if best else []))
    return out

@pytest.mark.parametrize('seed',range(12))
def test_generated_rank_and_owner_counterfactual(seed):
    s,b=generated(seed,full=seed%3==0);out=check(s,b)
    if not out['complete']:
        for rid in out['remedy']['requests']:
            q=next(q for q in s['requests'] if q['id']==rid)
            f=dict(id='delivered-'+rid,generation=s['generation'],tenant=s['tenant'],region='local',grant='access',coefficients=q['coefficients'],payload=encode(q['coefficients'],b));seal(f);s['fragments'].append(f)
        assert check(s,b)['complete']

def test_fixture_generation_isolation_and_exact_report():
    s=json.loads(Path('data/input.json').read_text())
    assert audit(s)==json.loads(Path('/grader/expected_report.json').read_text())

def test_integrity_and_grant_boundary():
    s,b=generated(21,True);bad=s['fragments'][0];bad['payload']='000000'
    out=audit(s);assert out['rejected'][bad['id']]=='digest'
    s,b=generated(21,True);s['at']=30
    out=audit(s);assert out['rank']==0 and set(out['rejected'].values())=={'grant'}

def test_replays_conflicts_inconsistency_and_absence():
    s,b=generated(31);s['fragments'].append(copy.deepcopy(s['fragments'][0]));check(s,b)
    s['fragments'][-1]['payload']='ffffff'
    with pytest.raises(ValueError):audit(s)
    s,b=generated(31);f=copy.deepcopy(s['fragments'][0]);f['id']='different';f['payload']='ffffff';seal(f);s['fragments'].append(f)
    with pytest.raises(ValueError):audit(s)
    s,b=generated(31);s['fragments']=[];out=check(s,b);assert out['rank']==0

def test_all_filter_dimensions_and_unavailable_remedy():
    for field,value,reason in [('tenant','different','tenant'),('region','remote','region'),('generation','different','generation')]:
        s,b=generated(4,True)
        for f in s['fragments']:f[field]=value;seal(f)
        out=audit(s);assert out['rank']==0 and set(out['rejected'].values())=={reason}
    s,b=generated(4);s['requests']=[];out=check(s,b);assert out['remedy'] is None


def test_nonleading_and_interleaved_pivots():
    s,_=generated(0);s.update(width=4,block_bytes=1,fragments=[],requests=[]);blocks=[bytes([v]) for v in [5,7,11,9]]
    for i,row in enumerate([[0,2,0,0],[0,0,0,3]]):
        fragment=dict(id='nonleading-'+str(i),generation=s['generation'],tenant=s['tenant'],region='local',grant='access',coefficients=row,payload=encode(row,blocks));seal(fragment);s['fragments'].append(fragment)
    out=check(s,blocks)
    assert out['rank']==2 and out['decoded']==[None,'07',None,'09'] and out['nullspace']==[[1,0,0,0],[0,0,1,0]]
    assert [f['payload'] for f in s['fragments']]==['0e','1b']
    for seed in range(6):
        s,b=generated(seed+17);order=list(range(s['width']));random.Random(seed).shuffle(order)
        for fragment in s['fragments']:
            fragment['coefficients']=[fragment['coefficients'][i] for i in order];seal(fragment)
        for request in s['requests']:request['coefficients']=[request['coefficients'][i] for i in order]
        check(s,[b[i] for i in order])

def test_cli_json_contract(tmp_path):
    import subprocess,sys
    for seed,full in [(40,True),(41,False)]:
        s,b=generated(seed,full);want=check(s,b);source=tmp_path/('case-'+str(seed)+'.json');source.write_text(json.dumps(s))
        run=subprocess.run([sys.executable,'vault.py',str(source)],capture_output=True,text=True,timeout=30)
        assert run.returncode==0,run.stderr
        assert json.loads(run.stdout)==want
