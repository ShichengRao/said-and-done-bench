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

def test_cancel_before_dispatch_releases_and_blocks_dispatch(tmp_path):
 db=setup(tmp_path);cancel(db);assert balances(db)['c1']==(0,0,100)
 with pytest.raises(ValueError):dispatch(db,at=2)

def test_provider_success_then_cancel_has_same_financial_effect(tmp_path):
 db=setup(tmp_path);dispatch(db);receipt(db,'success','succeeded');out=cancel(db);assert out['refund']['status']=='compensating' and out['provider_operation']['id']=='compensation/r'
 dispatch(db,'comp',2,5,'compensation');receipt(db,'done','succeeded',3,'compensation');assert balances(db)['c1']==(0,0,100)

def test_stale_worker_lease_is_fenced_but_actual_receipt_is_not(tmp_path):
 db=setup(tmp_path);first=dispatch(db);second=dispatch(db,'retry',5,8);assert first['provider_operation']['id']==second['provider_operation']['id']=='refund/r';old=r.snapshot(db)
 with pytest.raises(ValueError):command(db,'old-worker','abandon',5,provider_operation='refund/r',lease_token='refund/r/1')
 assert r.snapshot(db)==old
 receipt(db,'truth','succeeded',9);assert balances(db)['c1']==(0,70,30)

def test_duplicate_and_out_of_order_receipts_do_not_reopen_terminal(tmp_path):
 db=setup(tmp_path);dispatch(db);receipt(db,'success','succeeded');v=version(db);x=receipt(db,'same-command-new-id','succeeded',receipt_id='success');assert x['result']=='receipt_replayed' and version(db)==v+1
 x=receipt(db,'old-accepted','accepted');assert x['result']=='receipt_ignored' and x['refund']['status']=='succeeded'
 x=receipt(db,'same-truth','succeeded');assert x['result']=='received' and balances(db)['c1']==(0,70,30)
 before=r.snapshot(db)
 with pytest.raises(ValueError):receipt(db,'conflict','failed')
 with pytest.raises(ValueError):receipt(db,'reused-receipt','accepted',receipt_id='success')
 assert r.snapshot(db)==before

def test_compensation_failure_never_restores_availability(tmp_path):
 db=setup(tmp_path,130);dispatch(db);cancel(db);receipt(db,'success','succeeded');dispatch(db,'comp',2,5,'compensation');out=receipt(db,'comp-failure','failed',3,'compensation');assert out['refund']['status']=='compensation_failed';assert balances(db)=={'c1':(0,100,0),'c2':(0,30,50)};invariant(db)

def test_original_failure_releases_uncertain_exposure(tmp_path):
 db=setup(tmp_path);dispatch(db);cancel(db);out=receipt(db,'failed','failed');assert out['refund']['status']=='cancelled' and balances(db)['c1']==(0,0,100)
 assert len(r.snapshot(db)['provider_operations'])==1

def test_deadline_expires_only_never_dispatched_holds_and_error_rollback(tmp_path):
 db=setup(tmp_path);before=r.snapshot(db)
 with pytest.raises(ValueError):dispatch(db,at=16,until=20)
 assert r.snapshot(db)==before
 command(db,'clock','tick',16);assert r.snapshot(db)['refunds'][0]['status']=='expired' and balances(db)['c1']==(0,0,100)
 other=tmp_path/'other';other.mkdir();db=setup(other);dispatch(db);command(db,'clock','tick',40);assert r.snapshot(db)['refunds'][0]['status']=='inflight' and balances(db)['c1']==(70,0,30)
 receipt(db,'success','succeeded',41);assert balances(db)['c1']==(0,70,30)

def test_reservation_windows_other_holds_and_atomic_unavailable(tmp_path):
 db=setup(tmp_path,130);out=command(db,'more','reserve',2,refund='other',merchant='m',currency='USD',cents=60,until=10,candidates=['c1','c2']);assert out['result']=='unavailable' and len(r.snapshot(db)['refunds'])==1
 with pytest.raises(ValueError):command(db,'bad-route','reserve',2,refund='other',merchant='m',currency='USD',cents=1,until=10,candidates=['c2','unknown'])
 out=command(db,'small','reserve',2,refund='other',merchant='m',currency='USD',cents=50,until=40,candidates=['c1','c2']);assert out['refund']['expires']==30;invariant(db)

