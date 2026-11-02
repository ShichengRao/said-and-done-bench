"""Run task-only authors in fresh existing Docker images, with API-only auth.

Does not read Claude account sessions, host Claude configuration, or cloud output.
Only the explicitly prepared authoring package is mounted into each container.
"""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT/'runs/authoring-h7-api'


def now(): return datetime.now(timezone.utc).isoformat()


def api_key():
    for line in (Path.home()/'.config/beambench/secrets.env').read_text().splitlines():
        line = line.strip().removeprefix('export ')
        if line.startswith('ANTHROPIC_API_KEY='):
            return line.split('=', 1)[1].strip().strip('"').strip("'")
    raise RuntimeError('Configured Anthropic API key is missing')


async def main():
    plan = json.loads((ROOT/'heldout7/API_EXECUTION_PLAN.json').read_text())
    assert plan['budget_usd'] == 50
    assert sum(plan['authoring_session_caps_usd'].values()) == 13
    RUNS.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'ANTHROPIC_API_KEY': api_key()}
    assert env['ANTHROPIC_API_KEY']

    def emit(value):
        event = {'at': now(), **value}
        with (RUNS/'events.jsonl').open('a') as file:
            file.write(json.dumps(event)+'\n')
        print(json.dumps(event), flush=True)

    async def author(package):
        domain = package['domain']
        out = RUNS/domain
        out.mkdir()  # Never overwrite or auto-reroll an author attempt.
        name = 'beambench-h7-api-author-'+domain
        prompt = (
            'Read /workspace/CLAUDE.md and /workspace/REQUESTS.json explicitly. '
            'Complete all assigned task packages in deliverables/, following those instructions. '
            'Use only /workspace and temporary files under /tmp; the full benchmark harness is absent. '
            'Do not read other container installation files or directories. '
            'Work through the assignments one at a time, updating STATUS.json after each. '
            'Preserve unfinished work if the session budget is reached. '
            'Use the supplied fixture and proof code efficiently. Do not make external model or API calls, '
            'spawn agents, fetch external sources, push, or create PRs. '
            'Finish with HANDOFF.json and a concise completion summary. '
            'The coordinator runs the final offline Docker integration checks.'
        )
        argv = ['docker','run','--rm','--init','--name',name,
            '--user',f'{os.getuid()}:{os.getgid()}',
            '--volume',f"{package['path']}:/workspace",'--workdir','/workspace',
            '--env','ANTHROPIC_API_KEY','--env','HOME=/tmp/author-home',
            '--entrypoint','sh','beambench-claude:dev','-c',
            'mkdir -p /tmp/author-home && exec "$@"','author',
            'claude','--bare','--no-session-persistence','--strict-mcp-config',
            '--tools','Bash,Read,Write,Edit,Glob,Grep','--permission-mode','bypassPermissions',
            '--model',plan['requested_model'],'--effort',plan['effort'],
            '--max-budget-usd',str(plan['authoring_session_caps_usd'][domain]),
            '--verbose','--output-format','stream-json','-p',prompt]
        emit({'event':'start','domain':domain,'tasks':package['tasks'],
              'session_budget_usd':plan['authoring_session_caps_usd'][domain],
              'image':'beambench-claude:dev','auth':'API key only',
              'context':'Fresh container and task-only mount; no host Claude state'})
        with (out/'claude.jsonl').open('xb') as log, (out/'stderr.log').open('xb') as error:
            proc = await asyncio.create_subprocess_exec(*argv, cwd=ROOT, env=env, stdout=log, stderr=error)
            code = await proc.wait()
        result = None
        for line in (out/'claude.jsonl').read_text().splitlines():
            try: row = json.loads(line)
            except ValueError: continue
            if row.get('type') == 'result': result = row
        if result is not None:
            (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        emit({'event':'finish','domain':domain,'exit_code':code,
              'result_subtype':(result or {}).get('subtype'),
              'total_cost_usd':(result or {}).get('total_cost_usd'),
              'tasks_checkpoint':str(Path(package['path'])/'STATUS.json')})

    await asyncio.gather(*(author(package) for package in plan['source_packages']))


if __name__ == '__main__': asyncio.run(main())
