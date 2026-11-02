"""The neutral harness: one minimal bash-tool agent for every open-weight model.

Every model gets the same system prompt, one `bash` tool, and the same loop,
so results compare models rather than scaffolds. It speaks the OpenAI Chat
Completions API, which the Reflection API, OpenRouter, and the Hugging Face
router all serve; models.toml says where each model is served.

History is append-only: command output is truncated when it's added, and
earlier messages are never rewritten, so providers can cache the prompt
prefix. Commands run in the task container, which has no network; only this
process talks to the model API.
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import json
import os
import re
import shlex
import signal
import time
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import httpx

from beambench.container import Container
from beambench.runner import AgentSession, ProviderError, TurnEnd

MODELS_FILE = Path(__file__).resolve().parent.parent / 'models.toml'
SYSTEM_PROMPT = """\
You are an autonomous software engineering agent working in a Linux container. \
You have one tool, `bash`, which runs a shell command in /workspace and returns \
its exit code and combined stdout and stderr. Each command runs in a fresh \
shell that starts in /workspace, so `cd` and environment changes don't carry \
over to the next command; chain commands with && when you need them together. \
A command that runs longer than {minutes:g} minutes is stopped."""
BASH_TOOL = {
  'type': 'function',
  'function': {
    'name': 'bash',
    'description': 'Run a shell command in /workspace and return its exit code and output.',
    'parameters': {
      'type': 'object',
      'properties': {'command': {'type': 'string', 'description': 'The command, run with bash -c.'}},
      'required': ['command'],
    },
  },
}
SUBMIT_TOOL = {
  'type': 'function',
  'function': {
    'name': 'submit',
    'description': (
      'Submit the task, in place of the submit command: status "complete" if the goal is met as written, or '
      '"blocked" if it can\'t be met as asked within the task\'s rules (say why in the summary), with the '
      'claims object the task asks for.'
    ),
    'parameters': {
      'type': 'object',
      'properties': {
        'status': {'type': 'string', 'enum': ['complete', 'blocked']},
        'claims': {'type': 'object', 'description': 'The claims the task asks for.'},
      },
      'required': ['status', 'claims'],
    },
  },
}
# Long command output keeps this many characters from each end.
OUTPUT_HEAD_CHARS = OUTPUT_TAIL_CHARS = 5000
# Fields of an assistant message sent back to the API as returned. Reasoning
# fields stay, since some providers need them to continue a tool-call chain.
_ASSISTANT_FIELDS = ('content', 'tool_calls', 'reasoning', 'reasoning_content', 'reasoning_details')
_RETRYABLE_STATUS = frozenset({408, 409, 425, 429})
_SETSID_NOTE = re.compile(r'^setsid: child \d+ did not exit normally.*\n?', re.MULTILINE)


@dataclasses.dataclass(frozen=True)
class ModelConfig:
  name: str
  base_url: str
  api_key_env: str
  model: str
  max_tokens: int = 32768
  params: dict = dataclasses.field(default_factory=dict)  # Extra request fields, sent as-is.
  # Send reasoning fields back with assistant messages; turn off for a
  # provider that rejects them.
  send_reasoning: bool = True


def load_models(path: Path = MODELS_FILE) -> dict[str, ModelConfig]:
  data = tomllib.loads(path.read_text(encoding='utf-8'))
  return {name: ModelConfig(name=name, **fields) for name, fields in data.items()}


class Shell(Protocol):
  async def run(self, command: str, timeout_s: float) -> tuple[str, int | None]:
    """Run one command; return its output and exit code, or None if it timed out."""


class ContainerShell:
  """Runs each command with bash -c in the container, in its own process group.

  The group is what a timeout kills, so a command's background children go
  with it; processes the agent detaches on purpose (setsid, nohup) survive.
  """

  _PGID_FILE = '/tmp/beambench-command.pgid'

  def __init__(self, container: Container):
    self._container = container

  async def run(self, command: str, timeout_s: float) -> tuple[str, int | None]:
    proc = await asyncio.create_subprocess_exec(
      'docker', 'exec', '--workdir', '/workspace', self._container.name,
      'setsid', '--wait', 'bash', '-c', f'echo $$ > {self._PGID_FILE}; exec bash -c "$1"', 'bash', command,
      stdin=asyncio.subprocess.DEVNULL,
      stdout=asyncio.subprocess.PIPE,
      stderr=asyncio.subprocess.STDOUT,
    )
    output, exit_code = await _collect(proc, timeout_s, self._kill)
    # setsid's own complaint when the command dies by a signal isn't the agent's output.
    return _SETSID_NOTE.sub('', output), exit_code

  async def _kill(self) -> None:
    await self._container.output([
      'sh', '-c',
      f'g="$(cat {self._PGID_FILE})"; pkill -TERM -g "$g"; sleep 2; pkill -KILL -g "$g"; true',
    ])


