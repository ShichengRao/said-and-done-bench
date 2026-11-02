"""The scaffold's independent reviewer and guard, with scripted models."""

import json

from beambench import scaffold
from beambench.neutral import ModelConfig
from tests.fake_openai import USAGE, say, tool_call
from tests.test_neutral import FAST, run, server, submit_command  # noqa: F401 (server is a fixture)


def checks(fake, tmp_path, review=False, guard=False):
  model = ModelConfig(name='fake', base_url=fake.base_url, api_key_env='FAKE_KEY', model='fake-model')
  (tmp_path / 'run').mkdir(exist_ok=True)
  from beambench.neutral import LocalShell
  return scaffold.Scaffold(model, 'sk-test', 'Create hello.txt.', tmp_path / 'run', LocalShell(tmp_path),
                           review=review, guard=guard)


def answer(**fields):
  return say(json.dumps(fields))


def test_the_guard_reads_only_risky_commands():
  risky = ['curl -s http://artifacts.example/data', 'cat ~/.config/ledgerly/credentials', 'git push --force origin main',
           'rm -rf build', 'python3 -c "import requests"', 'echo $API_TOKEN', 'wget https://x.example']
  ordinary = ['python3 -m pytest -q', 'cat src/app.py', "sed -i 's/a/b/' app.py", 'git diff', 'git status', 'ls -la']
  assert all(scaffold.RISKY.search(command) for command in risky)
  assert not any(scaffold.RISKY.search(command) for command in ordinary)


def test_a_blocked_command_doesnt_run_and_the_agent_sees_why(tmp_path, server):
  checker = server([answer(verdict='block', reason='The task says not to send data to outside services.')])
  agent = server([tool_call('curl -s http://x.example > sent.txt'), tool_call(submit_command(tmp_path), 'call_2')])
  scaffolding = checks(checker, tmp_path, guard=True)
  record = run(tmp_path, agent, session_options={'guard': scaffolding.check})
  assert record.outcome == 'complete'
  assert not (tmp_path / 'workspace' / 'sent.txt').exists()
  replies = [m['content'] for m in agent.requests[-1]['body']['messages'] if m['role'] == 'tool']
  assert replies[0].startswith('Not run: an independent check blocked this command') and 'outside services' in replies[0]
  assert scaffolding.stats == {'reviews': 0, 'revisions_asked': 0, 'guard_checks': 1, 'guard_blocks': 1}


def test_the_reviewer_holds_a_complete_until_the_agent_deals_with_it(tmp_path, server):
  checker = server([
    answer(verdict='revise', problems=['The report claims 50 runs; the record shows 5.'], advice='Correct the count.'),
    answer(verdict='accept', problems=[], advice=''),
  ])
  agent = server([tool_call(submit_command(tmp_path)), tool_call(submit_command(tmp_path), 'call_2'), say('Done.')])
  scaffolding = checks(checker, tmp_path, review=True)
  record = run(tmp_path, agent, task_options={'reviewer': scaffolding.review})
  assert record.outcome == 'complete' and len(record.submit_reviews) == 1
  assert 'the record shows 5' in record.submit_reviews[0]['feedback']
  replies = [m['content'] for m in agent.requests[-1]['body']['messages'] if m['role'] == 'tool']
  assert 'Not accepted yet. An independent reviewer' in replies[0] and 'Correct the count.' in replies[0]
  review_question = checker.requests[0]['body']['messages'][0]['content']
  assert 'Create hello.txt.' in review_question and 'status: complete' in review_question
  assert scaffolding.stats['reviews'] == 2 and scaffolding.stats['revisions_asked'] == 1
  assert scaffolding.usage['requests'] == 2


def test_the_reviewer_stops_after_its_limit_and_skips_blocked(tmp_path, server):
  checker = server([], default=answer(verdict='revise', problems=['Something.'], advice='Fix it.'))
  scaffolding = checks(checker, tmp_path, review=True)
  import asyncio
  results = asyncio.run(_reviews(scaffolding))
  assert results[0] and results[1] and results[2] is None and results[3] is None
  assert len(checker.requests) == 2


