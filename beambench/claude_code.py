"""Claude Code as an AgentSession: one `claude -p` process per turn.

The first turn starts a session with a fixed --session-id and later turns
--resume it, so every nudge continues the same conversation. Tool calls run
without approval prompts (bypassPermissions); the container is the sandbox.
Web search and fetch are off because tasks are offline, and MCP servers come
only from --mcp-config, so connectors on the Claude account don't load.

Claude Code signs in with a subscription token (CLAUDE_CODE_OAUTH_TOKEN) or
an API key (ANTHROPIC_API_KEY), which bills by the token and reports each
turn's cost; the benchmark uses the key so Claude's cost compares with the
other models'.

As a brain (the brain/worker configuration) it keeps only its file-reading
tools and gets a worker model through an MCP server
(container/beam_worker.py): it reads, plans, delegates every edit and command
to the worker, checks the results, and submits with the server's tool.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from pathlib import Path

from beambench.container import Container
from beambench.headless import HeadlessCliSession
from beambench.runner import AgentError, ProviderError, TurnEnd

TOKEN_ENV = 'CLAUDE_CODE_OAUTH_TOKEN'  # From `claude setup-token` (subscription).
API_KEY_ENV = 'ANTHROPIC_API_KEY'  # Billed by the token; used instead of a subscription when set.
DEFAULT_MODEL = 'claude-opus-5-5'
STATE_DIR = '/harness/claude'
# The only hosts Claude Code may reach from a run's container (see sidecars.Egress).
EGRESS_HOSTS = ('api.anthropic.com',)
CONTAINER_ENV = {
  'CLAUDE_CONFIG_DIR': STATE_DIR,  # Keeps Claude Code's own transcripts in the run directory.
  'DISABLE_AUTOUPDATER': '1',
  'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
  'BASH_MAX_TIMEOUT_MS': '600000',  # The per-command deadline.
  'ENABLE_CLAUDEAI_MCP_SERVERS': 'false',  # No claude.ai connectors (see --strict-mcp-config).
}


BRAIN_TOOLS = 'Read,Grep,Glob'
BRAIN_PROMPT = """\
You lead this task with a worker: another AI model that works in this same \
container. You can read files yourself (Read, Grep, Glob), but you can't edit \
files or run commands. Give the worker clear, specific instructions with the \
`delegate` tool; it makes the edits and runs the commands, then reports what \
it did. Its reports are its own account, so check its work as you see fit. \
Submit with the `submit` tool, which takes the place of the submit command."""


def claude_flags(
  session_id: str, *, first_turn: bool, model: str, effort: str, brain_mcp_config: str | None = None,
) -> list[str]:
  flags = [
    '-p', '--output-format', 'stream-json', '--verbose',
    '--model', model, '--effort', effort,
    '--permission-mode', 'bypassPermissions',
    '--disallowedTools', 'WebSearch,WebFetch',
    '--strict-mcp-config',
  ]
  if brain_mcp_config:
    flags += ['--tools', BRAIN_TOOLS, '--mcp-config', brain_mcp_config, '--append-system-prompt', BRAIN_PROMPT]
  return [*flags, '--session-id' if first_turn else '--resume', session_id]


class ClaudeCodeSession(HeadlessCliSession):
  transcript_name = 'claude.jsonl'

  def __init__(
    self,
    *,
    run_dir: Path,
    model: str = DEFAULT_MODEL,
    effort: str = 'max',
    container: Container | None = None,
    executable: Sequence[str] = ('claude',),
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    brain_mcp_config: str | None = None,  # The worker server's config, as the container sees it.
    activity_files: Sequence[Path] = (),
  ):
    super().__init__(
      run_dir=run_dir, container=container, executable=executable, env=env, cwd=cwd,
      activity_files=activity_files,
    )
    self._model = model
    self._effort = effort
    self._brain_mcp_config = brain_mcp_config
    self._billed = 0.0  # The session's total_cost_usd so far: a running total across --resume.
    self._session_id = str(uuid.uuid4())
    self._result: dict | None = None
    self.info = {'session_id': self._session_id, 'model': model, 'effort': effort}

  def begin_turn(self) -> None:
    self._result = None

  def turn_args(self, *, first_turn: bool) -> list[str]:
    return claude_flags(
      self._session_id, first_turn=first_turn, model=self._model, effort=self._effort,
      brain_mcp_config=self._brain_mcp_config,
    )

  def on_event(self, event: dict) -> None:
    kind = event.get('type')
    if kind == 'system' and event.get('subtype') == 'init':
      self.info['init'] = {
        key: event.get(key) for key in ('model', 'claude_code_version', 'permissionMode', 'tools')
      }
    elif kind == 'assistant':
      for block in (event.get('message') or {}).get('content') or []:
        if block.get('type') == 'tool_use' and block.get('id'):
          self.on_step(block['id'])
    elif kind == 'result':
      self._result = event

  def end_turn(self, returncode: int, cancelled: bool) -> TurnEnd:
    result = self._result or {}
    usage = dict(result.get('usage') or {})  # Tokens are this turn's.
    total = result.get('total_cost_usd')
    if isinstance(total, (int, float)):
      # What the API billed, with an API key. Claude Code reports the session's
      # running total, so this turn's cost is the increase.
      usage['cost_usd'] = max(total - self._billed, 0.0)
      self._billed = max(total, self._billed)
    if cancelled:
      return TurnEnd('cancelled', usage)
    if not result:
      raise AgentError(f'claude exited with code {returncode} without a result')
    if result.get('is_error'):
      # Overloaded, usage limit, rejected model: Claude Code reports these as errors.
      raise ProviderError(
        f'claude reported an error ({result.get("subtype")}): {str(result.get("result"))[:300]}'
      )
    return TurnEnd(str(result.get('subtype')), usage)