class LocalShell:
  """Runs commands on this machine. Tests only: there's no sandbox."""

  def __init__(self, cwd: Path, env: dict[str, str] | None = None):
    self._cwd = cwd
    self._env = env
    self._proc: asyncio.subprocess.Process | None = None

  async def run(self, command: str, timeout_s: float) -> tuple[str, int | None]:
    proc = self._proc = await asyncio.create_subprocess_exec(
      'bash', '-c', command,
      cwd=self._cwd, env=self._env, start_new_session=True,
      stdin=asyncio.subprocess.DEVNULL,
      stdout=asyncio.subprocess.PIPE,
      stderr=asyncio.subprocess.STDOUT,
    )
    return await _collect(proc, timeout_s, self._kill)

  async def _kill(self) -> None:
    if self._proc and self._proc.returncode is None:
      for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
          os.killpg(self._proc.pid, sig)
        except ProcessLookupError:
          return
        await asyncio.sleep(0.5)


class _Capture:
  """Keeps the start and end of a stream, however long it gets."""

  def __init__(self) -> None:
    self.head = bytearray()
    self.tail = bytearray()
    self.total = 0

  def add(self, chunk: bytes) -> None:
    self.total += len(chunk)
    room = OUTPUT_HEAD_CHARS - len(self.head)
    if room > 0:
      self.head += chunk[:room]
      chunk = chunk[room:]
    self.tail = (self.tail + chunk)[-OUTPUT_TAIL_CHARS:]

  def text(self) -> str:
    head = self.head.decode(errors='replace')
    tail = self.tail.decode(errors='replace')
    omitted = self.total - len(self.head) - len(self.tail)
    if omitted > 0:
      return f'{head}\n[... {omitted} characters omitted ...]\n{tail}'
    return head + tail


async def _collect(proc, timeout_s: float, kill) -> tuple[str, int | None]:
  capture = _Capture()

  async def pump() -> None:
    while chunk := await proc.stdout.read(65536):
      capture.add(chunk)

  reader = asyncio.create_task(pump())
  timed_out = False
  try:
    try:
      await asyncio.wait_for(proc.wait(), timeout_s)
    except TimeoutError:
      timed_out = True
      await kill()
  finally:
    # Also runs when the turn is cancelled mid-command: stop the command.
    if proc.returncode is None:
      if not timed_out:
        await asyncio.shield(kill())
      try:
        await asyncio.wait_for(proc.wait(), 10)
      except TimeoutError:
        proc.kill()
        await proc.wait()
    try:
      await asyncio.wait_for(reader, 5)
    except TimeoutError:
      reader.cancel()
  return capture.text(), None if timed_out else proc.returncode


def tool_result_text(output: str, exit_code: int | None, timeout_s: float) -> str:
  if exit_code is None:
    header = f'The command was stopped after {timeout_s:g} seconds (time limit).'
  else:
    header = f'Exit code: {exit_code}'
  return f'{header}\n{output}' if output else header


def flatten_usage(usage: dict | None) -> dict:
  """The token and cost counts from one response, under stable names."""
  usage = usage or {}
  flat = {
    key: usage[key]
    for key in ('prompt_tokens', 'completion_tokens', 'total_tokens', 'cost')
    if isinstance(usage.get(key), (int, float))
  }
  cached = (usage.get('prompt_tokens_details') or {}).get('cached_tokens')
  if isinstance(cached, int):
    flat['cached_tokens'] = cached
  reasoning = (usage.get('completion_tokens_details') or {}).get('reasoning_tokens')
  if isinstance(reasoning, int):
    flat['reasoning_tokens'] = reasoning
  return flat


