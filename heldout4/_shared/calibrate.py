"""Round-four scheduling only; invokes the unchanged benchmark run/grade CLI.

Explicit task IDs must have passed their reference tests before scheduling.
One process owns each stored-auth lane at a time. A usage/auth failure halts
all new strong jobs; it never rotates credentials to evade provider limits.
"""
from __future__ import annotations
import argparse
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from beambench.tasks import load_task, task_hash, grader_hash


def stamp():
    return datetime.now(timezone.utc).isoformat()


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tasks', nargs='+')
    parser.add_argument('--revision', required=True)
    parser.add_argument('--anchors', choices=['both', 'astra', 'deepseek-v3'], default='both')
    parser.add_argument('--lanes', type=int, choices=[1, 2, 3], default=3)
    parser.add_argument('--wait-for-lanes', action='store_true')
    args = parser.parse_args()
    specs = []
    for task_id in args.tasks:
        if not task_id.startswith('h4-') or '/' in task_id:
            parser.error('use an explicit h4 task id')
        spec = load_task(ROOT / 'heldout4' / task_id)
        specs.append((task_id, task_hash(spec), grader_hash(spec)))
    out = ROOT / 'runs' / 'calibration-h4'
    control = out / 'control'
    control.mkdir(parents=True, exist_ok=True)
    event_path = control / f'{args.revision}-events.jsonl'
    halt_strong = asyncio.Event()
    stop_file = control / 'STOP_STRONG'

    def emit(event):
        event = {'at': stamp(), **event}
        with event_path.open('a') as stream:
            stream.write(json.dumps(event) + '\n')
        print(json.dumps(event), flush=True)

    async def command(argv, env, log):
        with log.open('wb') as stream:
            proc = await asyncio.create_subprocess_exec(*argv, cwd=ROOT, env=env, stdout=stream, stderr=asyncio.subprocess.STDOUT)
            return await proc.wait()

    async def run_one(item, anchor, lane=None):
        task_id, original_task_hash, original_grader_hash = item
        suffix = 'astra' if anchor == 'astra' else 'deepseek-v3'
        name = f'{task_id}-{args.revision}-{suffix}'
        run = out / name
        if run.exists():
            emit({'event': 'already_exists', 'run': name})
            return
        env = dict(os.environ)
        argv = ['uv', 'run', 'python', '-m', 'beambench', 'run']
        if anchor == 'astra':
            auth = Path.home() / '.config' / 'beambench' / ('codex' if lane == 1 else f'codex-{lane}')
            env['BEAMBENCH_CODEX_AUTH'] = str(auth)
            argv += ['--agent', 'codex', '--model', 'gpt-6-astra', '--effort', 'max']
        else:
            argv += ['--agent', 'neutral', '--model-config', 'deepseek-v3']
        argv += ['--task', str(ROOT / 'heldout4' / task_id), '--run-dir', str(run), '--run-deadline', '2700']
        emit({'event': 'start', 'run': name, 'anchor': anchor, 'lane': lane, 'task_hash': original_task_hash, 'grader_hash': original_grader_hash, 'argv': argv})
        started = time.monotonic()
        rc = await command(argv, env, control / f'{name}.log')
        record = json.loads((run / 'record.json').read_text()) if (run / 'record.json').exists() else {}
        detail = str(record.get('outcome_detail', ''))
        # Never print raw logs or credentials to the scheduler output.
        if anchor == 'astra' and (not record or record.get('outcome') == 'infra_error'):
            halt_strong.set()
            stop_file.write_text(name + '\n')
            emit({'event': 'strong_halted', 'run': name, 'reason': 'infrastructure/provider/auth failure; inspect this round record before continuing'})
        grade_rc = None
        verdict = {}
        if record and (run / 'snapshot.tar.gz').exists():
            grade_rc = await command(['uv', 'run', 'python', '-m', 'beambench', 'grade', str(run)], env, control / f'{name}-grade.log')
            if (run / 'grade.json').exists():
                verdict = json.loads((run / 'grade.json').read_text())
        spec = load_task(ROOT / 'heldout4' / task_id)
        changed = task_hash(spec) != original_task_hash or grader_hash(spec) != original_grader_hash
        emit({'event': 'finish', 'run': name, 'anchor': anchor, 'lane': lane, 'exit_code': rc, 'grade_exit_code': grade_rc, 'seconds': round(time.monotonic()-started, 2), 'mutated_during_run': changed, 'outcome': record.get('outcome'), 'usage': record.get('usage_total'), **{k: verdict.get(k) for k in ['verified_success','said_and_done','claims_truthful','scored','false_completion','stale_task']}})

    async def strong_lane(lane, queue):
        auth = Path.home() / '.config' / 'beambench' / ('codex' if lane == 1 else f'codex-{lane}')
        lock_id = hashlib.sha256(str(auth).encode()).hexdigest()[:20]
        lock_path = Path('/tmp') / f'beambench-h4-auth-{lock_id}.lock'
        with lock_path.open('a') as lock:
            while True:
                if stop_file.exists() or halt_strong.is_set():
                    emit({'event': 'strong_halted', 'lane': lane, 'reason': 'shared stop requires inspection before any new strong run'})
                    return
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if not args.wait_for_lanes:
                        halt_strong.set()
                        emit({'event': 'strong_halted', 'lane': lane, 'reason': 'auth lane is already locked'})
                        return
                    await asyncio.sleep(2)
            while not queue.empty() and not halt_strong.is_set() and not stop_file.exists():
                item = queue.get_nowait()
                await run_one(item, 'astra', lane)
                queue.task_done()

    async def weak_lane():
        for item in specs:
            await run_one(item, 'deepseek-v3')

    workers = []
    if args.anchors in ('both', 'astra'):
        queue = asyncio.Queue()
        for item in specs:
            queue.put_nowait(item)
        workers += [strong_lane(lane, queue) for lane in range(1, args.lanes + 1)]
    if args.anchors in ('both', 'deepseek-v3'):
        workers += [weak_lane()]
    await asyncio.gather(*workers)


if __name__ == '__main__':
    asyncio.run(main())
