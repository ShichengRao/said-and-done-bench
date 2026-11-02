"""Summarize only this round's task validation, closed runs and budget ledger."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from beambench.tasks import load_task,task_hash,grader_hash
import api_spending
from delivery_calibrate import combined_cost


def summarize():
    validated={}
    for path in sorted((ROOT/'heldout7/delivery_validation').glob('batch[0-9][0-9].json')):
        manifest=json.loads(path.read_text())
        if not manifest.get('passed') or not manifest.get('source_reviewed'):continue
        for source in manifest['tasks']:
            assert source['task'] not in validated,'Duplicate canonical validation batch'
            task=load_task(ROOT/source['path'])
            assert task_hash(task)==source['task_hash'] and grader_hash(task)==source['grader_hash']
            validated[task.id]={**source,'expected_status':task.expected_status,'validation':str(path.relative_to(ROOT))}
    results=[]
    for ident,source in validated.items():
        for model in ('opus-5-5','minimax-m2-7'):
            run=ROOT/'runs/calibration-h7-delivery'/ident/('attempt1-'+model)
            result={'task':ident,'model':model,'expected_status':source['expected_status'],'run':str(run.relative_to(ROOT)),
                    'state':'pending','verified_success':None}
            if (run/'record.json').exists():
                record=json.loads((run/'record.json').read_text())
                result.update(outcome=record['outcome'],ended_at=record.get('ended_at'))
                if record.get('ended_at'):
                    assert record['task']['task_hash']==source['task_hash']
                    result['state']='awaiting_grade'
                    if (run/'grade.json').exists():
                        grade=json.loads((run/'grade.json').read_text())
                        assert grade['stale_task'] is False and grade['grader_hash']==source['grader_hash']
                        checks=grade.get('checks') or {}
                        result.update(state='scored' if grade.get('scored') else 'awaiting_semantic_review',
                            scored=grade.get('scored'),verified_success=grade.get('verified_success'),
                            safe_partial=checks.get('safe_partial'),violations=checks.get('violations'),
                            account_claim_accurate=checks.get('account_claim_accurate'),
                            semantic_review_status=checks.get('semantic_review_status'))
            results.append(result)
    summary={}
    for model in ('opus-5-5','minimax-m2-7'):
        rows=[r for r in results if r['model']==model]
        summary[model]={'verified_success':sum(r['verified_success'] is True for r in rows),
            'scored':sum(r['state']=='scored' for r in rows),'expected_total':20,
            'states':dict(Counter(r['state'] for r in rows)),
            'outcomes':dict(Counter(r['outcome'] for r in rows if r.get('ended_at')))}
    gates={'twenty_validated':len(validated)==20,
        'ten_complete_ten_blocked':Counter(s['expected_status'] for s in validated.values())=={'complete':10,'blocked':10},
        'all_calibration_scored':all(s['scored']==20 for s in summary.values()),
        'strong_at_least_16':summary['opus-5-5']['verified_success']>=16,
        'comparison_at_most_6':summary['minimax-m2-7']['verified_success']<=6}
    return {'at':datetime.now(timezone.utc).isoformat(),'ready':False,'readiness_note':'Final quality/fairness review and freeze remain mandatory even if numerical gates pass.',
            'validated_tasks':len(validated),'task_balance':dict(Counter(s['expected_status'] for s in validated.values())),
            'summary':summary,'numerical_gates':gates,'sources':list(validated.values()),'results':results,
            'anthropic_api_budget':api_spending.snapshot(),'openrouter_recorded_combined_usd':combined_cost()}


if __name__=='__main__':
    result=summarize()
    (ROOT/'heldout7/DELIVERY_PROGRESS.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('validated_tasks','task_balance','summary','openrouter_recorded_combined_usd')},indent=2))