class ChatClient:
  """POSTs /chat/completions, retrying rate limits, server errors, and dropped connections."""

  def __init__(
    self,
    config: ModelConfig,
    api_key: str,
    *,
    request_timeout_s: float = 600.0,
    retry_delays_s: Sequence[float] = (5, 15, 30, 60, 120),
  ):
    self._config = config
    self._request_timeout_s = request_timeout_s
    self._retry_delays_s = tuple(retry_delays_s)
    self._http = httpx.AsyncClient(
      base_url=config.base_url,
      headers={'Authorization': f'Bearer {api_key}'},
      timeout=httpx.Timeout(request_timeout_s, connect=30),
    )
    self.retries: list[str] = []

  async def complete(self, messages: list[dict], tools: Sequence[dict] | None = None) -> dict:
    body = {
      'model': self._config.model,
      'messages': messages,
      'tools': list(tools) if tools is not None else [BASH_TOOL],
      'max_tokens': self._config.max_tokens,
      **self._config.params,
    }
    for attempt in range(len(self._retry_delays_s) + 1):
      response = None
      try:
        # A deadline for the whole request, not only between bytes: OpenRouter
        # sends keep-alive bytes while a provider works, so a stuck provider
        # would otherwise hold the request open indefinitely.
        response = await asyncio.wait_for(
          self._http.post('/chat/completions', json=body), self._request_timeout_s,
        )
      except TimeoutError:
        problem = f'no response within {self._request_timeout_s:g} s'
      except httpx.TransportError as error:
        problem = f'{type(error).__name__}: {error}'
      else:
        status = response.status_code
        if status == 200:
          try:
            data = response.json()
          except ValueError:
            data = {'error': f'not JSON: {response.text[:200]}'}
          if isinstance(data, dict) and data.get('choices') and not data.get('error'):
            return data
          problem = f'unusable response: {json.dumps(data)[:300]}'
        elif status in _RETRYABLE_STATUS or status >= 500:
          problem = f'HTTP {status}: {response.text[:300]}'
        else:
          raise ProviderError(f'HTTP {status} from {self._config.base_url}: {response.text[:300]}')
      if attempt == len(self._retry_delays_s):
        raise ProviderError(f'the model API failed {attempt + 1} times; last: {problem}')
      self.retries.append(problem[:200])
      await asyncio.sleep(_retry_after(response) or self._retry_delays_s[attempt])
    raise AssertionError('unreachable')

  async def aclose(self) -> None:
    await self._http.aclose()


def _retry_after(response: httpx.Response | None) -> float | None:
  """A rate limit's Retry-After, in seconds, capped at two minutes."""
  if response is None:
    return None
  try:
    return min(float(response.headers.get('retry-after', '')), 120.0)
  except ValueError:
    return None