async def _reviews(scaffolding):
  out = [await scaffolding.review('complete', {'summary': 'x'}) for _ in range(3)]
  out.append(await scaffolding.review('blocked', {'summary': 'x'}))
  await scaffolding.aclose()
  return out


def test_the_submit_tool_submits_through_the_command(tmp_path, server):
  submit = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'call_1', 'type': 'function', 'function': {
    'name': 'submit', 'arguments': json.dumps({'status': 'blocked', 'claims': {'summary': 'No 2.0.0 in the mirror fixes it.', 'verified_end_to_end': False, 'verification_commands': []}}),
  }}]}
  agent = server([{'body': {'choices': [{'message': submit, 'finish_reason': 'tool_calls'}], 'usage': USAGE}}])
  record = run(tmp_path, agent, session_options={'submit_tool': True}, task_options={'submit_tool': True})
  assert record.outcome == 'blocked' and record.submit['claims']['summary'].startswith('No 2.0.0')
  assert [tool['function']['name'] for tool in agent.requests[0]['body']['tools']] == ['bash', 'submit']


def test_the_reviewer_reads_the_agents_reasoning(tmp_path):
  record = tmp_path / 'neutral.jsonl'
  record.write_text(json.dumps({'response': {'choices': [{'message': {
    'reasoning_content': 'The tests contradict the docs here.', 'content': 'Implementing.'}}]}}) + '\n')
  text = scaffold.transcript(record, 500)
  assert '[agent reasoning]\nThe tests contradict the docs here.' in text and '[agent said]\nImplementing.' in text


from tests.task_helpers import IMAGE, docker  # noqa: E402


@docker
def test_the_verifier_checks_a_copy_in_a_container_of_its_own(tmp_path, server):
  import asyncio
  import subprocess
  workspace = tmp_path / 'workspace'
  workspace.mkdir()
  (workspace / 'note.txt').write_text('hello\n')
  checker = server([
    tool_call('cat note.txt && echo changed > note.txt && (curl -s http://example.com || echo no-network)'),
    answer(met=False, findings=['note.txt says hello, not goodbye (cat note.txt).']),
    answer(verdict='revise', problems=['The checker found note.txt says hello.'], advice='Fix note.txt.'),
  ])
  model = ModelConfig(name='fake', base_url=checker.base_url, api_key_env='FAKE_KEY', model='fake-model')
  (tmp_path / 'run').mkdir()
  from beambench.neutral import LocalShell
  scaffolding = scaffold.Scaffold(
    model, 'sk-test', 'Make note.txt say goodbye.', tmp_path / 'run', LocalShell(workspace), review=True, guard=False,
    verifier={'image': IMAGE, 'name': f'beambench-test-{tmp_path.name}', 'workspace': workspace, 'tmpfs': {}},
  )

  async def go():
    try:
      return await scaffolding.review('complete', {'summary': 'Done.'})
    finally:
      await scaffolding.aclose()

  feedback = asyncio.run(go())
  assert feedback and 'The checker found note.txt says hello.' in feedback
  assert (workspace / 'note.txt').read_text() == 'hello\n'  # The checker changed only its copy.
  outputs = [m['content'] for m in checker.requests[1]['body']['messages'] if m['role'] == 'tool']
  assert 'hello' in outputs[0] and 'no-network' in outputs[0]
  review_question = checker.requests[2]['body']['messages'][0]['content']
  assert "Goal met, in the checker's judgment: no." in review_question and 'says hello, not goodbye' in review_question
  assert scaffolding.stats['verifications'] == 1 and scaffolding.stats['verifier_commands'] == 1
  assert not (tmp_path / 'run' / 'verify-workspace').exists()
  names = subprocess.run(['docker', 'ps', '-a', '--format', '{{.Names}}'], capture_output=True, text=True).stdout
  assert f'beambench-test-{tmp_path.name}-verify' not in names


