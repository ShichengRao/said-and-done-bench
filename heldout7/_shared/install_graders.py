"""Install shared offline grader code after author input files are stable."""
from pathlib import Path
import json,shutil,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from beambench.tasks import load_task,task_hash
for task_id in sys.argv[1:]:
    p=ROOT/'heldout7/pilot'/task_id
    if not p.is_dir() or p.name!=task_id or '/' in task_id: raise ValueError(task_id)
    spec=load_task(p);grader=p/'grader'
    shutil.copyfile(Path(__file__).with_name('grade_entry.py'),grader/'grade.py')
    shutil.copyfile(Path(__file__).with_name('review_grader.py'),grader/'_review.py')
    (grader/'review_config.json').write_text(json.dumps({'schema_version':1,'task_id':spec.id,'task_hash':task_hash(spec),'expected_status':spec.expected_status},indent=2)+'\n')
    print(json.dumps({'task':task_id,'task_hash':task_hash(spec)}))
