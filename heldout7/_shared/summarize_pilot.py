"""Summarize only closed, final-graded predeclared pilot attempts."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from beambench.tasks import load_task,task_hash,grader_hash
H=ROOT/'heldout7';R=ROOT/'runs/calibration-h7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())

def timing_metadata(run):
 p=run/'neutral.jsonl'
 if not p.exists():return None
 events=[json.loads(line) for line in p.read_text().splitlines()]
 commands=[e for e in events if 'seconds' in e]
 waits=[e['t']-events[i-1]['t'] for i,e in enumerate(events) if i and 'response' in e]
 return {'command_count':len(commands),'command_seconds':round(sum(e['seconds'] for e in commands),2),
         'command_timeouts':sum(e.get('exit_code') is None for e in commands),
         'response_count':sum('response' in e for e in events),
         'recorded_response_intervals_seconds':round(sum(waits),2),
         'timing_note':'Log intervals and completed command durations only; excludes any unfinished final call and setup/cleanup.'}

def main():
 plan=read(H/'PILOT_PLAN.json');events=[json.loads(line) for line in (R/'control/events.jsonl').read_text().splitlines()]
 assert any(e['event']=='pilot_finished' for e in events)
 assert not (ROOT/'ready.txt').exists()
 rows=[];native=[];cost=0.;unknown=[]
 for task in plan['tasks']:
  spec=load_task(H/'pilot'/task)
  for model in plan['models']:
   run=R/task/('pilot1-'+model)
   if not (run/'record.json').exists():
    rows.append({'task':task,'model':model,'started':False});continue
   record=read(run/'record.json');assert record['ended_at']
   g=read(run/'grade.json') if (run/'grade.json').exists() else {}
   if g:
    assert g['grader_hash']==grader_hash(spec) and not g['stale_task']
    assert g['checks'].get('semantic_review_status') not in ('pending','invalid')
   assert record['task']['task_hash']==task_hash(spec)
   usage=record.get('usage_total') or {}
   if model=='astra':native.append({'task':task,'usage':usage})
   elif usage.get('cost') is not None:cost+=usage['cost']
   else:unknown.append(str(run.relative_to(ROOT)))
   hashes={p.name:sha(p) for p in [run/'record.json',run/'snapshot.tar.gz',run/'grade.json'] if p.exists()}
   review=run/'monitor/offline_review/semantic.json'
   if review.exists():hashes['monitor/offline_review/semantic.json']=sha(review)
   initial=run/'grade-history/before-author-review/grade.json'
   if initial.exists():hashes['grade-history/before-author-review/grade.json']=sha(initial)
   row={'task':task,'model':model,'started':True,'run':str(run.relative_to(ROOT)),
        'expected_status':spec.expected_status,'outcome':record['outcome'],
        'steps':record.get('steps'),'started_at':record['started_at'],'ended_at':record['ended_at'],
        'usage':usage,'hashes':hashes,'task_hash':task_hash(spec),'grader_hash':grader_hash(spec)}
   row.update({k:g.get(k) for k in ('scored','verified_success','claims_truthful','said_and_done','false_completion','wrongly_blocked','unjustified_block')})
   row['semantic_decisions']=g.get('checks',{}).get('semantic_decisions')
   row['files_changed_claim_accurate']=g.get('checks',{}).get('files_changed_claim_accurate')
   row['timing_metadata']=timing_metadata(run)
   row['api_retries']=(record.get('agent_info') or {}).get('retries')
   rows.append(row)
 counts={}
 for model in plan['models']:
  mr=[r for r in rows if r['model']==model];scored=[r for r in mr if r.get('scored')]
  counts[model]={'attempts':sum(r['started'] for r in mr),'scored':len(scored),
    'verified_success':sum(r['verified_success'] is True for r in scored),
    'said_and_done':sum(r['said_and_done'] is True for r in scored),
    'justified_blocked_submissions':sum(r.get('expected_status')=='blocked' and r.get('outcome')=='blocked' and r.get('verified_success') is True for r in mr),
    'false_completion':sum(r.get('false_completion') is True for r in mr),
    'unnecessary_refusal':sum(r.get('wrongly_blocked') is True for r in mr)}
 summary={'at':datetime.now(timezone.utc).isoformat(),'stage':'three-task pilot only; not ready',
    'source_commit':'0f041f5','plan_sha256':sha(H/'PILOT_PLAN.json'),'rubric_sha256':sha(H/'pilot_reviews/ADJUDICATION_RUBRIC.json'),
    'counts':counts,'recorded_api_cost_usd':cost,'unpriced_api_attempts':unknown,'native_usage':native,
    'cost_note':'Recorded API cost only; native subscription usage is separate and unreported failed requests may be unpriced.',
    'rows':rows,'ready':False,'full_calibration_run':False}
 out=H/'PILOT_RESULTS.json'
 with out.open('x') as f:f.write(json.dumps(summary,indent=2)+'\n')
 print(json.dumps({'counts':counts,'recorded_api_cost_usd':cost,'unpriced_api_attempts':unknown},indent=2))
if __name__=='__main__':main()
