import copy,hashlib,json,random,sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
import recovery as r

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def anchor():return {'frontier':{'a':0,'b':0},'values':{'a':{'x':'0'},'b':{'y':'0'}},'applied':[]}
def event(s,n,t,o,k,b,a):return dict(shard=s,lsn=n,txid=t,ordinal=o,key=k,before=b,after=a)
def seal(t,rows,outcome='commit',parents=()):
 return dict(txid=t,outcome=outcome,parents=list(parents),parts={s:dict(lsns=[e['lsn'] for e in sorted(rows,key=lambda e:e['lsn']) if e['shard']==s],sha256=digest([e for e in sorted(rows,key=lambda e:e['lsn']) if e['shard']==s])) for s in sorted({e['shard'] for e in rows})})
def case():
 a=[event('a',1,'t1',0,'x','0','1'),event('b',1,'t1',1,'y','0','1')]
 b=[event('a',2,'t2',0,'x','garbage','bad')]
 c=[event('a',3,'t3',1,'x','1','3'),event('b',2,'t3',0,'y','1','3')]
 return dict(events=a+b+c,decisions=[seal('t3',c,parents=['t1']),seal('t2',b,'abort'),seal('t1',a)])
def setup(tmp_path,batch=None):
 p=str(tmp_path/'db');r.initialize(p,anchor());r.ingest(p,'load',0,batch or case());return p

def test_canonical_cross_shard_abort_and_ordinals(tmp_path):
 p=setup(tmp_path);x=r.advance(p,'go',1,{'a':3,'b':2});assert x['order']==['t1','t2','t3'];assert x['values']=={'a':{'x':'3'},'b':{'y':'3'}};assert x['processed']['t2']=='abort'
def test_partial_vector_rejected_atomically(tmp_path):
 p=setup(tmp_path);old=r.inspect(p)
 with pytest.raises(ValueError):r.advance(p,'bad',1,{'a':3,'b':1})
 assert r.inspect(p)==old
 assert r.advance(p,'bad',1,{'a':3,'b':2})['version']==2

def test_late_before_failure_rolls_back_all_groups(tmp_path):
 b=case();b['events'][-1]['before']='wrong';b['decisions'][0]=seal('t3',[e for e in b['events'] if e['txid']=='t3'],parents=['t1']);p=setup(tmp_path,b);old=r.inspect(p)
 with pytest.raises(ValueError):r.advance(p,'go',1,{'a':3,'b':2})
 assert r.inspect(p)==old

def test_exact_retry_before_cas_and_conflicting_reuse(tmp_path):
 p=setup(tmp_path);a=r.advance(p,'go',1,{'a':3,'b':2});r.ingest(p,'empty',2,{'events':[],'decisions':[]})
 assert r.advance(p,'go',1,{'b':2,'a':3})==a
 with pytest.raises(ValueError):r.ingest(p,'go',1,{'events':[],'decisions':[]})
 with pytest.raises(ValueError):r.advance(p,'go',3,{'a':3,'b':2})

def test_missing_and_aborted_parent(tmp_path):
 for parent in ['missing','t2']:
  b=case();b['decisions'][0]['parents']=[parent];p=tmp_path/parent;p.mkdir();db=setup(p,b)
  with pytest.raises(ValueError):r.advance(db,'go',1,{'a':3,'b':2})

def test_serialization_cycle(tmp_path):
 es=[event('a',1,'a',0,'x','0','1'),event('a',2,'b',0,'x','1','2'),event('b',1,'b',1,'y','0','1'),event('b',2,'a',1,'y','1','2')]
 b={'events':es,'decisions':[seal(t,[e for e in es if e['txid']==t]) for t in ['a','b']]};p=setup(tmp_path,b)
 with pytest.raises(ValueError):r.advance(p,'go',1,{'a':2,'b':2})

def test_seal_and_extra_event_and_duplicate_ordinal(tmp_path):
 for mode in ['hash','extra','ordinal']:
  b=case()
  if mode=='hash':b['decisions'][0]['parts']['a']['sha256']='0'*64
  if mode=='extra':b['events'].append(event('b',3,'t3',2,'z',None,'x'))
  if mode=='ordinal':b['events'][-1]['ordinal']=1;b['decisions'][0]=seal('t3',[e for e in b['events'] if e['txid']=='t3'],parents=['t1'])
  p=tmp_path/mode;p.mkdir();db=setup(p,b)
  with pytest.raises(ValueError):r.advance(db,'go',1,{'a':3,'b':2})