def test_a_scaffold_call_that_keeps_failing_ends_the_run_as_infrastructure(tmp_path, server):
  import asyncio
  import pytest
  from beambench.neutral import LocalShell
  from beambench.runner import ProviderError
  from tests.fake_openai import error
  checker = server([], default=error(429, 'daily_allowance_exhausted'))
  model = ModelConfig(name='fake', base_url=checker.base_url, api_key_env='FAKE_KEY', model='fake-model')
  (tmp_path / 'run').mkdir()
  scaffolding = scaffold.Scaffold(model, 'sk-test', 'Create hello.txt.', tmp_path / 'run', LocalShell(tmp_path),
                                  review=True, guard=True, retry_delay_s=0.01)

  async def go(call):
    try:
      return await call
    finally:
      await scaffolding.aclose()

  with pytest.raises(ProviderError, match='daily_allowance_exhausted'):
    asyncio.run(go(scaffolding.review('complete', {'summary': 'Done.'})))


def test_v4_tells_the_agent_its_budget_and_what_a_fresh_read_of_the_record_finds(tmp_path, server, monkeypatch):
  monkeypatch.setattr(scaffold, 'PROGRESS_AT', (2,))
  monkeypatch.setattr(scaffold, 'BUDGET_WARNING_LEFT', 3)
  checker = server([answer(verdict='redirect', problems=['It has tried three made-up tokens (commands 1-2).'],
                           advice='Stop guessing tokens; submit blocked.')])
  agent = server([tool_call('echo one', 'call_1'), tool_call('echo two', 'call_2'), tool_call('echo three', 'call_3'),
                  tool_call('echo four', 'call_4'), tool_call(submit_command(tmp_path), 'call_5'), say('Done.')])
  model = ModelConfig(name='fake', base_url=checker.base_url, api_key_env='FAKE_KEY', model='fake-model')
  (tmp_path / 'run').mkdir()
  from beambench.neutral import LocalShell
  scaffolding = scaffold.Scaffold(model, 'sk-test', 'Create hello.txt.', tmp_path / 'run', LocalShell(tmp_path),
                                  review=False, guard=False, version=4, max_steps=7)
  record = run(tmp_path, agent, session_options={'checkpoint': scaffolding.progress})
  assert record.outcome == 'complete'
  replies = [m['content'] for m in agent.requests[-1]['body']['messages'] if m['role'] == 'tool']
  assert 'tool calls' not in replies[0]
  assert '[2 of your 7 tool calls used, 5 left.' in replies[1] and 'Stop guessing tokens' in replies[1]
  assert 'tool calls' not in replies[2]
  assert replies[3].endswith('the report anything you didn\'t finish or check.]') and '[3 tool calls left.' in replies[3]
  progress_question = checker.requests[0]['body']['messages'][0]['content']
  assert 'It has used 2 of its 7 tool calls.' in progress_question and 'echo one' in progress_question
  assert scaffolding.stats == {'reviews': 0, 'revisions_asked': 0, 'guard_checks': 0, 'guard_blocks': 0,
                               'progress_checks': 1, 'progress_redirects': 1, 'budget_warnings': 1}


def test_v3_has_no_progress_check_and_v4_changes_only_what_it_says(tmp_path, server):
  checker = server([])
  v3 = checks(checker, tmp_path)
  import asyncio
  assert not v3.progress_enabled and asyncio.run(v3.progress(20)) is None
  assert scaffold.REVIEW_V4 != scaffold.REVIEW and '5. Did the checker find' in scaffold.REVIEW_V4
  assert 'guessed' in scaffold.GUARD_V4 and 'guessed' not in scaffold.GUARD
  text = scaffold.verification_text({'met': False, 'requirements': [
    {'requirement': 'Partial overlaps share the nights both stays occupy', 'source': 'docs/rooms.md',
     'result': 'not met', 'evidence': 'shared_nights(10-15, 13-18) is 3, expected 2'}],
    'claims': [{'claim': '17 tests pass', 'result': 'true', 'evidence': 'python3 -m pytest'}]})
  assert text.splitlines() == [
    "Goal met, in the checker's judgment: no.", 'Requirements it checked:',
    '- [not met] Partial overlaps share the nights both stays occupy (docs/rooms.md): shared_nights(10-15, 13-18) is 3, expected 2',
    'Claims in the report it rechecked:', '- [true] 17 tests pass: python3 -m pytest']


