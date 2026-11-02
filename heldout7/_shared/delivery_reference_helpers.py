"""Exercise actual offline delivery graders with reviewed scripted reference outcomes.

No reference bypass: each review binds exact record, workspace and grader bytes.
Only author-owned validation fixtures should be passed as decisions to this helper.
"""
from pathlib import Path
import asyncio
import hashlib
import importlib.util
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from beambench.tasks import load_task,prepare_workspace,task_hash
from beambench.grading import grade_run
from beambench.snapshot import snapshot_workspace
from tests.task_helpers import IMAGE,in_container
spec=importlib.util.spec_from_file_location('h7_review',Path(__file__).with_name('review_grader.py'))
review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)


def reference_run(tmp_path,task_id,outcome,*,files=None,script=None,claims=None,decisions=None,rationale=None):
    task=load_task(ROOT/'heldout7/tasks'/task_id);run=Path(tmp_path)/'run';workspace=run/'workspace'
    asyncio.run(prepare_workspace(task,workspace,IMAGE))
    for relative,source in (files or {}).items():
        target=workspace/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    if script:in_container(workspace,script,task.tmpfs)
    snapshot_workspace(workspace,run/'snapshot.tar.gz')
    record={'outcome':outcome,'task':{'id':task.id,'path':str(task.path),'task_hash':task_hash(task),'image':IMAGE},'submit':{'status':outcome,'claims':claims} if claims is not None else None,'terminal_state':None}
    (run/'record.json').write_text(json.dumps(record,indent=2)+'\n')
    if decisions is not None:
        config=json.loads((task.path/'grader/review_config.json').read_text())
        data={'schema_version':1,'provenance':'post_run_author_adjudication','final':True,
              'reviewer':'predeclared author reference fixture','reviewed_at':'2026-11-01T00:00:00+00:00',
              'binding':review.binding(run/'record.json',workspace,task.path/'grader',config),
              'decisions':decisions,'rationale':rationale or 'Predeclared author-reviewed reference response; see fixture and author rubric.',
              'evidence':['Scripted reference claims and snapshot',str(task.path/'AUTHOR_PROOF.md')]}
        p=run/'monitor/offline_review/semantic.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2)+'\n')
    return asyncio.run(grade_run(run))
