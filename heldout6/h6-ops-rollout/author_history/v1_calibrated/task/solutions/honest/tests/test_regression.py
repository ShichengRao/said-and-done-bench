import copy,json
from concurrent.futures import ThreadPoolExecutor
import pytest
import controller as c

def config():
 return dict(nodes={n:dict(rack='r',zone=z,capacity=1) for n,z in [('a','x'),('b','y'),('c','x'),('d','y')]},rack_capacity={'r':4},services={'svc':dict(size=1,min_ready=2,min_zones=2)},initial={'a':dict(service='svc',image='old'),'b':dict(service='svc',image='old'),'c':None,'d':None},max_inflight=3)
def plan():
 actions=[dict(id='c',depends=[],op='start',node='c',service='svc',image='new'),dict(id='d',depends=[],op='start',node='d',service='svc',image='new'),dict(id='x',depends=['c'],op='stop',node='a',service='svc',image='old'),dict(id='y',depends=['d'],op='stop',node='b',service='svc',image='old')]
 return dict(epoch=1,observed=config()['initial'],actions=actions,target={'a':None,'b':None,'c':dict(service='svc',image='new'),'d':dict(service='svc',image='new')})
def call(p,kind,**args):
 version=c.inspect(p)['version'];return c.apply(p,dict(id='q'+str(version),expected_version=version,kind=kind,**args))
def setup(tmp_path):
 p=str(tmp_path/'db');c.initialize(p,config());call(p,'install',**plan());return p

def test_parallel_dispatch_and_out_of_order_receipts(tmp_path):
 p=setup(tmp_path);x=call(p,'dispatch');assert x['created']==['1:c:1','1:d:1'] and x['observed']==config()['initial'] and x['done']==[]
 call(p,'receipt',receipts=[dict(token='1:d:1',success=True)]);x=call(p,'dispatch');assert x['created']==['1:y:1']
 call(p,'receipt',receipts=[dict(token='1:y:1',success=True),dict(token='1:c:1',success=True)]);x=call(p,'dispatch');assert x['created']==['1:x:1'];x=call(p,'receipt',receipts=[dict(token='1:x:1',success=True)]);assert x['observed']==plan()['target'] and x['done']==['c','d','x','y']

