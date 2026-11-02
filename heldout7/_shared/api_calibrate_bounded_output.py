"""Run validated delivery tasks through the existing native Claude API adapter.

One attempt per task, 900 seconds, fresh run/container/context, no cloud state.
Waits for the shared three-job limit and reserves the explicit $50 API budget.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT),str(HERE)]
from beambench.tasks import load_task,task_hash,grader_hash,harness_hash
import api_spending

RUNS=ROOT/'runs/calibration-h7-delivery'
PYTHON=ROOT/'.venv/bin/python'
CLAUDE_IMAGE='sha256:517cb73bd32ea39f6da1fb1da09f0ca1ce11f93eac1aa3e878b127f5c928616f'


def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--validation',type=Path,required=True)
    parser.add_argument('--session-cap',type=float,default=2)
    args=parser.parse_args()
    assert 0 < args.session_cap <= 5
    validation=read(args.validation)
    assert validation['passed'] and validation['source_reviewed']
    baseline=read(ROOT/'heldout6/MODEL_CONFIGS.json')
    expected_limits={**baseline['limits'],'run_deadline_s':900.0}
    assert harness_hash()==baseline['harness_hash']
    assert subprocess.check_output(['docker','image','inspect','--format','{{.Id}}','beambench-claude:dev'],text=True).strip()==CLAUDE_IMAGE
    runtime={str(p.resolve()):sha(p) for p in (Path(__file__),HERE/'run_api_bounded_output.py',HERE/'api_spending.py',args.validation)}
    for relative,digest in validation['test_file_sha256'].items():
        assert sha(ROOT/relative)==digest
        runtime[str((ROOT/relative).resolve())]=digest
    control=RUNS/'control';control.mkdir(parents=True,exist_ok=True)
    ledger=ROOT/'runs/h7-api-budget';leases=ledger/'leases';leases.mkdir(parents=True,exist_ok=True)
    stop=asyncio.Event()

    def emit(row):
        row={'at':now(),**row}
        with (control/'opus-events.jsonl').open('a') as file:file.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)

    async def command(argv,env,log):
        with log.open('xb') as file:
            proc=await asyncio.create_subprocess_exec(*map(str,argv),cwd=ROOT,env=env,
                stdout=file,stderr=asyncio.subprocess.STDOUT)
            return await proc.wait()

    async def one(x):
        task=load_task(ROOT/x['path'])
        assert task.id==x['task'] and task.command_timeout_s==120
        assert task_hash(task)==x['task_hash'] and grader_hash(task)==x['grader_hash']
        run=RUNS/x['task']/'attempt1-opus-5-5'
        assert not run.exists(), 'Never automatically reroll an existing attempt'
        job='calibration-'+x['task']
        waiting=False
        while not stop.is_set():
            with (ledger/'allocation.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                budget=api_spending.snapshot()
                active=sum(not j['closed'] for j in budget['jobs'])
                if active<3 and budget['unreserved_usd']>=args.session_cap+2.3:
                    with (leases/(job+'.json')).open('x') as file:
                        json.dump({'job':job,'limit_usd':args.session_cap,'inflight_reserve_usd':2.3,'context_limit_tokens':200000,'max_output_tokens':32000,'log':str((run/'claude.jsonl').relative_to(ROOT))},file)
                    break
                if not active:
                    emit({'event':'budget_stop','task':x['task'],'budget':budget});stop.set();return
            if not waiting:
                emit({'event':'waiting_for_capacity','task':x['task']});waiting=True
            await asyncio.sleep(20)
        if stop.is_set():return
        assert all(sha(p)==digest for p,digest in runtime.items())
        archive=ROOT/'heldout7/_history'/x['task']/(x['task_hash']+'-'+x['grader_hash'])
        if not archive.exists():
            archive.parent.mkdir(parents=True,exist_ok=True)
            shutil.copytree(task.path,archive,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        assert task_hash(load_task(archive))==x['task_hash']
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','H7_API_SESSION_CAP_USD':str(args.session_cap)}
        env.pop('H7_API_TRANSPORT_PROBE',None)
        emit({'event':'start','task':x['task'],'source':x,'profile':'native-opus-api-900s-200k-32koutput-v3',
              'session_cap_usd':args.session_cap,'runtime_pins':runtime})
        code=await command([PYTHON,HERE/'run_api_bounded_output.py','run','--agent','claude',
            '--model','claude-opus-5-5','--effort','high','--task',task.path,'--run-dir',run,
            '--run-deadline','900'],env,control/(x['task']+'-opus.log'))
        if not (run/'record.json').exists():
            emit({'event':'missing_record','task':x['task'],'exit_code':code});stop.set();return
        record=read(run/'record.json');info=record.get('agent_info') or {};rt=record.get('task') or {}
        issues=[]
        if record.get('limits')!=expected_limits:issues.append('limits')
        if info.get('model')!='claude-opus-5-5' or info.get('effort')!='high':issues.append('model/effort')
        if rt.get('agent_image_id')!=CLAUDE_IMAGE:issues.append('native image')
        if rt.get('task_hash')!=x['task_hash'] or rt.get('harness_hash')!=baseline['harness_hash']:issues.append('task/harness identity')
        if not record.get('ended_at'):issues.append('unclosed record')
        if record.get('outcome')!='infra_error' and (record.get('snapshot') or {}).get('writers_frozen') is not True:issues.append('snapshot not frozen')
        if not (run/'claude.jsonl').exists():issues.append('missing API usage evidence')
        if not (run/'grade.json').exists() and (run/'snapshot.tar.gz').exists() and not issues:
            await command([PYTHON,'-m','beambench','grade',run],env,control/(x['task']+'-opus-grade.log'))
        grade=read(run/'grade.json') if (run/'grade.json').exists() else {}
        if grade and (grade.get('grader_hash')!=x['grader_hash'] or grade.get('stale_task') is not False):issues.append('grader identity')
        assert task_hash(task)==x['task_hash'] and grader_hash(task)==x['grader_hash']
        assert all(sha(p)==digest for p,digest in runtime.items())
        emit({'event':'finish','task':x['task'],'exit_code':code,'outcome':record.get('outcome'),
            'scored':grade.get('scored'),'verified_success':grade.get('verified_success'),
            'semantic_review_status':(grade.get('checks') or {}).get('semantic_review_status'),
            'issues':issues,'record_sha256':sha(run/'record.json'),'api_budget':api_spending.snapshot()})
        if issues or code or record.get('outcome')=='infra_error':stop.set()

    await asyncio.gather(*(one(x) for x in validation['tasks']))
    emit({'event':'batch_finished','stopped':stop.is_set()})


if __name__=='__main__':asyncio.run(main())
