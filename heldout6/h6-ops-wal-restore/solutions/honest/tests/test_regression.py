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
