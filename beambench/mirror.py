"""Mirror (or any ACP agent) as an AgentSession.

`mirror acp` starts sessions without extensions, so the run loop plays the
/goal extension's part: it sends the kickoff and "continue" prompts and
detects completion through the `submit` command instead of a tool. One ACP
process serves the whole run; a turn is one session/prompt request.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from beambench import HARNESS_VERSION
from beambench.acp import PROTOCOL_VERSION, AcpConnection
from beambench.container import Container
from beambench.acp import AcpError
from beambench.runner import AgentError, AgentSession, TurnEnd

API_KEY_ENV = 'REFLECTION_API_KEY'
STATE_DIR = '/harness/mirror'
CONTAINER_ENV: dict[str, str] = {}
# The only hosts Mirror may reach from a run's container (see sidecars.Egress).
EGRESS_HOSTS = ('api.reflection.ai',)


def mirror_command(database: str) -> list[str]:
  """Mirror at max effort, with its state in `database`, not ~/.mirror."""
  return ['mirror', '--no-update', '--reasoning-effort', 'max', '--database', database, 'acp']


class AcpSession(AgentSession):
  def __init__(
    self,
    command: Sequence[str],
    *,
    agent_cwd: str,
    run_dir: Path,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    container: Container | None = None,
  ):
    """command runs the agent; with a container, it's wrapped in docker exec.

    agent_cwd is the workspace as the agent sees it, sent in session/new.
    """
    super().__init__()
    self._command = container.exec_command(command) if container else list(command)
    self._agent_cwd = agent_cwd
    self._container = container
    self.container = container
    self._conn = AcpConnection(
      self._command,
      env=env,
      cwd=cwd,
      transcript_path=run_dir / 'acp.jsonl',
      stderr_path=run_dir / 'agent-stderr.log',
    )
    self._conn.on_notification('session/update', self._on_update)
    self._conn.on_request('session/request_permission', self._on_permission_request)
    self._session_id: str | None = None

  @property
  def command(self) -> list[str]:
    return self._command

  async def start(self) -> None:
    if self._container:
      await self._container.start()
    await self._conn.start()
    init = await self._conn.request('initialize', {
      'protocolVersion': PROTOCOL_VERSION,
      'clientCapabilities': {
        'fs': {'readTextFile': False, 'writeTextFile': False},
        'terminal': False,
      },
      'clientInfo': {'name': 'beambench', 'version': HARNESS_VERSION},
    })
    self.info = {
      key: init.get(key)
      for key in ('protocolVersion', 'agentInfo', 'agentCapabilities', 'authMethods')
    }
    session = await self._conn.request('session/new', {'cwd': self._agent_cwd, 'mcpServers': []})
    self._session_id = session['sessionId']
    self.info['models'] = session.get('models')

  async def prompt(self, text: str) -> TurnEnd:
    try:
      response = await self._conn.request('session/prompt', {
        'sessionId': self._session_id,
        'prompt': [{'type': 'text', 'text': text}],
      }) or {}
    except AcpError as error:
      raise AgentError(str(error)) from error
    return TurnEnd(str(response.get('stopReason')), response.get('usage'))

  async def cancel(self) -> None:
    await self._conn.notify('session/cancel', {'sessionId': self._session_id})

  async def close(self) -> None:
    await self._conn.close()
    if self._container:
      await self._container.remove()

  def _on_update(self, params: dict) -> None:
    self.on_activity()
    update = params.get('update') or {}
    if update.get('sessionUpdate') not in ('tool_call', 'tool_call_update'):
      return
    call_id = update.get('toolCallId')
    # Mirror reports the process behind a bash call as its own `task:<n>`
    # tool call; a step is a call the model made, so skip those.
    if call_id and not call_id.startswith('task:'):
      self.on_step(call_id)

  async def _on_permission_request(self, params: dict) -> dict:
    self.on_activity()
    allowed = self.on_permission(params.get('toolCall') or {})
    if allowed is not None:
      kinds = ('allow_once', 'allow_always') if allowed else ('reject_once', 'reject_always')
      for kind in kinds:
        for option in params.get('options') or []:
          if option.get('kind') == kind:
            return {'outcome': {'outcome': 'selected', 'optionId': option['optionId']}}
    return {'outcome': {'outcome': 'cancelled'}}
