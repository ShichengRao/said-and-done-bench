"""Resume untouched diagnostic tasks once native attempts and old diagnostics close."""
from pathlib import Path
import fcntl
import json
import subprocess
import sys
import time
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parent))
import calibrate as cal


def main():
    control=cal.RUNS/'control'
    tasks=[r['replacement'] for r in json.loads((cal.HERE/'ROUND4_BASELINE.json').read_text())['mapping']]
    while any(not (cal.RUNS/task/'v1-astra/grade.json').exists() for task in tasks):
        if (control/'STOP_astra').exists():raise SystemExit('Native calibration halted; review before expanding diagnostics.')
        time.sleep(10)
    with (control/'diagnostic.lock').open('r+') as diagnostic:
        fcntl.flock(diagnostic,fcntl.LOCK_EX)
        cfg=cal.verify_configs();cal.verify_baseline()
        missing=[]
        for task in tasks:
            identity=cal.validated_identity(task)
            for model in ('astra',):
                issues=cal.existing_grade_issues(cal.RUNS/task/('v1-'+model),identity,model,cfg)
                assert not issues,(task,model,issues)
            run=cal.RUNS/task/'v1-minimax-m2-7'
            if run.exists():
                issues=cal.existing_grade_issues(run,identity,'minimax-m2-7',cfg)
                assert not issues,(task,issues)
            else:missing.append(task)
        stop=control/'STOP_minimax-m2-7'
        assert json.loads(stop.read_text())['reason'].startswith('Planned scheduler transition')
        retained=control/('parallel-transition-'+uuid.uuid4().hex);retained.mkdir()
        stop.rename(retained/'original-stop.json')
        path=cal.HERE/'ADDITIONAL_MODEL_CONFIGS.json'
        (retained/'previous-configuration.json').write_bytes(path.read_bytes())
        extra=json.loads(path.read_text())
        extra['additional_diagnostic_lane']['max_concurrent']=3
        extra['combined_neutral_concurrency']=4
        extra['concurrency_transition']={'at':cal.stamp(),'reason':'Earlier task attempts closed without interruption; remaining single attempts run in three independent workers. Model settings and per-attempt budgets unchanged.','remaining_tasks':missing}
        path.write_text(json.dumps(extra,indent=2)+'\n')
        (retained/'new-configuration.json').write_bytes(path.read_bytes())
        cal.verify_configs()
    if missing:
        result=subprocess.call([cal.PYTHON,str(cal.HERE/'_shared/calibrate.py'),*missing,'--revision','v1',
                                '--models','minimax-m2-7','--diagnostic-lane','--diagnostic-concurrency','3'],cwd=cal.ROOT)
        if result:raise SystemExit(result)
        cfg=cal.verify_configs()
        for task in missing:
            issues=cal.existing_grade_issues(cal.RUNS/task/'v1-minimax-m2-7',cal.validated_identity(task),'minimax-m2-7',cfg)
            if issues:raise SystemExit('Diagnostic requires review: '+task+': '+'; '.join(issues))
    print(json.dumps({'event':'parallel_diagnostic_finished','new_tasks':len(missing)}),flush=True)


if __name__=='__main__':main()
