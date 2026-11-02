"""Fixture-only checks; never touches the real Round 5 evidence."""
import copy,fcntl,hashlib,importlib.util,json,shutil,sys,tempfile,types,unittest
from pathlib import Path
REAL=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REAL/'heldout5/_shared'))
spec=importlib.util.spec_from_file_location('freeze_draft',str(REAL/'heldout5/_shared/freeze.py'));f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
COMMIT='a'*40;H='f'*64;STAMP='2026-10-30T12:00:00+00:00'
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n' if not isinstance(v,str) else v)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class Fixture:
 def __init__(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.here=self.root/'heldout5';self.runs=self.root/'runs/calibration-h5';self.events=[]
  self.cfg=copy.deepcopy(json.loads((REAL/'heldout5/MODEL_CONFIGS.json').read_text()));self.cfg['harness_hash']=H;write(self.here/'MODEL_CONFIGS.json',self.cfg)
  extra=json.loads((REAL/'heldout5/ADDITIONAL_MODEL_CONFIGS.json').read_text());write(self.here/'ADDITIONAL_MODEL_CONFIGS.json',extra);self.cfg['neutral'].update(extra['neutral']);self.cfg['additional_diagnostic_lane']=extra['additional_diagnostic_lane'];self.cfg['combined_neutral_concurrency']=extra['combined_neutral_concurrency']
  self.cal=types.SimpleNamespace(ROOT=self.root,HERE=self.here,RUNS=self.runs,CONFIG_NAMES=f.calibrate.CONFIG_NAMES,PROVIDERS=f.calibrate.PROVIDERS,verify_configs=lambda:self.cfg,harness_hash=lambda:H)
  self.cal.load_task=lambda p:types.SimpleNamespace(id=p.parent.name if p.parent.parent.name=='_history' else p.name,expected_status=json.loads((p/'task.toml').read_text())['status'],family='heldout5-trap',path=p)
  self.cal.task_hash=lambda spec:digest(spec.path/'task.toml');self.cal.grader_hash=lambda spec:digest(spec.path/'grader/grade.py')
  self.identities={};mapping=[];olds=[]
  for i in range(20):
   tid='h5-fixture-'+str(i);status='complete' if i<10 else 'blocked';p=self.here/tid
   write(p/'task.toml',{'status':status,'id':tid});write(p/'grader/grade.py','pass\n');write(p/'workspace/a.py','pass\n')
   task=self.cal.load_task(p);th=self.cal.task_hash(task);gh=self.cal.grader_hash(task);test='tests/test_task_'+tid.replace('-','_')+'.py';write(self.root/test,'def test_x(): assert True\n')
   ident={'task_hash':th,'grader_hash':gh,'test_file':test,'test_sha256':digest(self.root/test)};self.identities[tid]={'task':tid,**ident}
   vrun='fixture-'+str(i);log='heldout5/validation/'+vrun+'.log';xml='heldout5/validation/'+vrun+'.xml';write(self.root/log,'1 passed\n');write(self.root/xml,'<testsuite tests="1" failures="0" errors="0" skipped="0"/>')
   validation={'valid':True,'source_unchanged':True,'exit_code':0,'counts':{'tests':1,'failures':0,'errors':0,'skipped':0},'tasks':{tid:ident},'after':{tid:ident},'run_id':vrun,'log':log,'log_sha256':digest(self.root/log),'xml':xml,'xml_sha256':digest(self.root/xml)}
   write(self.here/'validation'/f'{tid}.json',validation);write(self.here/'validation'/f'{vrun}.json',validation)
   archive=self.here/'_history'/tid/(th+'-'+gh);shutil.copytree(p,archive)
   pred='h4-fixture-'+str(i);mapping.append({'replacement':tid,'predecessor':pred,'expected_status':status,'predecessor_task_hash':th,'predecessor_grader_hash':gh});olds.append({'id':pred,'expected_status':status,'task_hash':th,'grader_hash':gh})
   for model in f.MODELS:self.add_run(tid,model,status,th,gh,archive)
  self.events.append({'event':'scheduler_finished','at':STAMP,'revision':'v1'})
  self.save_events();write(self.runs/'control/scheduler.lock','')
  write(self.here/'ROUND4_BASELINE.json',{'baseline_source_commit':'b'*40,'baseline_freeze_commit':'c'*40,'mapping':mapping})
  self.pins={}
  for path in f.PRIOR_PINS:
   if path.startswith('heldout4/'):
    body={'source_commit':'b'*40,'tasks':olds,'source_file_sha256':{},'model_configuration':{'harness_hash':H,'images':self.cfg['images']}}
   else:body={'prior_manifest_sha256':dict(self.pins),'followup_file_sha256':{}}
   write(self.root/path,body);self.pins[path]=digest(self.root/path)
  self.cal.validated_identity=lambda tid:self.identities[tid]
 def save_events(self):write(self.runs/'control/events.jsonl',''.join(json.dumps(e)+'\n' for e in self.events))
 def add_run(self,tid,model,status,th,gh,archive,revision='v1',verified=None,outcome=None):
  name=tid+'/'+revision+'-'+model;run=self.runs/name
  previous=[e['run'] for e in self.events if e['event']=='start' and e['task']==tid and e['model']==model and e['task_hash']==th]
  start={'event':'start','at':STAMP,'revision':revision,'run':name,'task':tid,'model':model,'lane':2 if model=='astra' else None,'task_hash':th,'grader_hash':gh,'source_archive':str(archive.relative_to(self.root)),'repeat_reason':'independent repeat' if previous else None,'previous_same_input_attempts':previous}
  vs=(model=='astra') if verified is None else verified;outcome=outcome or status
  meta={'id':tid,'expected_status':status,'path':str(self.here/tid),'task_hash':th,'harness_hash':H,'image_id':self.cfg['images']['image_id'],'agent_image_id':self.cfg['images']['agent_image_id'] if model=='astra' else self.cfg['images']['image_id'],'agent':'codex' if model=='astra' else 'neutral','track':'native' if model=='astra' else 'neutral'}
  if model=='astra':info={'model':'gpt-6-astra','effort':'max'}
  else:
   c=self.cfg['neutral'][f.calibrate.CONFIG_NAMES[model]];info={k:c[k] for k in ['model','base_url','params']};info.update(model_config=c['name'],providers=[f.calibrate.PROVIDERS[model]])
  record={'run_id':name.replace('/','-'),'task':meta,'agent_info':info,'started_at':STAMP,'ended_at':STAMP,'outcome':outcome,'limits':self.cfg['limits'],'snapshot':{'file':'snapshot.tar.gz','writers_frozen':True,'bytes':8},'usage_total':{'cost':0.1} if model!='astra' else {},'steps':5}
  grade={'task':tid,'outcome':outcome,'expected_status':status,'grader_hash':gh,'grading_image':self.cfg['images']['image_id'],'grading_image_is_the_runs':True,**{k:False for k in f.FLAGS}}
  grade.update(scored=outcome!='infra_error',verified_success=vs,claims_truthful=vs,said_and_done=vs)
  write(run/'record.json',record);write(run/'grade.json',grade);write(run/'snapshot.tar.gz','snapshot');write(run/'scrub.json',{'redacted':[],'unscrubbable':[]})
  if model=='astra':write(run/'codex.jsonl','{}\n')
  else:write(run/'neutral.jsonl',json.dumps({'response':{'model':info['model'],'provider':info['providers'][0],'usage':{'cost':0.1}}})+'\n')
  finish={'event':'finish','at':STAMP,'revision':revision,'run':name,'model':model,'outcome':outcome,'mutated_during_run':False,'grade_exit_code':0,**{k:grade[k] for k in ['scored','verified_success','said_and_done','claims_truthful','stale_task']}}
  self.events.extend([start,finish]);return run
 def git(self,root,*args,input=None):
  if args==('rev-parse','HEAD'):return COMMIT
  if args==('branch','--show-current'):return 'blind-round-4'
  if args[:2]==('status','--porcelain'):return ''
  if args[0]=='ls-files':return '\n'.join(sorted(['heldout5/'+p for p in f.tree(self.here)]+[str(p.relative_to(self.root)) for p in (self.root/'tests').glob('test_task_h5_*.py')]))
  if args[0]=='check-ignore':return input.strip()
  raise AssertionError(args)
 def image(self,name):return next(self.cfg['images'][k+'_id'] for k in ['image','agent_image'] if self.cfg['images'][k]==name)
 def collect(self):return f.collect(self.cal,COMMIT,git_call=self.git,image_lookup=self.image,prior_pins=self.pins)
 def freeze(self):return f.freeze(COMMIT,cal=self.cal,git_call=self.git,image_lookup=self.image,prior_pins=self.pins)
 def close(self):self.tmp.cleanup()
class Tests(unittest.TestCase):
 def setUp(self):self.x=Fixture()
 def tearDown(self):self.x.close()
 def test_valid_80_runs_freeze_and_no_overwrite(self):
  r=self.x.freeze();self.assertEqual(len(r['attempts']),80);self.assertEqual(len(r['tasks']),20);self.assertIn('-04:00',r['frozen_at_eastern'])
  self.assertEqual(r['models']['deepseek-v3']['recorded_cost_usd'],2.0000000000000004)
  with self.assertRaises(ValueError):self.x.freeze()
 def test_started_without_finish(self):
  self.x.events=[e for e in self.x.events if not (e['event']=='finish' and e['run'].endswith('v1-flash'))];self.x.save_events()
  with self.assertRaisesRegex(ValueError,'lack finish|Overlapping'):self.x.collect()
 def test_no_best_retry(self):
  tid='h5-fixture-0';v=self.x.identities[tid];archive=self.x.here/'_history'/tid/(v['task_hash']+'-'+v['grader_hash'])
  self.x.add_run(tid,'deepseek-v3','complete',v['task_hash'],v['grader_hash'],archive,'v2',verified=True);self.x.events.append({'event':'scheduler_finished','at':STAMP,'revision':'v2'});self.x.save_events()
  with self.assertRaisesRegex(ValueError,'Weak anchor succeeded'):self.x.collect()
 def test_strong_scored_failure_blocks(self):
  name='h5-fixture-0/v1-astra';p=self.x.runs/name/'grade.json';g=json.loads(p.read_text());g.update(verified_success=False,said_and_done=False,claims_truthful=False);write(p,g)
  for e in self.x.events:
   if e.get('run')==name and e['event']=='finish':e.update(verified_success=False,said_and_done=False,claims_truthful=False)
  self.x.save_events()
  with self.assertRaisesRegex(ValueError,'Strong anchor failed'):self.x.collect()
 def test_live_image_change_blocks(self):
  with self.assertRaisesRegex(ValueError,'Image changed'):f.collect(self.x.cal,COMMIT,git_call=self.x.git,image_lookup=lambda _: 'changed',prior_pins=self.x.pins)
 def test_current_grader_change_requires_regrade(self):
  path=self.x.runs/'h5-fixture-0/v1-astra/grade.json';g=json.loads(path.read_text());g['grader_hash']='0'*64;write(path,g)
  with self.assertRaisesRegex(ValueError,'lacks provenance'):self.x.collect()
 def test_missing_archive(self):
  archive=next((self.x.here/'_history/h5-fixture-0').iterdir());shutil.rmtree(archive)
  with self.assertRaisesRegex(ValueError,'original archive'):self.x.collect()
 def test_validation_log_tamper(self):
  write(self.x.here/'validation/fixture-0.log','changed')
  with self.assertRaisesRegex(ValueError,'validation log'):self.x.collect()
 def test_prior_manifest_tamper(self):
  write(self.x.root/next(iter(self.x.pins)),{})
  with self.assertRaisesRegex(ValueError,'Hash mismatch'):self.x.collect()
 def test_transcript_wrong_provider(self):
  p=self.x.runs/'h5-fixture-0/v1-flash/neutral.jsonl';p.write_text(p.read_text().replace('DeepInfra','Other'))
  with self.assertRaisesRegex(ValueError,'model/provider'):self.x.collect()
 def test_unfinished_regrade(self):
  write(self.x.runs/'h5-fixture-0/v1-astra/grade-history/partial/started.json',{})
  with self.assertRaisesRegex(ValueError,'Partial/orphan'):self.x.collect()
 def test_snapshot_writer_not_frozen(self):
  p=self.x.runs/'h5-fixture-0/v1-astra/record.json';r=json.loads(p.read_text());r['snapshot']['writers_frozen']=False;write(p,r)
  with self.assertRaisesRegex(ValueError,'Incomplete snapshot'):self.x.collect()
 def test_infra_flash_explicit_and_no_cost_doublecount(self):
  name='h5-fixture-0/v1-flash';run=self.x.runs/name
  for file in ['record.json','grade.json']:
   p=run/file;x=json.loads(p.read_text());x['outcome']='infra_error'
   if file=='grade.json':x['scored']=False;x['claims_truthful']=None
   else:x['snapshot']['writers_frozen']=False
   write(p,x)
  for e in self.x.events:
   if e.get('run')==name and e['event']=='finish':e.update(outcome='infra_error',scored=False,claims_truthful=None)
  self.x.save_events();r=self.x.collect();self.assertEqual(r['tasks'][0]['models']['flash']['infrastructure'],1)
  self.assertAlmostEqual(r['models']['flash']['recorded_cost_usd'],2.0)
  attempt=next(a for a in r['attempts'] if a['name']==name);self.assertTrue(attempt['infrastructure_unfrozen_snapshot']);self.assertFalse(attempt['flags']['scored'])
  self.assertIsNone(attempt['flags']['claims_truthful'])
 def test_scored_unknown_claim_is_preserved_without_counting_as_true(self):
  name='h5-fixture-0/v1-flash';run=self.x.runs/name
  for file in ['record.json','grade.json']:
   p=run/file;x=json.loads(p.read_text());x['outcome']='timeout'
   if file=='grade.json':x['claims_truthful']=None
   write(p,x)
  for e in self.x.events:
   if e.get('run')==name and e['event']=='finish':e.update(outcome='timeout',claims_truthful=None)
  self.x.save_events();r=self.x.collect()
  attempt=next(a for a in r['attempts'] if a['name']==name)
  self.assertTrue(attempt['flags']['scored']);self.assertIsNone(attempt['flags']['claims_truthful'])
  self.assertEqual(r['tasks'][0]['models']['flash']['claims_truthful'],0)
 def add_regrades(self):
  tid='h5-fixture-0';x=self.x;oldid=copy.deepcopy(x.identities[tid]);write(x.here/tid/'grader/grade.py','changed grader\n');newhash=digest(x.here/tid/'grader/grade.py');x.identities[tid]['grader_hash']=newhash
  vpath=x.here/'validation'/f'{tid}.json';v=json.loads(vpath.read_text());v['tasks'][tid]['grader_hash']=newhash;v['after'][tid]['grader_hash']=newhash;v['run_id']='regrade-validation';write(vpath,v);write(x.here/'validation/regrade-validation.json',v)
  archive=x.here/'_history'/tid/(oldid['task_hash']+'-'+newhash);shutil.copytree(x.here/tid,archive)
  for model in f.MODELS:
   name=tid+'/v1-'+model;run=x.runs/name;before=json.loads((run/'grade.json').read_text());directory=run/'grade-history/regraded'
   write(directory/'before.json',before);after=dict(before,grader_hash=newhash);write(directory/'after.json',after);write(run/'grade.json',after)
   e={'event':'regrade','at':STAMP,'run':name,'run_id':name.replace('/','-'),'revision':'v1','reason':'coverage fix','task_hash':oldid['task_hash'],'source_archive':str(archive.relative_to(x.root)),'validation_run':'regrade-validation','validation_sha256':digest(vpath),'test_sha256':oldid['test_sha256'],'before_grade_sha256':digest(directory/'before.json'),'before_grader_hash':before['grader_hash'],'before_flags':{k:before[k] for k in f.FLAGS},'raw_evidence_sha256':f.tree(run,exclude=('grading','grade-history','grade.json')),'history_directory':str(directory.relative_to(x.root)),'before_grade':'before.json'}
   write(directory/'started.json',e);e.update(succeeded=True,raw_evidence_unchanged=True,command_exit_code=0,error=None,after_grade_sha256=digest(directory/'after.json'),after_grader_hash=newhash,after_flags={k:after[k] for k in f.FLAGS},after_grade='after.json');write(directory/'event.json',e);write(directory/'command.log','graded\n');x.events.append(e)
  x.save_events()
 def test_retained_regrade_chain(self):
  self.add_regrades();r=self.x.collect();attempt=next(a for a in r['attempts'] if a['name']=='h5-fixture-0/v1-astra');self.assertEqual(len(attempt['grade_versions']),2);self.assertEqual(len(attempt['regrade_events']),1)
 def test_broken_regrade_before_hash(self):
  self.add_regrades();write(self.x.runs/'h5-fixture-0/v1-astra/grade-history/regraded/before.json',{})
  with self.assertRaisesRegex(ValueError,'retained grade'):self.x.collect()
 def test_regrade_validation_identity(self):
  self.add_regrades();e=next(e for e in self.x.events if e['event']=='regrade');e['validation_sha256']='0'*64;write(self.x.root/e['history_directory']/'event.json',e);self.x.save_events()
  with self.assertRaisesRegex(ValueError,'Regrade validation'):self.x.collect()
 def test_active_lock(self):
  with (self.x.runs/'control/scheduler.lock').open('r+') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   with self.assertRaisesRegex(ValueError,'still active'):self.x.freeze()
 def test_active_diagnostic_lock(self):
  path=self.x.runs/'control/diagnostic.lock'
  with path.open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   with self.assertRaisesRegex(ValueError,'still active'):self.x.freeze()
 def test_parallel_independent_neutral_lanes(self):
  names=['h5-fixture-0/v1-flash','h5-fixture-0/v1-minimax-m2-7']
  selected=[e for e in self.x.events if e.get('run') in names]
  rest=[e for e in self.x.events if e.get('run') not in names]
  starts=[e for e in selected if e['event']=='start'];finishes=[e for e in selected if e['event']=='finish']
  self.x.events=starts+finishes+rest;self.x.save_events()
  self.assertEqual(len(self.x.collect()['attempts']),80)
 def test_three_diagnostic_workers_and_collision_rejection(self):
  extra=json.loads((self.x.here/'ADDITIONAL_MODEL_CONFIGS.json').read_text())
  extra['additional_diagnostic_lane']['max_concurrent']=3;extra['combined_neutral_concurrency']=4
  write(self.x.here/'ADDITIONAL_MODEL_CONFIGS.json',extra)
  self.x.cfg['additional_diagnostic_lane']=extra['additional_diagnostic_lane'];self.x.cfg['combined_neutral_concurrency']=4
  names=[f'h5-fixture-{i}/v1-minimax-m2-7' for i in range(3)]
  selected=[e for e in self.x.events if e.get('run') in names]
  rest=[e for e in self.x.events if e.get('run') not in names]
  starts=[e for e in selected if e['event']=='start'];finishes=[e for e in selected if e['event']=='finish']
  for i,e in enumerate(starts):e['lane']=i+1
  self.x.events=starts+finishes+rest;self.x.save_events()
  self.assertEqual(len(self.x.collect()['attempts']),80)
  starts[1]['lane']=1;self.x.save_events()
  with self.assertRaisesRegex(ValueError,'Overlapping'):self.x.collect()
 def test_missing_model_task(self):
  name='h5-fixture-0/v1-flash';shutil.rmtree(self.x.runs/name);self.x.events=[e for e in self.x.events if e.get('run')!=name];self.x.save_events()
  with self.assertRaisesRegex(ValueError,'current input attempts'):self.x.collect()
if __name__=='__main__':unittest.main()
