"""The human baseline mode, with commands piped into its logged shell."""

import json
import subprocess
import sys
import time
from pathlib import Path

from beambench import human
from tests.task_helpers import docker

REPO = Path(__file__).resolve().parent.parent

SESSION = """\
echo 'hello from beambench' > hello.txt
cat hello.txt
false
printf '%s' '{"summary": "Wrote hello.txt", "verified_end_to_end": true, "verification_commands": ["cat hello.txt"]}' > /harness/human/claims.json
submit --status complete --claims /harness/human/claims.json
exit
"""


@docker
def test_a_person_works_in_the_logged_shell_and_the_run_is_graded(tmp_path):
  run_dir = tmp_path / 'run'
  run = subprocess.Popen(
    [sys.executable, '-m', 'beambench', 'human', '--task', 'tasks/hello', '--run-dir', str(run_dir), '--hours', '1'],
    cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
  )
  try:
    for _ in range(300):
      if (run_dir / human.SHELL_FILE).exists():
        break
      time.sleep(0.5)
    container = json.loads((run_dir / human.SHELL_FILE).read_text())['container']
    shell = [arg for arg in human.shell_command(container) if arg != '--tty']  # No terminal here.
    subprocess.run(shell, input=SESSION, text=True, capture_output=True, timeout=120)
    output, _ = run.communicate(timeout=300)
  finally:
    if run.poll() is None:
      run.kill()
  assert 'GOAL' in output and 'beambench shell' in output
  assert 'verified success: True' in output and 'commands logged: ' in output
  record = json.loads((run_dir / 'record.json').read_text())
  assert record['outcome'] == 'complete' and record['task']['track'] == 'human'
  logged = [json.loads(line) for line in (run_dir / 'telemetry' / 'human.jsonl').read_text().splitlines()]
  assert [entry['command'] for entry in logged[:3]] == ["echo 'hello from beambench' > hello.txt", 'cat hello.txt', 'false']
  assert logged[2]['exit_code'] == 1 and logged[0]['cwd'] == '/workspace'
  assert record['human']['commands'] >= 4 and record['human']['failed_commands'] >= 1
  assert not (run_dir / human.SHELL_FILE).exists()  # The container is gone.


def test_the_claims_template_has_every_field_the_task_asks_for():
  template = human.claims_template(['runs_after_fix', 'failures_after_fix'])
  assert list(template) == ['summary', 'verified_end_to_end', 'verification_commands', 'runs_after_fix', 'failures_after_fix']
