import copy,hashlib,itertools,json,random,subprocess,sys
from pathlib import Path
import pytest
import vault as v

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':')).encode()
def sha(x):return hashlib.sha256(canonical(x)).hexdigest()
def mul(a,b):
 # Independent polynomial convolution and reduction.
 z=0
 for i in range(8):
  if b>>i&1:z^=a<<i
 for i in range(14,7,-1):
  if z>>i&1:z^=0x11b<<(i-8)
 return z
def dot(c,x):
 out=0
 for a,b in zip(c,x):out^=mul(a,b)
 return out
def fragment(i,c,x):return dict(id=i,revision=1,tenant='blue',generation='g7',live=True,coefficients=c,value=x,sha256=sha(dict(coefficients=c,value=x)))
def production():return json.loads((Path(__file__).parent/'original/data/input.json').read_text())
def candidates(d):
 return [x for x in itertools.product(range(256),repeat=d['width']) if sum(dot(r['coefficients'],x)!=r['value'] for r in d['fragments'])<=d['fault_budget'] and all(dot(a['coefficients'],x)==a['value'] for a in d['anchors'])]
def verify_encoding(out,xs):
 enc=sorted(bytes(x).hex() for x in xs);assert out['candidate_count']==len(xs) and out['candidate_sha256']==sha(enc) and out['witnesses']==enc[:2]

def test_canonical_independent_exhaustion_and_query_minimum():
 d=production();out=v.audit(d);xs=[]
 # Repeated x equations force xA=10,xB=30 under the total two-fault budget.
 for y,z in itertools.product(range(256),repeat=2):
  x=(10,y,30,z)
  if sum(dot(r['coefficients'],x)!=r['value'] for r in d['fragments'])<=2:xs.append(x)
 verify_encoding(out,xs);assert len(xs)==4 and out['unique_symbols']==[10,None,30,None] and not out['certifiable']
 options=[]
 for n in range(5):
  for qs in itertools.combinations(d['owner_queries'],n):
   if len({tuple(dot(q['coefficients'],x) for q in qs) for x in xs})==4:options.append((sum(q['cost'] for q in qs),sorted(q['id'] for q in qs)))
 best=min(options);assert out['owner_plan']==dict(cost=best[0],queries=best[1]);assert out['blocker']==dict(kind='ambiguous_restore',candidate_count=4,owner_queries=best[1])

def test_actual_owner_responses_make_same_contract_feasible():
 d=production();d['anchors']=[dict(coefficients=[0,1,0,0],value=20),dict(coefficients=[0,0,0,1],value=41)]
 x=v.audit(d);verify_encoding(x,[(10,20,30,41)]);assert x['certifiable'] and x['blocker'] is None and x['owner_plan']==dict(cost=0,queries=[])

def test_single_parity_read_is_insufficient():
 d=production();d['owner_queries']=d['owner_queries'][:1];x=v.audit(d);assert x['owner_plan'] is None and x['blocker']['owner_queries'] is None

def test_zero_budget_inconsistent_and_rank_deficient_enumeration():
 d=dict(width=1,tenant='blue',generation='g7',fault_budget=0,fragments=[fragment('a',[1],3),fragment('b',[1],4)],anchors=[],owner_queries=[])
 x=v.audit(d);verify_encoding(x,[]);assert x['blocker']['kind']=='inconsistent_evidence'
 d['fault_budget']=1;x=v.audit(d);verify_encoding(x,[(3,),(4,)])
 d['fragments']=[];d['fault_budget']=0;x=v.audit(d);verify_encoding(x,[(i,) for i in range(256)])

def test_generated_candidates_by_direct_plaintext_enumeration():
 rng=random.Random(615)
 for n in range(5):
  truth=(rng.randrange(256),rng.randrange(256));rows=[fragment(str(i),c,dot(c,truth)) for i,c in enumerate([[1,0],[0,1],[1,1],[2,1]])];rows[-1]['value']^=n+1;rows[-1]['sha256']=sha({k:rows[-1][k] for k in ['coefficients','value']})
  d=dict(width=2,tenant='blue',generation='g7',fault_budget=1,fragments=rows,anchors=[],owner_queries=[dict(id='x',coefficients=[1,0],cost=1),dict(id='y',coefficients=[0,1],cost=1)])
  verify_encoding(v.audit(d),candidates(d))

def test_revision_scope_checksum_and_duplicate_reordering():
 d=production();original=copy.deepcopy(d);rng=random.Random(7);rng.shuffle(d['fragments']);d['fragments']+=copy.deepcopy(d['fragments']);assert v.audit(d)==v.audit(original)
 for name,changes,reason in [('dead',dict(live=False),'retired'),('scope',dict(tenant='red'),'scope'),('checksum',dict(sha256='0'*64),'checksum')]:
  row=fragment(name,[1,0,0,0],10);d['fragments'].append(row);new={**row,**changes,'revision':2};d['fragments'].append(new)
 out=v.audit(d);assert out['rejected']==[dict(id='checksum',reason='checksum'),dict(id='dead',reason='retired'),dict(id='scope',reason='scope')];assert out['candidate_sha256']==v.audit(original)['candidate_sha256']

def test_conflicting_revision_even_if_superseded():
 d=production();r=copy.deepcopy(d['fragments'][0]);r['value']^=1;d['fragments']+=[r,{**r,'revision':2}]
 with pytest.raises(ValueError):v.audit(d)

def test_input_preservation_and_cli(tmp_path):
 d=production();old=copy.deepcopy(d);x=v.audit(d);assert d==old
 p=tmp_path/'input.json';p.write_text(json.dumps(d));r=subprocess.run([sys.executable,v.__file__,str(p)],capture_output=True,text=True);assert r.returncode==0 and json.loads(r.stdout)==x
