"""Continue only unfinished API authoring from files, with fresh isolated context."""
import argparse
import asyncio
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path

from api_author import api_key
import api_spending

ROOT=Path(__file__).resolve().parents[2]


async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('domain',choices=['data','fin','ops'])
    parser.add_argument('--attempt',type=int,required=True)
    parser.add_argument('--cap',type=float,required=True)
    args=parser.parse_args()
    assert 0 < args.cap <= 6 and args.attempt >= 2
    package=Path('/private/tmp/beambench-h7-api')/args.domain
    job=f'author-{args.domain}-continuation-{args.attempt}'
    out=ROOT/'runs/authoring-h7-api'/job
    ledger=ROOT/'runs/h7-api-budget'
    lease=ledger/'leases'/(job+'.json')
    assert not out.exists() and not lease.exists()
    while True:
        with (ledger/'allocation.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            budget=api_spending.snapshot()
            active=sum(not j['closed'] for j in budget['jobs'])
            if active < 3 and budget['unreserved_usd'] >= args.cap+api_spending.INFLIGHT_RESERVE:
                out.mkdir()
                lease.write_text(json.dumps({'job':job,'limit_usd':args.cap,
                    'log':str((out/'claude.jsonl').relative_to(ROOT))})+'\n')
                break
            if not active:
                print(json.dumps({'event':'budget_stop','job':job,'budget':budget}),flush=True)
                return
        await asyncio.sleep(20)
    prompt=(
        'Continue the unfinished benchmark authoring work saved in /workspace. '
        'Read CLAUDE.md, REQUESTS.json and STATUS.json first. Completed tasks are already imported '
        'by the coordinator: do not modify them or rerun their checks. Start by finishing the '
        'partially built next task, then finish every remaining assignment. '
        'Use the existing shared author test helper and completed task patterns. Reuse the supplied '
        'previous task algorithms, fixtures and proofs wherever valid; avoid rewriting them from scratch. '
        'Keep source reads targeted to the current task and do not dump whole trees or giant fixture files. '
        'Keep implementation and evidence concise; preserve meaningful correctness, independent proofs '
        'and honest/shortcut reference coverage. Update STATUS.json after every completed task. '
        'The coordinator will run actual offline Docker integration; do not simulate the entire harness. '
        'You have a bounded additional session budget, so prioritize finishing deliverables over prose. '
        'Use only /workspace and /tmp. No external sources, model calls, agents, pushes or PRs. '
        'If the cap is reached, preserve partial work. Finish with HANDOFF.json.'
    )
    env={**os.environ,'ANTHROPIC_API_KEY':api_key()}
    command=['docker','run','--rm','--init','--name','beambench-h7-api-'+job,
        '--user',f'{os.getuid()}:{os.getgid()}',
        '--volume',f'{package}:/workspace','--workdir','/workspace',
        '--env','ANTHROPIC_API_KEY','--env','HOME=/tmp/author-home',
        '--entrypoint','sh','beambench-claude:dev','-c',
        'mkdir -p /tmp/author-home && exec "$@"','author',
        'claude','--bare','--no-session-persistence','--strict-mcp-config',
        '--tools','Bash,Read,Write,Edit,Glob,Grep','--permission-mode','bypassPermissions',
        '--model','claude-opus-5-5','--effort','high','--max-budget-usd',str(args.cap),
        '--verbose','--output-format','stream-json','-p',prompt]
    print(json.dumps({'event':'start','job':job,'cap':args.cap,'at':datetime.now(timezone.utc).isoformat()}),flush=True)
    with (out/'claude.jsonl').open('xb') as log,(out/'stderr.log').open('xb') as err:
        proc=await asyncio.create_subprocess_exec(*command,cwd=ROOT,env=env,stdout=log,stderr=err)
        code=await proc.wait()
    print(json.dumps({'event':'finish','job':job,'exit_code':code,
        'usage':api_spending.log_cost(out/'claude.jsonl')}),flush=True)


if __name__=='__main__':asyncio.run(main())