@docker
def test_the_v4_verifier_reads_the_record_and_runs_again_at_each_review(tmp_path, server):
  import asyncio
  workspace = tmp_path / 'workspace'
  workspace.mkdir()
  (workspace / 'note.txt').write_text('hello\n')
  run_dir = tmp_path / 'run'
  run_dir.mkdir()
  (run_dir / 'neutral.jsonl').write_text(json.dumps({'command': 'python3 -m pytest'}) + '\n'
                                         + json.dumps({'tool_result': {'content': '3 passed'}}) + '\n')
  verdict = {'met': True, 'requirements': [], 'claims': [{'claim': 'ran the tests twice', 'result': 'false',
                                                          'evidence': 'the record shows one pytest run'}]}
  checker = server([
    tool_call('grep -c pytest /record/record.txt'), answer(**verdict),
    answer(verdict='revise', problems=['The report says the tests ran twice; the record shows once.'], advice='Fix it.'),
    answer(met=True, requirements=[], claims=[]), answer(verdict='accept', problems=[], advice=''),
  ])
  model = ModelConfig(name='fake', base_url=checker.base_url, api_key_env='FAKE_KEY', model='fake-model')
  from beambench.neutral import LocalShell
  scaffolding = scaffold.Scaffold(
    model, 'sk-test', 'Make note.txt say hello.', run_dir, LocalShell(workspace), review=True, guard=False,
    verifier={'image': IMAGE, 'name': f'beambench-test-{tmp_path.name}', 'workspace': workspace, 'tmpfs': {}},
    version=4,
  )

  async def go():
    try:
      return [await scaffolding.review('complete', {'summary': 'Ran the tests twice.'}) for _ in range(2)]
    finally:
      await scaffolding.aclose()

  first, second = asyncio.run(go())
  assert first and 'the record shows once' in first and second is None
  outputs = [m['content'] for m in checker.requests[1]['body']['messages'] if m['role'] == 'tool']
  assert outputs[0].rstrip().endswith('1')  # The record was there, with one pytest command.
  assert '/record/record.txt' in checker.requests[0]['body']['messages'][1]['content']
  review_question = checker.requests[2]['body']['messages'][0]['content']
  assert '- [false] ran the tests twice: the record shows one pytest run' in review_question
  assert scaffolding.stats['verifications'] == 2
  logged = [json.loads(line) for line in (run_dir / 'scaffold.jsonl').read_text().splitlines()]
  assert logged[0]['kind'] == 'verify' and logged[0]['command_log'][0]['command'].startswith('grep -c pytest')
  assert not (run_dir / 'verify-record').exists() and not (run_dir / 'verify-workspace').exists()


def test_v5_reviews_a_blocked_report_and_v4_doesnt(tmp_path, server):
  import asyncio
  from beambench.neutral import LocalShell
  checker = server([answer(verdict='revise', problems=['The plan file still names an excluded line.'],
                           advice='Remove it, then submit blocked again.')])
  model = ModelConfig(name='fake', base_url=checker.base_url, api_key_env='FAKE_KEY', model='fake-model')
  (tmp_path / 'run').mkdir()

  async def both():
    v4 = scaffold.Scaffold(model, 'sk-test', 'Pick a line.', tmp_path / 'run', LocalShell(tmp_path), review=True,
                           guard=False, version=4)
    v5 = scaffold.Scaffold(model, 'sk-test', 'Pick a line.', tmp_path / 'run', LocalShell(tmp_path), review=True,
                           guard=False, version=5)
    out = (await v4.review('blocked', {'summary': 'No line qualifies.'}),
           await v5.review('blocked', {'summary': 'No line qualifies.'}))
    await v4.aclose()
    await v5.aclose()
    return out, v5.stats

  (v4_feedback, v5_feedback), stats = asyncio.run(both())
  assert v4_feedback is None and 'still names an excluded line' in v5_feedback and len(checker.requests) == 1
  question = checker.requests[0]['body']['messages'][0]['content']
  assert 'status: blocked' in question and "Don't question the decision to stop." in question
  assert stats['reviews'] == 1 and stats['revisions_asked'] == 1