def test_request_replay_before_clock_and_input_response_isolation(tmp_path):
 db=setup(tmp_path);q=dict(operation_id='send',at=1,kind='dispatch',refund='r',expected_version=1,provider_kind='refund',worker='w',until=5);before=copy.deepcopy(q);out=r.apply(db,q);saved=copy.deepcopy(out);command(db,'tick','tick',6);out['provider_operation']['lease']['token']='mutated';assert r.apply(db,q)==saved and q==before
 with pytest.raises(ValueError):r.apply(db,{**q,'at':6})

def test_generated_observation_permutations_conserve_principal(tmp_path):
 # Independent accounting expectation depends only on confirmed terminal truth,
 # never worker lease or arrival order of accepted/retryable observations.
 for index,order in enumerate(itertools.permutations(['accepted','retryable','succeeded'])):
  folder=tmp_path/str(index);folder.mkdir();db=setup(folder,130);dispatch(db);cancel(db)
  for i,event in enumerate(order):receipt(db,str(i),event,2);invariant(db)
  assert balances(db)=={'c1':(0,100,0),'c2':(0,30,50)}
  dispatch(db,'comp',3,4,'compensation');receipt(db,'compdone','succeeded',5,'compensation');assert balances(db)=={'c1':(0,0,100),'c2':(0,0,80)}

def test_fresh_process_snapshot_and_immutable_replay(tmp_path):
 db=setup(tmp_path);q=dict(operation_id='send',at=1,kind='dispatch',refund='r',expected_version=1,provider_kind='refund',worker='w',until=5);out=r.apply(db,q);cancel(db)
 script="import json,sys,refunds; print(json.dumps({'snapshot':refunds.snapshot(sys.argv[1]),'replay':refunds.apply(sys.argv[1],json.loads(sys.argv[2]))}))"
 child=subprocess.run([sys.executable,'-c',script,db,json.dumps(q)],capture_output=True,text=True,timeout=15);assert child.returncode==0,child.stderr;actual=json.loads(child.stdout);assert actual['snapshot']==r.snapshot(db) and actual['replay']==out

def test_two_process_dispatch_cas_has_one_lease(tmp_path):
 db=setup(tmp_path);gate=tmp_path/'go'
 script="""import json,pathlib,sys,time,refunds
p,ready,gate,rid=sys.argv[1:];pathlib.Path(ready).touch()
while not pathlib.Path(gate).exists():time.sleep(.005)
q={'operation_id':rid,'at':1,'kind':'dispatch','refund':'r','expected_version':1,'provider_kind':'refund','worker':rid,'until':5}
try: out=refunds.apply(p,q)['provider_operation']['lease']['token']
except ValueError:out=None
print(json.dumps(out))
"""
 children=[subprocess.Popen([sys.executable,'-c',script,db,str(tmp_path/('ready'+str(i))),str(gate),str(i)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for i in range(2)];deadline=time.monotonic()+10
 while not all((tmp_path/('ready'+str(i))).exists() for i in range(2)) and time.monotonic()<deadline:time.sleep(.005)
 gate.touch();out=[child.communicate(timeout=15) for child in children];assert all(child.returncode==0 for child in children),out;vals=[json.loads(o) for o,e in out];assert vals.count('refund/r/1')==1 and vals.count(None)==1;invariant(db)

def test_supplied_sequence_with_secondary_expiry_and_compensation_retry(tmp_path):
 data=json.loads((Path(__file__).parent/'original/data/input.json').read_text());db=str(tmp_path/'db');r.initialize(db,data['captures'])
 for q in data['commands']:
  r.apply(db,q);invariant(db)
 final=r.snapshot(db);states={x['id']:x['status'] for x in final['refunds']};assert states=={'r':'compensated','waiting':'expired'}
 assert balances(db)=={'c1':(0,0,100),'c2':(0,0,80)}
 comp=next(x for x in final['provider_operations'] if x['kind']=='compensation');assert comp['id']=='compensation/r' and comp['attempt']==2
