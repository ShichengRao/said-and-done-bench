"""Codex CLI as an AgentSession: one `codex exec --json` process per turn.

The first turn starts a thread and later turns `codex exec resume` it.
Commands run without approvals or Codex's own sandboxing
(--dangerously-bypass-approvals-and-sandbox); the container is the sandbox.
Web search is off because tasks are offline, and so is every feature that
runs tools on OpenAI's side or acts on the ChatGPT account (DISABLED_FEATURES):
ChatGPT apps alone add about a hundred tools, among them a search service and
site deployment, which the run's egress proxy can't see. --strict-config makes
a mistyped setting fail the run instead of being ignored.

Codex signs in with a ChatGPT account through `codex login --device-auth`,
which writes auth.json. Each run gets a copy in its CODEX_HOME; if Codex
refreshes the sign-in during the run, the new auth.json replaces the stored
one, and the run's copy is deleted so run directories hold no credentials.
Run Codex tasks one at a time: parallel runs could each refresh the sign-in
and invalidate the other's.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Sequence
from pathlib import Path

from beambench.container import Container
from beambench.headless import HeadlessCliSession
from beambench.runner import AgentError, ProviderError, TurnEnd

DEFAULT_MODEL = 'gpt-6.1-sol'
STATE_DIR = '/harness/codex'
CONTAINER_ENV = {'CODEX_HOME': STATE_DIR}
# The only hosts Codex may reach from a run's container (see sidecars.Egress):
# the ChatGPT backend it calls, and the sign-in service that refreshes its token.
EGRESS_HOSTS = ('chatgpt.com', 'auth.openai.com')
AUTH_DIR = Path(
  os.environ.get('BEAMBENCH_CODEX_AUTH', Path.home() / '.config' / 'beambench' / 'codex')
)
# Items that aren't tool calls; any other item type counts as a step.
_NOT_TOOL_CALLS = frozenset({'agent_message', 'reasoning', 'error', 'user_message'})


# Features that would give Codex tools beyond its shell and file edits: ChatGPT
# apps and plugins (run on OpenAI's servers), a browser, computer use, and
# image generation, plus suggestions and installs that would fetch more.
DISABLED_FEATURES = (
  'apps', 'plugins', 'remote_plugin', 'plugin_sharing', 'tool_suggest', 'skill_mcp_dependency_install',
  'browser_use', 'browser_use_external', 'computer_use', 'image_generation',
)


def codex_args(thread_id: str | None, *, model: str, effort: str) -> list[str]:
  options = [
    '--json', '--strict-config', '--skip-git-repo-check',
    '--dangerously-bypass-approvals-and-sandbox',
    '-m', model,
    '-c', f'model_reasoning_effort="{effort}"',
    '-c', 'web_search="disabled"',
  ]
  for feature in DISABLED_FEATURES:
    options += ['--disable', feature]
  if thread_id is None:
    return ['exec', *options, '-']
  return ['exec', 'resume', *options, thread_id, '-']


class CodexSession(HeadlessCliSession):
  transcript_name = 'codex.jsonl'

  def __init__(
    self,
    *,
    run_dir: Path,
    model: str = DEFAULT_MODEL,
    effort: str = 'max',
    container: Container | None = None,
    executable: Sequence[str] = ('codex',),
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    codex_home: Path | None = None,
    auth_file: Path | None = None,
  ):
    """codex_home is this run's CODEX_HOME on this machine; auth_file is the stored sign-in."""
    super().__init__(run_dir=run_dir, container=container, executable=executable, env=env, cwd=cwd)
    self._model = model
    self._effort = effort
    self._codex_home = codex_home
    self._auth_file = auth_file
    self._thread_id: str | None = None
    self._usage: dict | None = None
    self._completed = False
    self._failure: str | None = None
    self.info = {'model': model, 'effort': effort}

  async def start(self) -> None:
    if self._codex_home and self._auth_file:
      self._codex_home.mkdir(parents=True, exist_ok=True)
      copy = self._codex_home / 'auth.json'
      shutil.copyfile(self._auth_file, copy)
      copy.chmod(0o600)
    await super().start()

  async def close(self) -> None:
    await super().close()
    self._return_auth()
    self._remove_state_databases()

  def begin_turn(self) -> None:
    self._usage = None
    self._completed = False
    self._failure = None

  def turn_args(self, *, first_turn: bool) -> list[str]:
    return codex_args(None if first_turn else self._thread_id, model=self._model, effort=self._effort)

  def on_event(self, event: dict) -> None:
    kind = event.get('type')
    if kind == 'thread.started':
      self._thread_id = event.get('thread_id')
      self.info['thread_id'] = self._thread_id
    elif kind in ('item.started', 'item.updated', 'item.completed'):
      item = event.get('item') or {}
      if item.get('type') == 'error':
        warnings = self.info.setdefault('warnings', [])
        if item.get('message') not in warnings and len(warnings) < 10:
          warnings.append(item.get('message'))
      elif item.get('id') and item.get('type') not in _NOT_TOOL_CALLS:
        # Item ids restart in each resumed process, so key them by turn.
        self.on_step(f'{self.turn_number}:{item["id"]}')
    elif kind == 'turn.completed':
      self._completed = True
      self._usage = event.get('usage')
    elif kind == 'turn.failed':
      self._failure = str((event.get('error') or {}).get('message'))

  def end_turn(self, returncode: int, cancelled: bool) -> TurnEnd:
    if cancelled:
      return TurnEnd('cancelled', self._usage)
    if self._failure:
      # At capacity, usage limits, auth: Codex reports these as a failed turn.
      raise ProviderError(f'codex turn failed: {self._failure[:300]}')
    if not self._completed:
      raise AgentError(f'codex exited with code {returncode} without finishing the turn')
    return TurnEnd('completed', self._usage)

  def _remove_state_databases(self) -> None:
    """Delete Codex's SQLite state from the run's CODEX_HOME.

    It holds token strings from the sign-in, and SQLite files can't be
    scrubbed in place; the transcript is in codex.jsonl and the session file.
    """
    if not self._codex_home:
      return
    for path in self._codex_home.glob('*.sqlite*'):
      path.unlink(missing_ok=True)

  def _return_auth(self) -> None:
    """Keep a sign-in Codex refreshed during the run, then delete the run's copy."""
    if not (self._codex_home and self._auth_file):
      return
    copy = self._codex_home / 'auth.json'
    if not copy.exists():
      return
    if copy.read_bytes() != self._auth_file.read_bytes():
      temporary = self._auth_file.with_name(self._auth_file.name + '.tmp')
      shutil.copyfile(copy, temporary)
      temporary.chmod(0o600)
      os.replace(temporary, self._auth_file)
      self.info['auth_refreshed'] = True
    copy.unlink()
