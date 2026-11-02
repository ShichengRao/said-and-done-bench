"""grade_run's shared verdict: grader failures and the grading image."""

import asyncio
import json
import tarfile

from beambench.grading import grade_run
from beambench.tasks import image_id, load_task, task_hash
from tests.task_helpers import docker

IMAGE = 'beambench-task:dev'


def make_run(tmp_path, grader_source, recorded_image_id):
  task = tmp_path / 'task'
  (task / 'grader').mkdir(parents=True)
  (task / 'task.toml').write_text('id = "task"\nfamily = "test"\nexpected_status = "complete"\n')
  (task / 'goal.md').write_text('Do it.\n')
  (task / 'grader' / 'grade.py').write_text(grader_source)
  run = tmp_path / 'run'
  (run / 'workspace').mkdir(parents=True)
  with tarfile.open(run / 'snapshot.tar.gz', 'w:gz') as tar:
    tar.add(run / 'workspace', arcname='workspace')
  (run / 'record.json').write_text(json.dumps({
    'outcome': 'complete',
    'task': {'path': str(task), 'task_hash': task_hash(load_task(task)), 'image': IMAGE, 'image_id': recorded_image_id},
  }))
  return run


@docker
def test_a_grader_that_fails_gives_no_verdict(tmp_path):
  run = make_run(tmp_path, 'raise SystemExit(3)\n', asyncio.run(image_id(IMAGE)))
  verdict = asyncio.run(grade_run(run))
  assert 'grader_error' in verdict['checks'] and not verdict['scored']
  assert verdict['verified_success'] is None and verdict['false_completion'] is None


@docker
def test_grading_uses_the_runs_image_and_says_when_it_cant(tmp_path):
  current = asyncio.run(image_id(IMAGE))
  verdict = asyncio.run(grade_run(make_run(tmp_path / 'a', 'print(\'{"passed": true}\')\n', current)))
  assert verdict['grading_image'] == current and verdict['grading_image_is_the_runs']
  assert verdict['verified_success'] is True
  gone = 'sha256:' + '0' * 64  # An image since deleted: fall back to the tag, and say so.
  verdict = asyncio.run(grade_run(make_run(tmp_path / 'b', 'print(\'{"passed": true}\')\n', gone)))
  assert verdict['grading_image'] == IMAGE and verdict['grading_image_is_the_runs'] is False


@docker
def test_the_grade_carries_the_said_and_done_verdict(tmp_path):
  overclaimed = 'print(\'{"passed": true, "runs_overclaimed_after_fix": true, "violations": []}\')\n'
  verdict = asyncio.run(grade_run(make_run(tmp_path, overclaimed, asyncio.run(image_id(IMAGE)))))
  assert verdict['verified_success'] is True
  assert verdict['claims_truthful'] is False and verdict['said_and_done'] is False
