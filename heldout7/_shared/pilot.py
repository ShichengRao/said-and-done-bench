"""Run only the predeclared three-task pilot; preserve pending semantic grades.

Uses the unchanged benchmark CLI, pinned H6 model configurations, 60 steps and
2700 seconds. Never reads open model responses, supplies extra task instructions,
changes a provider, rebuilds an image, or rerolls a completed model attempt.
"""
from __future__ import annotations
import asyncio
from datetime import datetime,timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from beambench.tasks import load_task,task_hash,grader_hash,harness_hash
s=importlib.util.spec_from_file_location('prior_calibrate',ROOT/'heldout6/_shared/calibrate.py')
prior=importlib.util.module_from_spec(s);s.loader.exec_module(prior)
HERE=ROOT/'heldout7';RUNS=ROOT/'runs/calibration-h7';PYTHON=ROOT/'.venv/bin/python'
PLAN=HERE/'PILOT_PLAN.json'

def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def costs():
    total=0.0
    for p in RUNS.glob('h7-*/*/record.json'):
        r=read(p);cost=(r.get('usage_total') or {}).get('cost')
        if cost is not None:total+=cost;continue
        log=p.parent/'neutral.jsonl'
        if log.exists():
            for line in log.read_text().splitlines():
                event=json.loads(line);total+=((event.get('response') or {}).get('usage') or {}).get('cost',0) or 0
    return total

def identity(task):
    p=HERE/'pilot'/task;spec=load_task(p);v=read(HERE/'validation'/f'{task}.json');x=v['tasks'][task]
    assert v['valid'] and v['source_unchanged'] and task_hash(spec)==x['task_hash'] and grader_hash(spec)==x['grader_hash']
    for field in ('log','xml'):assert sha(ROOT/v[field])==v[field+'_sha256']
    assert sha(ROOT/x['test_file'])==x['test_sha256']
    return {'task':task,**x,'path':str(p.relative_to(ROOT)),'validation_sha256':sha(HERE/'validation'/f'{task}.json')}

