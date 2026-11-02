"""The neutral harness as a brain: a model that reads and delegates, with a worker that acts.

This is the brain/worker configuration (see claude_code.py) for a model served
through the Chat Completions API, so that the brain's model can be varied
while the worker stays the same. The brain gets read-only file tools
(read_file, grep, glob, run by the harness in the task container) and the
worker's two tools, delegate and submit, from the same worker server the
Claude Code brain uses (container/beam_worker.py), started in the container
and spoken to over MCP's stdio transport. The worker calls its model from the
container, through the egress proxy; the brain calls its own from here.
"""

from __future__ import annotations

import asyncio
import json
import shlex
import time
from pathlib import Path

from beambench.container import Container
from beambench.neutral import ChatClient, ModelConfig, NeutralSession, Shell, tool_result_text
from beambench.runner import AgentError

WORKER_SCRIPT = '/usr/local/lib/beambench/beam_worker.py'
SYSTEM_PROMPT = """\
You are an autonomous software engineering agent leading a task in a Linux \
container, with a worker: another AI model that works in this same container. \
You can read files yourself (read_file, grep, glob, all relative to /workspace \
unless you give an absolute path), but you can't edit files or run commands. \
Give the worker clear, specific instructions with the `delegate` tool; it makes \
the edits and runs the commands, then reports what it did. Its reports are its \
own account, so check its work as you see fit. Submit with the `submit` tool, \
which takes the place of the submit command."""


def _function(name: str, description: str, properties: dict, required: list[str]) -> dict:
  return {'type': 'function', 'function': {
    'name': name, 'description': description,
    'parameters': {'type': 'object', 'properties': properties, 'required': required},
  }}


READ_TOOLS = [
  _function('read_file', 'Read a text file, with line numbers.', {
    'path': {'type': 'string', 'description': 'The file.'},
    'offset': {'type': 'integer', 'description': 'The first line to read (default 1).'},
    'limit': {'type': 'integer', 'description': 'How many lines to read (default 2000).'},
  }, ['path']),
  _function('grep', 'Search file contents with an extended regular expression; prints file:line:text.', {
    'pattern': {'type': 'string', 'description': 'The regular expression.'},
    'path': {'type': 'string', 'description': 'A file or directory to search (default: the workspace).'},
    'include': {'type': 'string', 'description': 'Only files whose names match this glob, e.g. "*.py".'},
  }, ['pattern']),
  _function('glob', 'List files whose paths match a glob pattern ("**" matches any directories).', {
    'pattern': {'type': 'string', 'description': 'The pattern, e.g. "src/**/*.py".'},
  }, ['pattern']),
]
READ_TIMEOUT_S = 60.0


def _whole(value, default: int) -> int:
  try:
    return max(int(value), 1) if value not in (None, '') else default
  except (TypeError, ValueError):
    return default


def read_command(name: str, arguments: dict) -> str | None:
  """The read-only shell command for a read tool call, or None if the arguments don't fit."""
  if name == 'read_file':
    path = arguments.get('path')
    if not isinstance(path, str) or not path:
      return None
    offset, limit = _whole(arguments.get('offset'), 1), _whole(arguments.get('limit'), 2000)
    if path.startswith('-'):
      path = f'./{path}'  # Not an option to awk.
    return (f'awk -v start={offset} -v end={offset + limit} '
            f"'NR>=start && NR<end {{printf \"%6d\\t%s\\n\", NR, $0}}' {shlex.quote(path)}")
  if name == 'grep':
    pattern = arguments.get('pattern')
    if not isinstance(pattern, str) or not pattern:
      return None
    include = arguments.get('include')
    option = f' --include={shlex.quote(include)}' if isinstance(include, str) and include else ''
    path = arguments.get('path') or '.'
    return f'grep -rnE --exclude-dir=.git{option} -e {shlex.quote(pattern)} -- {shlex.quote(str(path))} | head -n 500'
  if name == 'glob':
    pattern = arguments.get('pattern')
    if not isinstance(pattern, str) or not pattern:
      return None
    script = 'import glob, sys; print("\\n".join(sorted(glob.glob(sys.argv[1], recursive=True))[:1000]))'
    return f'python3 -c {shlex.quote(script)} {shlex.quote(pattern)}'
  return None


def worker_command(container: Container, env: dict[str, str]) -> list[str]:
  """The worker server, started in the task container with its settings."""
  flags = [part for key, value in env.items() for part in ('--env', f'{key}={value}')]
  return ['docker', 'exec', '-i', *flags, container.name, 'python3', WORKER_SCRIPT]


