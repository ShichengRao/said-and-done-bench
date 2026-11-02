"""The in-container submit command against the host-side channel."""

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

from beambench import prompts
from beambench.submit_channel import SubmitChannel, check_claims

SUBMIT = Path(__file__).resolve().parent.parent / 'container' / 'submit'
GOOD = {'summary': 'Did it.', 'verified_end_to_end': False, 'verification_commands': []}


def answer_one(channel, extra=()):
  """Answer the next request the way the run loop does, from a thread."""
  def loop():
    while True:
      for request in channel.poll():
        verdict = channel.validate(request)
        message = (
          prompts.submit_accepted(verdict.status) if verdict.accepted
          else prompts.submit_rejected(verdict.errors)
        )
        channel.ack(request.id, verdict.accepted, message)
        return
      time.sleep(0.05)
  thread = threading.Thread(target=loop, daemon=True)
  thread.start()
  return thread


def submit(tmp_path, *args, stdin=None):
  return subprocess.run(
    [sys.executable, str(SUBMIT), *args],
    input=stdin, capture_output=True, text=True, timeout=10,
    env={'BEAMBENCH_SUBMIT_DIR': str(tmp_path / 'submit'), 'PATH': '/usr/bin:/bin'},
  )


def test_accepted_submit_exits_zero(tmp_path):
  channel = SubmitChannel(tmp_path / 'submit')
  (tmp_path / 'claims.json').write_text(json.dumps(GOOD))
  answer_one(channel)
  result = submit(tmp_path, '--status', 'complete', '--claims', str(tmp_path / 'claims.json'))
  assert result.returncode == 0
  assert 'Submission recorded (status: complete)' in result.stdout


def test_claims_from_stdin(tmp_path):
  channel = SubmitChannel(tmp_path / 'submit')
  answer_one(channel)
  result = submit(tmp_path, '--status=blocked', '--claims', '-', stdin=json.dumps(GOOD))
  assert result.returncode == 0


def test_bad_status_and_missing_claims_are_rejected_with_reasons(tmp_path):
  channel = SubmitChannel(tmp_path / 'submit')
  answer_one(channel)
  result = submit(tmp_path, '--status', 'done')
  assert result.returncode == 1
  assert '--status must be "complete" or "blocked"' in result.stdout
  assert '--claims is required' in result.stdout


def test_unreadable_and_invalid_claims(tmp_path):
  channel = SubmitChannel(tmp_path / 'submit')
  answer_one(channel)
  result = submit(tmp_path, '--status', 'complete', '--claims', str(tmp_path / 'missing.json'))
  assert result.returncode == 1
  assert "can't read the claims file" in result.stdout

  answer_one(channel)
  result = submit(tmp_path, '--status', 'complete', '--claims', '-', stdin='{not json')
  assert result.returncode == 1
  assert "aren't valid JSON" in result.stdout


def test_help_sends_nothing(tmp_path):
  (tmp_path / 'submit').mkdir()
  result = submit(tmp_path, '--help')
  assert result.returncode == 0
  assert 'verification_commands' in result.stdout
  assert not list((tmp_path / 'submit').iterdir())


def test_unknown_arguments_still_reach_the_harness(tmp_path):
  channel = SubmitChannel(tmp_path / 'submit')
  answer_one(channel)
  result = submit(tmp_path, '--status', 'complete', '--force')
  assert result.returncode == 1
  assert "unexpected argument '--force'" in result.stdout


def test_check_claims():
  assert check_claims(GOOD) == []
  assert check_claims([]) == ['the claims must be a JSON object']
  errors = check_claims({'summary': ' ', 'verified_end_to_end': 'yes', 'verification_commands': 'ls'})
  assert len(errors) == 3
  assert check_claims({**GOOD, 'verified_end_to_end': True}) == [
    "\"verification_commands\" can't be empty when \"verified_end_to_end\" is true"
  ]
  assert check_claims(GOOD, extra_fields=['root_cause']) == ['"root_cause" is required for this task']


def test_reject_pending_answers_everything(tmp_path):
  channel = SubmitChannel(tmp_path / 'submit')
  (tmp_path / 'submit' / 'req-1-a.json').write_text('{}')
  channel.poll()
  (tmp_path / 'submit' / 'req-2-b.json').write_text('{}')
  channel.reject_pending('over')
  for request_id in ('1-a', '2-b'):
    ack = json.loads((tmp_path / 'submit' / f'ack-{request_id}.json').read_text())
    assert ack == {'accepted': False, 'message': 'over'}