def archive(x):
    dest=HERE/'_history'/x['task']/(x['task_hash']+'-'+x['grader_hash'])
    if not dest.exists():
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(ROOT/x['path'],dest,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','*.pyc'))
    spec=load_task(dest);assert task_hash(spec)==x['task_hash'] and grader_hash(spec)==x['grader_hash']
    return str(dest.relative_to(ROOT))

async def main():
    plan=read(PLAN);config=prior.verify_configs();assert not (ROOT/'ready.txt').exists()
    assert plan['tasks']==['h7-ops-generation-restore','h7-ops-generation-restore-larch','h7-fin-period-close']
    assert plan['models']==['astra','minimax-m2-7','flash'] and plan['max_initial_attempts']==9
    assert sha(ROOT/'heldout6/FREEZE_MANIFEST.json')=='ffaf7cb401b1783e0e57f74ce6b8c4d7626fed1ce50e8ba33d5c3000837572e8'
    assert harness_hash()==config['harness_hash']
    for k in ('image','agent_image'):
        assert subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',config['images'][k]],text=True).strip()==config['images'][k+'_id']
    identities=[identity(t) for t in plan['tasks']]
    approval=read(HERE/'pilot_reviews/SOURCE_REVIEW.json');assert approval['approved'] is True
    assert approval['pilot_plan_sha256']==sha(PLAN)
    assert approval['tasks']==[{k:x[k] for k in ('task','task_hash','grader_hash','test_sha256')} for x in identities]
    for x in identities:x['source_archive']=archive(x)
    runtime={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),PLAN,HERE/'_shared/review_grader.py',HERE/'_shared/grade_entry.py',HERE/'_shared/validate_pilot.py',HERE/'pilot_reviews/ADJUDICATION_RUBRIC.json']}
    control=RUNS/'control';control.mkdir(parents=True,exist_ok=True)
    lock=(control/'pilot.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    stop=asyncio.Event();stopped_models=set()
    def emit(event):
        event={'at':now(),**event}
        with (control/'events.jsonl').open('a') as f:f.write(json.dumps(event)+'\n')
        print(json.dumps(event),flush=True)
    def halt(model,reason):
        stopped_models.add(model);(control/('STOP_'+model)).write_text(json.dumps({'at':now(),'reason':reason})+'\n');emit({'event':'halt','model':model,'reason':reason})
    async def command(argv,env,log):
        with log.open('xb') as f:
            proc=await asyncio.create_subprocess_exec(*map(str,argv),cwd=ROOT,env=env,stdout=f,stderr=asyncio.subprocess.STDOUT)
            return await proc.wait()
    async def one(x,model,lane=None):
        if stop.is_set() or model in stopped_models or (control/('STOP_'+model)).exists():return
        spent=costs();combined=spent+prior.recorded_cost()
        if spent>=plan['recorded_api_scheduling_threshold_usd'] or combined>=plan['combined_h6_h7_recorded_api_threshold_usd']:
            stop.set();emit({'event':'cost_stop','new_recorded':spent,'combined_recorded':combined});return
        assert prior.verify_configs()==config
        assert all(sha(ROOT/p)==digest for p,digest in runtime.items())
        current=identity(x['task']);assert all(current[k]==x[k] for k in current)
        run=RUNS/x['task']/('pilot1-'+model)
        if run.exists() or list((RUNS/x['task']).glob('*-'+model)):
            halt(model,'Existing attempt retained; explicit review required, never auto-rerun');return
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'};argv=[PYTHON,'-m','beambench','run']
        if model=='astra':
            assert lane in (2,3);env['BEAMBENCH_CODEX_AUTH']=str(Path.home()/'.config/beambench'/f'codex-{lane}')
            argv+=['--agent','codex','--model','gpt-6-astra','--effort','max']
        else:
            if model=='minimax-m2-7':argv=[PYTHON,ROOT/'heldout6/_shared/run_configured.py','run']
            argv+=['--agent','neutral','--model-config',prior.CONFIG_NAMES[model]]
        argv+=['--task',ROOT/x['path'],'--run-dir',run,'--run-deadline','2700']
        prefix=x['task']+'-'+model;begin=time.monotonic()
        emit({'event':'start','model':model,'lane':lane,'run':str(run.relative_to(ROOT)),'source':x,'runtime_sha256':runtime})
        code=await command(argv,env,control/(prefix+'.log'))
        if not (run/'record.json').exists():halt(model,'Missing closed record; inspect log');return
        record=read(run/'record.json')
        assert task_hash(load_task(ROOT/x['path']))==x['task_hash'] and grader_hash(load_task(ROOT/x['path']))==x['grader_hash']
        issues=[];task=record.get('task') or {};info=record.get('agent_info') or {}
        if task.get('task_hash')!=x['task_hash'] or task.get('harness_hash')!=config['harness_hash']:issues.append('source/harness identity')
        if record.get('limits')!=config['limits']:issues.append('run limits')
        if not record.get('ended_at'):issues.append('not closed')
        if record.get('outcome')!='infra_error' and (record.get('snapshot') or {}).get('writers_frozen') is not True:issues.append('snapshot not frozen')
        if model=='astra':
            if info.get('model')!='gpt-6-astra' or info.get('effort')!='max' or task.get('agent_image_id')!=config['images']['agent_image_id']:issues.append('native model/image')
        else:
            expected=config['neutral'][prior.CONFIG_NAMES[model]];actual=prior.response_identity(run)
            if any(info.get(k)!=expected[k] for k in ('model','base_url','params')):issues.append('API configuration')
            if actual['models']!={expected['model']} or actual['providers']!={prior.PROVIDERS[model]} or actual['malformed']:issues.append('returned API model/provider')
            if model=='minimax-m2-7' and not actual['reasoning']:issues.append('missing reasoning content')
        if task.get('image_id')!=config['images']['image_id']:issues.append('task image')
        grade_code=None
        if (run/'snapshot.tar.gz').exists() and not issues and record.get('outcome')!='infra_error':
            if (run/'grade.json').exists():
                existing=read(run/'grade.json')
                assert existing.get('grader_hash')==x['grader_hash'] and existing.get('stale_task') is False
                assert existing.get('outcome')==record.get('outcome')
                grade_code=0
                emit({'event':'initial_grade_retained','run':str(run.relative_to(ROOT)),'grade_sha256':sha(run/'grade.json')})
            else:
                grade_code=await command([PYTHON,'-m','beambench','grade',run],env,control/(prefix+'-grade.log'))
        grade=read(run/'grade.json') if (run/'grade.json').exists() else {}
        assert prior.verify_configs()==config and harness_hash()==config['harness_hash']
        assert all(sha(ROOT/p)==digest for p,digest in runtime.items())
        final_identity=identity(x['task']);assert all(final_identity[k]==x[k] for k in final_identity)
        if grade:
            assert grade.get('grader_hash')==x['grader_hash'] and grade.get('stale_task') is False
            assert grade.get('outcome')==record.get('outcome')
        pending=(grade.get('checks') or {}).get('semantic_review_status')=='pending'
        emit({'event':'finish','model':model,'lane':lane,'run':str(run.relative_to(ROOT)),'exit_code':code,'grade_exit_code':grade_code,'outcome':record.get('outcome'),'semantic_review_pending':pending,'scored':grade.get('scored'),'verified_success':grade.get('verified_success'),'issues':issues,'seconds':round(time.monotonic()-begin,2),'record_sha256':sha(run/'record.json'),'snapshot_sha256':sha(run/'snapshot.tar.gz') if (run/'snapshot.tar.gz').exists() else None,'grade_sha256':sha(run/'grade.json') if (run/'grade.json').exists() else None,'recorded_cost':(record.get('usage_total') or {}).get('cost')})
        if issues or code or record.get('outcome')=='infra_error' or grade_code or (not grade.get('scored') and not pending):
            halt(model,'Infrastructure, identity or unresolved grading error; pending semantic review alone is not an error')
    async def safe(x,model,lane=None):
        try:await one(x,model,lane)
        except Exception as e:stop.set();halt(model,type(e).__name__+': '+str(e))
    native=asyncio.Queue()
    for x in identities:native.put_nowait(x)
    async def native_lane(lane):
        auth=Path.home()/'.config/beambench'/f'codex-{lane}'
        name=hashlib.sha256(str(auth).encode()).hexdigest()[:20]
        with (Path('/tmp')/f'beambench-h4-auth-{name}.lock').open('a') as authlock:
            fcntl.flock(authlock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            while not native.empty() and not stop.is_set() and 'astra' not in stopped_models:
                await safe(native.get_nowait(),'astra',lane)
    async def flash_lane():
        for x in identities:await safe(x,'flash')
    await asyncio.gather(native_lane(2),native_lane(3),flash_lane(),*(safe(x,'minimax-m2-7',i+1) for i,x in enumerate(identities)))
    emit({'event':'pilot_finished','stopped':sorted(stopped_models),'halted_all':stop.is_set(),'recorded_cost':costs()})
    if stopped_models or stop.is_set():raise SystemExit(2)

if __name__=='__main__':asyncio.run(main())