def test_batch_conflict_rolls_back_evidence(tmp_path):
 p=setup(tmp_path);b=case();bad=copy.deepcopy(b['events'][0]);bad['after']='different';extra=event('a',4,'late',0,'x','3','4')
 with pytest.raises(ValueError):r.ingest(p,'bad',1,{'events':[extra,bad],'decisions':[]})
 assert r.inspect(p)['version']==1
 altered=copy.deepcopy(extra);altered['after']='5';r.ingest(p,'ok',1,{'events':[altered],'decisions':[]})

def test_missing_evidence_can_be_supplied_after_failure(tmp_path):
 b=case();last=b['events'].pop();p=setup(tmp_path,b)
 with pytest.raises(ValueError):r.advance(p,'go',1,{'a':3,'b':2})
 r.ingest(p,'late',1,{'events':[last],'decisions':[]});assert r.advance(p,'go',2,{'a':3,'b':2})['values']['b']['y']=='3'

def test_anchor_and_input_preservation(tmp_path):
 a=anchor();b=case();before=copy.deepcopy([a,b]);p=str(tmp_path/'db');r.initialize(p,a);r.ingest(p,'load',0,b);r.advance(p,'go',1,{'a':3,'b':2});assert [a,b]==before
 assert r.initialize(p,a)['version']==2
 bad=copy.deepcopy(a);bad['values']['a']['x']='9'
 with pytest.raises(ValueError):r.initialize(p,bad)

def test_concurrent_cas_one_winner(tmp_path):
 p=setup(tmp_path)
 def run(n):
  try:return r.advance(p,str(n),1,{'a':3,'b':2})['version']
  except ValueError:return None
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,[1,2]))
 assert results.count(2)==1 and results.count(None)==1

def test_generated_partition_replay_and_decision_reordering(tmp_path):
 rng=random.Random(2907)
 for n in range(10):
  root=tmp_path/str(n);root.mkdir();p=str(root/'db');a=anchor();r.initialize(p,a);lsn={'a':0,'b':0};vals=copy.deepcopy(a['values']);es=[];ds=[];expected=[]
  for i in range(8):
   t=f't{i:02}';rows=[];abort=i%4==1;shards=['a','b'] if i%3 else ['b'];rng.shuffle(shards)
   for ordinal,s in enumerate(shards):
    lsn[s]+=1;k='x' if s=='a' else 'y';new=f'{n}-{i}';rows.append(event(s,lsn[s],t,ordinal,k,vals[s][k],new))
    if not abort:vals[s][k]=new
   es+=rows;ds.append(seal(t,rows,'abort' if abort else 'commit'));expected.append(t)
  rng.shuffle(es);rng.shuffle(ds);r.ingest(p,'a',0,{'events':es[:len(es)//2],'decisions':ds});r.ingest(p,'b',1,{'events':es[len(es)//2:],'decisions':[]});x=r.advance(p,'go',2,lsn);assert x['values']==vals and x['order']==expected

def test_fresh_interpreter_inspect_and_original_replay(tmp_path):
 import subprocess,sys,json
 p=setup(tmp_path);response=r.advance(p,'go',1,{'a':3,'b':2});r.ingest(p,'after',2,{'events':[],'decisions':[]})
 script="import json,sys,recovery; p=sys.argv[1]; print(json.dumps({'current':recovery.inspect(p),'replay':recovery.advance(p,'go',1,{'a':3,'b':2})},sort_keys=True))"
 child=subprocess.run([sys.executable,'-c',script,p],capture_output=True,text=True,timeout=15)
 assert child.returncode==0,child.stderr
 out=json.loads(child.stdout);assert out['current']==r.inspect(p) and out['replay']==response

def test_synchronized_two_process_compare_and_swap(tmp_path):
 import subprocess,sys,time,json
 p=setup(tmp_path);gate=tmp_path/'gate'
 script="""import json,sys,time,pathlib,recovery
p,ready,gate,request=sys.argv[1:]
pathlib.Path(ready).touch()
while not pathlib.Path(gate).exists():time.sleep(.005)
try: result=recovery.advance(p,request,1,{'a':3,'b':2})['version']
except ValueError: result=None
print(json.dumps(result))
"""
 children=[subprocess.Popen([sys.executable,'-c',script,p,str(tmp_path/('ready'+str(i))),str(gate),'child'+str(i)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for i in range(2)]
 deadline=time.monotonic()+10
 while not all((tmp_path/('ready'+str(i))).exists() for i in range(2)) and time.monotonic()<deadline:time.sleep(.005)
 gate.touch();outputs=[child.communicate(timeout=15) for child in children]
 assert all(child.returncode==0 for child in children),outputs
 results=[json.loads(out) for out,err in outputs];assert results.count(2)==1 and results.count(None)==1
 assert r.inspect(p)['version']==2