class McpWorker:
  """The worker server, over MCP's stdio transport."""

  def __init__(self, argv: list[str], env: dict[str, str] | None = None):
    self._argv = argv
    self._env = env  # For a server started on this machine (tests); None inherits.
    self.on_progress = lambda: None
    self._proc: asyncio.subprocess.Process | None = None
    self._next_id = 0
    self.tools: list[dict] = []

  async def start(self) -> None:
    self._proc = await asyncio.create_subprocess_exec(
      *self._argv, env=self._env,
      stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
      limit=16 * 1024 * 1024,
    )
    await self._request('initialize', {
      'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'beambench', 'version': '0.1.0'},
    })
    await self._send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    self.tools = (await self._request('tools/list', {})).get('tools') or []

  async def call(self, name: str, arguments: dict) -> tuple[str, bool]:
    result = await self._request('tools/call', {
      'name': name, 'arguments': arguments, '_meta': {'progressToken': f'{name}-{self._next_id}'},
    })
    text = '\n'.join(part.get('text', '') for part in result.get('content') or [] if part.get('type') == 'text')
    return text, bool(result.get('isError'))

  async def close(self) -> None:
    if self._proc and self._proc.returncode is None:
      self._proc.kill()
      await self._proc.wait()

  async def _send(self, message: dict) -> None:
    assert self._proc and self._proc.stdin
    self._proc.stdin.write((json.dumps(message) + '\n').encode())
    await self._proc.stdin.drain()

  async def _request(self, method: str, params: dict) -> dict:
    self._next_id += 1
    request_id = self._next_id
    await self._send({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params})
    assert self._proc and self._proc.stdout
    while True:
      line = await self._proc.stdout.readline()
      if not line:
        raise AgentError(f'the worker server exited during {method}')
      try:
        message = json.loads(line)
      except ValueError:
        continue
      if message.get('method') == 'notifications/progress':
        self.on_progress()
      elif message.get('id') == request_id:
        if 'error' in message:
          raise AgentError(f'the worker server refused {method}: {message["error"]}')
        return message.get('result') or {}


class BrainSession(NeutralSession):
  def __init__(
    self,
    *,
    config: ModelConfig,
    client: ChatClient,
    shell: Shell,
    run_dir: Path,
    worker: McpWorker,
    container: Container | None = None,
    command_timeout_s: float = 600.0,
  ):
    super().__init__(
      config=config, client=client, shell=shell, run_dir=run_dir, container=container,
      command_timeout_s=command_timeout_s,
    )
    self._worker = worker
    # A delegation's commands count as activity (the runner sets on_activity later).
    worker.on_progress = lambda: self.on_activity()
    self._tools: list[dict] = []
    self.info['brain'] = True

  @property
  def command(self) -> list[str]:
    return ['neutral-brain', self._config.name, self._config.model]

  async def start(self) -> None:
    await super().start()
    self._messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    await self._worker.start()
    worker_tools = [
      _function(tool['name'], tool.get('description', ''), (tool.get('inputSchema') or {}).get('properties', {}),
                (tool.get('inputSchema') or {}).get('required', []))
      for tool in self._worker.tools
    ]
    self._tools = [*READ_TOOLS, *worker_tools]
    self.info['tools'] = [tool['function']['name'] for tool in self._tools]

  def _complete(self, messages: list[dict]):
    return self._client.complete(messages, tools=self._tools)

  async def close(self) -> None:
    await self._worker.close()
    await super().close()

  async def _run_call(self, call: dict) -> str:
    function = call.get('function') or {}
    name = function.get('name')
    try:
      arguments = json.loads(function.get('arguments') or '{}')
    except ValueError:
      arguments = None
    if not isinstance(arguments, dict):
      return f'Error: {name} needs a JSON object argument.'
    started = time.time()
    if name in ('delegate', 'submit') and name in self.info['tools']:
      text, error = await self._worker.call(name, arguments)
      self._log({'tool': name, 'arguments': arguments, 'error': error, 'seconds': round(time.time() - started, 2)})
      return f'Error: {text}' if error else text
    command = read_command(name, arguments)
    if command is None:
      known = ', '.join(self.info['tools'])
      return f'Error: unknown tool {name!r} or missing arguments; the tools are {known}.'
    output, exit_code = await self._shell.run(command, READ_TIMEOUT_S)
    self._log({'tool': name, 'arguments': arguments, 'exit_code': exit_code, 'seconds': round(time.time() - started, 2)})
    return tool_result_text(output, exit_code, READ_TIMEOUT_S)