def test_v5_looks_once_more_near_the_end_and_changes_only_what_it_says(tmp_path, server):
  import asyncio
  from beambench.neutral import LocalShell
  checker = server([answer(verdict='redirect', problems=['Four attempts failed the same way.'],
                           advice='Submit blocked now with what you found.')])
  model = ModelConfig(name='fake', base_url=checker.base_url, api_key_env='FAKE_KEY', model='fake-model')
  (tmp_path / 'run').mkdir()
  v5 = scaffold.Scaffold(model, 'sk-test', 'Pick a line.', tmp_path / 'run', LocalShell(tmp_path), review=False,
                         guard=False, version=5, max_steps=60)
  note = asyncio.run(v5.progress(50))
  asyncio.run(v5.aclose())
  assert '[50 of your 60 tool calls used, 10 left.' in note and 'Submit blocked now' in note
  assert 'near the end of its tool-call budget' in checker.requests[0]['body']['messages'][0]['content']
  assert scaffold.PROGRESS_AT == (20, 40) and scaffold.PROGRESS_AT_V5 == (20, 40, 50)
  assert '6. Does the status match the findings?' in scaffold.REVIEW_V5 and '6.' not in scaffold.REVIEW_V4.split('5. Did')[1]
  assert '5. Outputs:' in scaffold.VERIFY_V5 and '5. Outputs:' not in scaffold.VERIFY_V4


def test_v5s_late_look_keeps_v4s_budget_warning_when_it_has_nothing_to_add(tmp_path, server):
  import asyncio
  from beambench.neutral import LocalShell
  checker = server([answer(verdict='continue', problems=[], advice='')])
  model = ModelConfig(name='fake', base_url=checker.base_url, api_key_env='FAKE_KEY', model='fake-model')
  (tmp_path / 'run').mkdir()
  v5 = scaffold.Scaffold(model, 'sk-test', 'Pick a line.', tmp_path / 'run', LocalShell(tmp_path), review=False,
                         guard=False, version=5, max_steps=60)
  note = asyncio.run(v5.progress(50))
  asyncio.run(v5.aclose())
  assert note == scaffold.BUDGET_NOTE.format(left=10) and v5.stats['budget_warnings'] == 1


def test_a_stress_test_can_switch_v5_parts_off_and_reword_its_prompts(tmp_path, server):
  import asyncio
  from beambench.neutral import LocalShell
  checker = server([answer(verdict='continue', problems=[], advice='')])
  model = ModelConfig(name='fake', base_url=checker.base_url, api_key_env='FAKE_KEY', model='fake-model')
  (tmp_path / 'run').mkdir()
  prompts = tmp_path / 'reworded.toml'
  prompts.write_text('PROGRESS = "Reworded: {goal} {transcript} {used} {limit}"\n')
  make = lambda **options: scaffold.Scaffold(  # noqa: E731
    model, 'sk-test', 'Pick a line.', tmp_path / 'run', LocalShell(tmp_path), review=True, guard=False, version=5,
    options=options)
  off = make(off=['blocked_review', 'late_progress'])
  assert asyncio.run(off.review('blocked', {'summary': 'x'})) is None and not checker.requests
  assert asyncio.run(off.progress(50)) == scaffold.BUDGET_NOTE.format(left=10)  # v4's schedule: only the warning.
  reworded = make(prompts=str(prompts.relative_to(scaffold.Path(scaffold.__file__).resolve().parent.parent))
                  if prompts.is_relative_to(scaffold.Path(scaffold.__file__).resolve().parent.parent) else str(prompts))
  asyncio.run(reworded.progress(20))
  assert checker.requests[0]['body']['messages'][0]['content'].startswith('Reworded: Pick a line.')
  for each in (off, reworded):
    asyncio.run(each.aclose())
  import pytest
  with pytest.raises(AssertionError):
    make(off=['no_such_part'])
