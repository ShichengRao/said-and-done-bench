"""Regrade completed own-round snapshots after grader-only fixes, retaining old verdicts."""
import asyncio
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from beambench.tasks import load_task, grader_hash, task_hash
from beambench.grading import grade_run

async def main():
    prefixes=sys.argv[1:]
    events=ROOT/'heldout4'/'GRADER_REGRADES.jsonl'
    for run in sorted((ROOT/'runs'/'calibration-h4').glob('h4-*')):
        if prefixes and not any(run.name.startswith(p) for p in prefixes):
            continue
        path=run/'grade.json'
        if not path.exists():
            continue
        old=json.loads(path.read_text())
        record=json.loads((run/'record.json').read_text())
        spec=load_task(Path(record['task']['path']))
        if record['task']['task_hash'] != task_hash(spec):
            print(json.dumps({'run':run.name,'skipped':'superseded task inputs; requires fresh model runs'}),flush=True)
            continue
        current=grader_hash(spec)
        if old.get('grader_hash')==current:
            continue
        backup=run/('grade-before-'+old.get('grader_hash','unknown')+'.json')
        if not backup.exists():
            backup.write_bytes(path.read_bytes())
        new=await grade_run(run)
        fields=('grader_hash','verified_success','said_and_done','claims_truthful','scored','passed','false_completion','unjustified_block','graded_at')
        event={'run':run.name,'task_hash':record['task']['task_hash'],'stale_task':new.get('stale_task'),'before':{k:old.get(k) for k in fields},'after':{k:new.get(k) for k in fields}}
        with events.open('a') as stream:
            stream.write(json.dumps(event)+'\n')
        print(json.dumps(event),flush=True)

asyncio.run(main())
