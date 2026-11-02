import copy,itertools,json,subprocess,sys,time
from pathlib import Path
import pytest
import refunds as r

def captures():return [dict(id='c1',merchant='m',currency='USD',captured_cents=100,refund_until=20),dict(id='c2',merchant='m',currency='USD',captured_cents=80,refund_until=30)]
def setup(tmp_path,cents=70):
 db=str(tmp_path/'db');r.initialize(db,captures());r.apply(db,dict(operation_id='reserve',at=1,kind='reserve',refund='r',merchant='m',currency='USD',cents=cents,until=15,candidates=['c1','c2']));return db

def version(db):return next(x['version'] for x in r.snapshot(db)['refunds'] if x['id']=='r')
def command(db,op,kind,at=1,**kwargs):return r.apply(db,dict(operation_id=op,kind=kind,at=at,**kwargs))
def dispatch(db,op='dispatch',at=1,until=5,kind='refund'):return command(db,op,'dispatch',at,refund='r',expected_version=version(db),provider_kind=kind,worker='worker',until=until)
def cancel(db,at=2):return command(db,'cancel','cancel',at,refund='r',expected_version=version(db))
def receipt(db,op,result,at=2,kind='refund',receipt_id=None):return command(db,op,'receipt',at,receipt_id=receipt_id or op,provider_operation=kind+'/r',result=result)
def balances(db):return {c['id']:(c['held_cents'],c['refunded_cents'],c['available_cents']) for c in r.snapshot(db)['captures']}
def invariant(db):
 s=r.snapshot(db)
 for c in s['captures']:assert c['held_cents']>=0 and c['refunded_cents']>=0 and c['available_cents']>=0 and c['captured_cents']==c['held_cents']+c['refunded_cents']+c['available_cents']

def test_cancellation_inflight_retains_exposure_then_compensates(tmp_path):
 db=setup(tmp_path);dispatch(db);assert cancel(db)['refund']['status']=='cancel_pending';assert balances(db)['c1']==(70,0,30)
 command(db,'later','tick',6);out=receipt(db,'late-success','succeeded',6);assert out['refund']['status']=='compensating' and balances(db)['c1']==(0,70,30)
 dispatch(db,'comp-dispatch',7,10,'compensation');assert balances(db)['c1']==(0,70,30)
 receipt(db,'comp-retry','retryable',8,'compensation');command(db,'abandon','abandon',8,provider_operation='compensation/r',lease_token='compensation/r/1');out=dispatch(db,'comp-dispatch-2',9,10,'compensation');assert out['provider_operation']['id']=='compensation/r' and out['provider_operation']['lease']['token']=='compensation/r/2'
 out=receipt(db,'comp-success','succeeded',11,'compensation');assert out['refund']['status']=='compensated' and balances(db)['c1']==(0,0,100);invariant(db)

