"""Perform the specifically reviewed provider retry after the core batch closes."""
from pathlib import Path
import argparse
import fcntl
import json
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calibrate as cal


def review_failure(document):
    name=document['run']
    assert name in {'h5-data-service-scope/v1-deepseek-v3','h5-fin-credit-release/v1-deepseek-v3'}
    run=cal.RUNS/name;record,grade=cal.read_run(run)
    assert cal.sha(run/'record.json')==document['record_sha256']
    assert cal.sha(run/'grade.json')==document['grade_sha256']
    assert record['outcome']=='infra_error' and grade['scored'] is False and not grade['verified_success']
    assert 'HTTP 400' in record['outcome_detail'] and 'invalid escaped character' in record['outcome_detail']
    identity=cal.validated_identity(run.parent.name)
    assert identity['task_hash']==document['task_hash']==record['task']['task_hash']
    assert identity['grader_hash']==document['grader_hash']==grade['grader_hash']
    assert document['planned_retry_revision']=='infra-retry-1'
    assert document['reason'].strip()
    return identity


def launch(tasks,revision,reason=None):
    command=[cal.PYTHON,str(cal.HERE/'_shared/calibrate.py'),*tasks,
             '--revision',revision,'--models','deepseek-v3']
    if reason:command+=['--repeat-reason',reason]
    result=subprocess.call(command,cwd=cal.ROOT)
    if result:raise SystemExit(result)
    config=cal.verify_configs()
    for task in tasks:
        run=cal.RUNS/task/(revision+'-deepseek-v3')
        issues=cal.existing_grade_issues(run,cal.validated_identity(task),'deepseek-v3',config)
        if issues:raise SystemExit('Recovery requires further review: '+task+': '+'; '.join(issues))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-document',choices=['INFRASTRUCTURE_REVIEW.json','INFRASTRUCTURE_REVIEW_CREDIT.json'],default='INFRASTRUCTURE_REVIEW.json')
    args=parser.parse_args()
    document=json.loads((cal.HERE/args.review_document).read_text())
    control=cal.RUNS/'control'
    with (control/'scheduler.lock').open('r+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        cal.verify_baseline();identity=review_failure(document)
        retry=cal.RUNS/identity['task']/(document['planned_retry_revision']+'-deepseek-v3')
        assert not retry.exists(),'The single reviewed retry was already attempted; inspect it explicitly.'
        stop=control/'STOP_deepseek-v3';stopped=json.loads(stop.read_text())
        assert stopped['run']==document['run']
        archived=control/('reviewed-STOP_deepseek-v3-'+uuid.uuid4().hex+'.json')
        assert not archived.exists();stop.rename(archived)
        retained={'at':cal.stamp(),'review':document,'retained_stop':str(archived.relative_to(cal.ROOT)),
                  'retained_stop_sha256':cal.sha(archived)}
        with (control/('infrastructure-review-'+uuid.uuid4().hex+'.json')).open('x') as stream:
            json.dump(retained,stream,indent=2);stream.write('\n')
    launch([identity['task']],document['planned_retry_revision'],document['reason'])
    mapping=json.loads((cal.HERE/'ROUND4_BASELINE.json').read_text())['mapping']
    missing=[r['replacement'] for r in mapping if not (cal.RUNS/r['replacement']/'v1-deepseek-v3').exists()]
    if missing:launch(missing,'v1')
    print(json.dumps({'event':'reviewed_v3_recovery_finished','new_unattempted_tasks':len(missing)}),flush=True)


if __name__=='__main__':
    main()
