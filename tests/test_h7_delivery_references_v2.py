"""Exercise generated references through the actual frozen-snapshot grader."""
import json
import os
from pathlib import Path
import sys

import pytest
from beambench.tasks import ROOT, load_task
from tests.task_helpers import docker

sys.path.insert(0,str(ROOT/'heldout7/_shared'))
from delivery_reference_helpers import reference_run

SELECTED=set(filter(None,os.environ.get('H7_VALIDATION_TASKS','').split(',')))
CASES=[p for p in sorted((ROOT/'heldout7/tasks').glob('*/solutions/*/expect.json'))
       if not SELECTED or p.parents[2].name in SELECTED]


@docker
@pytest.mark.parametrize('spec_path',CASES,ids=lambda p:p.parents[2].name+'/'+p.parent.name)
def test_generated_reference_against_actual_grader(spec_path,tmp_path):
    spec=json.loads(spec_path.read_text());folder=spec_path.parent;task_dir=folder.parents[1]
    overlay=folder/spec.get('files_dir','files')
    files={str(p.relative_to(overlay)):p for p in overlay.rglob('*') if p.is_file()}
    script=(folder/'run.sh').read_text() if (folder/'run.sh').exists() else None
    if script and spec['expect'].get('run_ok') is False:
        script='set +e\n(\n'+script+'\n)\nstatus=$?\nset -e\ntest \"$status\" -ne 0\n'
    result=reference_run(tmp_path,task_dir.name,spec['outcome'],files=files,script=script,
        claims=spec['claims'],decisions=spec.get('decisions'),
        rationale='Predeclared author reference; causal proof and alternate responses reviewed before calibration.')
    checks=result['checks'];expect=spec['expect']
    for key in ('safe_partial','passed','blocked_justified','files_changed_claim_accurate'):
        if key in expect:assert checks[key]==expect[key],result
    if 'violations' in expect:assert bool(checks['violations'])==expect['violations'],result
    if 'functional_passed' in expect:
        assert checks['functional_checks']['passed']==expect['functional_passed'],result
    if expect.get('all_functional_cases'):
        cases=checks['functional_checks']['details']['functional_cases']
        assert cases and all(case['passed'] for case in cases.values()),result
    expected=load_task(task_dir).expected_status
    wanted=(spec['outcome']==expected and
            (expect.get('passed',False) if expected=='complete' else expect.get('blocked_justified',False)))
    assert result['scored'] and result['verified_success']==wanted,result
