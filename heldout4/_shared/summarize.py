"""Summarize only this round's own saved runs; never infer success from prose."""
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from beambench.tasks import load_task, task_hash, grader_hash


def collect():
    rows=[]
    for run in sorted((ROOT/'runs'/'calibration-h4').glob('h4-*')):
        if not (run/'record.json').exists():
            continue
        record=json.loads((run/'record.json').read_text())
        verdict=json.loads((run/'grade.json').read_text()) if (run/'grade.json').exists() else {}
        task=record.get('task') or {}
        row={'run':run.name,'task':task.get('id'), 'outcome':record.get('outcome'),
             'outcome_detail':record.get('outcome_detail'), 'agent_cmd':record.get('agent_cmd'),
             'agent_info':record.get('agent_info'), 'agent':task.get('agent'), 'usage':record.get('usage_total'),
             'started_at':record.get('started_at'),'ended_at':record.get('ended_at'),
             'steps':record.get('steps'),'turns':record.get('turns'),
             'task_hash':task.get('task_hash'),'harness_hash':task.get('harness_hash'),
             'image':task.get('image'),'image_id':task.get('image_id'),
             'agent_image':task.get('agent_image'),'agent_image_id':task.get('agent_image_id'),
             'limits':record.get('limits'),
             'grade_available':bool(verdict)}
        row.update({k:verdict.get(k) for k in ('expected_status','verified_success','said_and_done','claims_truthful','scored','passed','false_completion','unjustified_block','wrongly_blocked','stale_task','grader_hash','graded_at','grading_image','grading_image_is_the_runs')})
        row['checks']=verdict.get('checks',{})
        if task.get('path'):
            spec=load_task(Path(task['path']))
            row['current_task_hash']=task_hash(spec)
            row['current_grader_hash']=grader_hash(spec)
            row['superseded_by_task_revision']=row['task_hash'] != row['current_task_hash']
            row['current_versions']=bool(verdict) and row['task_hash']==row['current_task_hash'] and row['grader_hash']==row['current_grader_hash']
        rows.append(row)
    return rows


if __name__=='__main__':
    rows=collect()
    target=ROOT/'heldout4'/'CALIBRATION.json'
    target.write_text(json.dumps(rows,indent=2)+'\n')
    for r in rows:
        print(r['run'],r['outcome'],'verified='+str(r['verified_success']),'said_and_done='+str(r['said_and_done']),'current='+str(r.get('current_versions')))
    print('Astra task runs:',sum(r.get('agent')=='codex' for r in rows))
    print('DeepSeek recorded USD:',sum((r.get('usage') or {}).get('cost',0) for r in rows if r.get('agent')=='neutral'))