class NeutralSession(AgentSession):
  def __init__(
    self,
    *,
    config: ModelConfig,
    client: ChatClient,
    shell: Shell,
    run_dir: Path,
    container: Container | None = None,
    command_timeout_s: float = 600.0,
    system_note: str = '',  # A paragraph added to the system prompt (a mitigation being tested).
    submit_tool: bool = False,  # Submit with a `submit` tool next to bash, not the command.
    guard=None,  # async (command) -> message to return instead of running it, or None (scaffold.py).
    # async (tool calls so far) -> a note to add to the latest call's output, or None (scaffold.py, v4).
    checkpoint=None,
  ):
    super().__init__()
    self._tools = [BASH_TOOL, SUBMIT_TOOL] if submit_tool else [BASH_TOOL]
    self._guard = guard
    self._checkpoint = checkpoint
    self._calls = 0
    self._system_note = system_note.strip()
    self._config = config
    self._client = client
    self._shell = shell
    self._run_dir = run_dir
    self._container = container
    self.container = container
    self._command_timeout_s = command_timeout_s
    self._messages: list[dict] = []
    self._cancelling = False
    self._current: asyncio.Task | None = None
    self._transcript = None
    self.info = {
      'model_config': config.name,
      'model': config.model,
      'base_url': config.base_url,
      'params': config.params,
      'providers': [],
    }

  @property
  def command(self) -> list[str]:
    return ['neutral', self._config.name, self._config.model]

  async def start(self) -> None:
    self._transcript = open(self._run_dir / 'neutral.jsonl', 'a', encoding='utf-8')
    if self._container:
      await self._container.start()
    self._messages = [
      {'role': 'system', 'content': SYSTEM_PROMPT.format(minutes=self._command_timeout_s / 60)
       + (f'\n\n{self._system_note}' if self._system_note else '')}
    ]

  async def prompt(self, text: str) -> TurnEnd:
    self._cancelling = False
    self._messages.append({'role': 'user', 'content': text})
    usage: dict = {}
    while True:
      response = await self._step(self._complete(list(self._messages)))
      if response is None:
        return TurnEnd('cancelled', usage)
      self.on_activity()
      self._log({'response': response})
      # Requests are what free endpoints cap per day (see matrix.toml).
      usage['requests'] = usage.get('requests', 0) + 1
      for key, value in flatten_usage(response.get('usage')).items():
        usage[key] = usage.get(key, 0) + value
      provider = response.get('provider')
      if provider and provider not in self.info['providers']:
        self.info['providers'].append(provider)
      choice = response['choices'][0]
      message = choice.get('message') or {}
      fields = _ASSISTANT_FIELDS if self._config.send_reasoning else ('content', 'tool_calls')
      assistant = {'role': 'assistant'}
      assistant.update({key: message[key] for key in fields if message.get(key) is not None})
      assistant.setdefault('content', '')
      self._messages.append(assistant)
      calls = message.get('tool_calls') or []
      if not calls:
        return TurnEnd(str(choice.get('finish_reason') or 'stop'), usage)
      for index, call in enumerate(calls):
        # Some providers reuse ids like functions.bash:0, so key steps by position too.
        self.on_step(f'{len(self._messages)}:{index}:{call.get("id")}')
        result = await self._step(self._run_call(call))
        if result is None:
          for unfinished in calls[index:]:
            self._reply(unfinished, 'The command was cancelled because the turn was stopped.')
          return TurnEnd('cancelled', usage)
        self._calls += 1
        if self._checkpoint and (call.get('function') or {}).get('name') != 'submit':
          note = await self._step(self._checkpoint(self._calls))
          if note:
            result = f'{result}\n\n{note}'
        self._reply(call, result)
        self.on_activity()

  def _complete(self, messages: list[dict]):
    return self._client.complete(messages, tools=self._tools)

  async def cancel(self) -> None:
    self._cancelling = True
    if self._current and not self._current.done():
      self._current.cancel()

  async def close(self) -> None:
    await self.cancel()
    await self._client.aclose()
    self.info['retries'] = len(self._client.retries)
    self.info['retry_reasons'] = self._client.retries[-10:]
    if self._container:
      await self._container.remove()
    if self._transcript:
      self._transcript.close()

  async def _step(self, awaitable):
    """Await one model call or command; None if the turn was cancelled meanwhile."""
    if self._cancelling:
      return None
    self._current = asyncio.ensure_future(awaitable)
    try:
      return await self._current
    except asyncio.CancelledError:
      if self._cancelling:
        return None
      raise
    finally:
      self._current = None

  async def _run_call(self, call: dict) -> str:
    function = call.get('function') or {}
    names = [tool['function']['name'] for tool in self._tools]
    if function.get('name') not in names:
      return f'Error: unknown tool {function.get("name")!r}; the tools are {", ".join(names)}.'
    if function.get('name') == 'submit':
      return await self._submit(function.get('arguments') or '{}')
    try:
      command = json.loads(function.get('arguments') or '{}').get('command')
    except (ValueError, AttributeError):
      command = None
    if not isinstance(command, str) or not command.strip():
      return 'Error: bash needs a JSON object argument with a non-empty "command" string.'
    if self._guard and (blocked := await self._guard(command)):
      self._log({'command': command, 'blocked': blocked})
      return blocked
    started = time.time()
    output, exit_code = await self._shell.run(command, self._command_timeout_s)
    self._log({'command': command, 'exit_code': exit_code, 'seconds': round(time.time() - started, 2)})
    return tool_result_text(output, exit_code, self._command_timeout_s)

  async def _submit(self, arguments: str) -> str:
    """The submit tool: runs the submit command with the claims, as the agent would."""
    try:
      parsed = json.loads(arguments)
    except ValueError:
      parsed = None
    if not isinstance(parsed, dict):
      return 'Error: submit needs a JSON object argument with "status" and "claims".'
    encoded = base64.b64encode(json.dumps(parsed.get('claims')).encode()).decode()
    path = f'/tmp/submit-claims-{time.time_ns()}.json'
    command = (f'printf %s {encoded} | base64 -d > {path} && '
               f'submit --status {shlex.quote(str(parsed.get("status")))} --claims {path}')
    started = time.time()
    # The submit command can wait for a review (scaffold.py), so it gets longer than a command.
    output, exit_code = await self._shell.run(command, max(self._command_timeout_s, 1800.0))
    self._log({'submit': parsed, 'exit_code': exit_code, 'seconds': round(time.time() - started, 2)})
    return output.strip() or f'exit code {exit_code}'

  def _reply(self, call: dict, content: str) -> None:
    self._messages.append({'role': 'tool', 'tool_call_id': call.get('id', ''), 'content': content})
    self._log({'tool_result': {'id': call.get('id'), 'content': content}})

  def _log(self, entry: dict) -> None:
    if self._transcript:
      self._transcript.write(json.dumps({'t': time.time(), **entry}) + '\n')
      self._transcript.flush()
