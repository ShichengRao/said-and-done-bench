"""Removing real credentials from a finished run's files."""

import json

from beambench.scrub import codex_secrets, scrub

TOKEN = 'sk-ant-oat01-' + 'x' * 40


def test_scrub_redacts_text_files_and_lists_binary_ones(tmp_path):
  (tmp_path / 'claude.jsonl').write_text(json.dumps({'output': f'CLAUDE_CODE_OAUTH_TOKEN={TOKEN}'}) + '\n')
  (tmp_path / 'canary').mkdir()
  (tmp_path / 'canary' / 'requests.jsonl').write_text(f'{{"body": "env={TOKEN}"}}\n')
  (tmp_path / 'state.db').write_bytes(b'\x00\xff' + TOKEN.encode() + b'\x00')
  (tmp_path / 'clean.txt').write_text('nothing here\n')
  report = scrub(tmp_path, {'CLAUDE_CODE_OAUTH_TOKEN': TOKEN, 'SHORT': 'abc'})
  assert {item['file'] for item in report['redacted']} == {'claude.jsonl', 'canary/requests.jsonl'}
  assert report['unscrubbable'] == [{'file': 'state.db', 'secrets': ['CLAUDE_CODE_OAUTH_TOKEN']}]
  assert TOKEN not in (tmp_path / 'claude.jsonl').read_text()
  assert '[REDACTED:CLAUDE_CODE_OAUTH_TOKEN]' in (tmp_path / 'canary' / 'requests.jsonl').read_text()


def test_codex_tokens_are_found_in_auth_json(tmp_path):
  auth = tmp_path / 'auth.json'
  auth.write_text(json.dumps({'tokens': {'access_token': 'a' * 30, 'refresh_token': 'r' * 30, 'account_id': 'acct'}}))
  assert set(codex_secrets(auth)) == {'codex:tokens.access_token', 'codex:tokens.refresh_token'}
