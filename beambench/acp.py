"""A minimal Agent Client Protocol client: JSON-RPC 2.0 over an agent's stdio.

Every message in both directions is appended to a JSONL transcript.
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import json
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = 1
_LINE_LIMIT = 64 * 1024 * 1024

RequestHandler = Callable[[dict], Awaitable[Any]]
NotificationHandler = Callable[[dict], None]


class AcpError(Exception):
  """The agent answered a request with a JSON-RPC error."""

  def __init__(self, code: int, message: str, data: Any = None):
    super().__init__(f'{message} (code {code})')
    self.code = code
    self.data = data


class AgentExited(Exception):
  """The agent process ended or closed its pipes."""


class AcpConnection:
  def __init__(
    self,
    cmd: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    transcript_path: Path | None = None,
    stderr_path: Path | None = None,
  ):
    self._cmd = cmd
    self._env = env
    self._cwd = cwd
    self._transcript_path = transcript_path
    self._stderr_path = stderr_path
    self._transcript = None
    self._stderr = None
    self._proc: asyncio.subprocess.Process | None = None
    self._reader: asyncio.Task | None = None
    self._ids = itertools.count(1)
    self._pending: dict[Any, asyncio.Future] = {}
    self._request_handlers: dict[str, RequestHandler] = {}
    self._notification_handlers: dict[str, NotificationHandler] = {}
    self._handler_tasks: set[asyncio.Task] = set()

  def on_request(self, method: str, handler: RequestHandler) -> None:
    self._request_handlers[method] = handler

  def on_notification(self, method: str, handler: NotificationHandler) -> None:
    self._notification_handlers[method] = handler

  @property
  def returncode(self) -> int | None:
    return self._proc.returncode if self._proc else None

  async def start(self) -> None:
    if self._transcript_path:
      self._transcript = open(self._transcript_path, 'a', encoding='utf-8')
    self._stderr = open(self._stderr_path, 'ab') if self._stderr_path else None
    self._proc = await asyncio.create_subprocess_exec(
      *self._cmd,
      stdin=asyncio.subprocess.PIPE,
      stdout=asyncio.subprocess.PIPE,
      stderr=self._stderr or asyncio.subprocess.DEVNULL,
      env=self._env,
      cwd=self._cwd,
      limit=_LINE_LIMIT,
    )
    self._reader = asyncio.create_task(self._read_loop())

  async def request(self, method: str, params: dict) -> Any:
    request_id = next(self._ids)
    future = asyncio.get_running_loop().create_future()
    self._pending[request_id] = future
    try:
      await self._send({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params})
      return await future
    finally:
      self._pending.pop(request_id, None)

  async def notify(self, method: str, params: dict) -> None:
    await self._send({'jsonrpc': '2.0', 'method': method, 'params': params})

  async def close(self, grace_s: float = 5.0) -> None:
    proc = self._proc
    if proc and proc.returncode is None:
      with contextlib.suppress(Exception):
        proc.stdin.close()
      try:
        await asyncio.wait_for(proc.wait(), grace_s)
      except TimeoutError:
        proc.terminate()
        try:
          await asyncio.wait_for(proc.wait(), grace_s)
        except TimeoutError:
          proc.kill()
          await proc.wait()
    if self._reader:
      with contextlib.suppress(Exception):
        await self._reader
    for task in list(self._handler_tasks):
      task.cancel()
    for handle in (self._transcript, self._stderr):
      if handle:
        handle.close()

  async def _send(self, message: dict) -> None:
    if not self._proc or self._proc.returncode is not None:
      raise AgentExited('the agent is not running')
    self._log('out', message)
    try:
      self._proc.stdin.write((json.dumps(message) + '\n').encode())
      await self._proc.stdin.drain()
    except (BrokenPipeError, ConnectionResetError) as error:
      raise AgentExited(f'the agent closed stdin: {error}') from error

  async def _read_loop(self) -> None:
    try:
      while True:
        line = await self._proc.stdout.readline()
        if not line:
          break
        try:
          message = json.loads(line)
        except ValueError:
          self._log('in', None, raw=line.decode(errors='replace'))
          continue
        self._log('in', message)
        self._dispatch(message)
    finally:
      returncode = await self._proc.wait()
      for future in self._pending.values():
        if not future.done():
          future.set_exception(AgentExited(f'the agent exited with code {returncode}'))

  def _dispatch(self, message: dict) -> None:
    method = message.get('method')
    if method is None:
      future = self._pending.get(message.get('id'))
      if future is None or future.done():
        return
      if 'error' in message:
        error = message['error'] or {}
        future.set_exception(
          AcpError(error.get('code', 0), error.get('message', ''), error.get('data'))
        )
      else:
        future.set_result(message.get('result'))
    elif 'id' in message:
      task = asyncio.create_task(self._answer(message))
      self._handler_tasks.add(task)
      task.add_done_callback(self._handler_tasks.discard)
    else:
      handler = self._notification_handlers.get(method)
      if handler:
        handler(message.get('params') or {})

  async def _answer(self, message: dict) -> None:
    handler = self._request_handlers.get(message['method'])
    if handler is None:
      reply = {'error': {'code': -32601, 'message': f'method not found: {message["method"]}'}}
    else:
      try:
        reply = {'result': await handler(message.get('params') or {})}
      except AcpError as error:
        reply = {'error': {'code': error.code, 'message': str(error), 'data': error.data}}
      except Exception as error:  # A handler bug shouldn't hang the agent.
        reply = {'error': {'code': -32603, 'message': f'{type(error).__name__}: {error}'}}
    with contextlib.suppress(AgentExited):
      await self._send({'jsonrpc': '2.0', 'id': message['id'], **reply})

  def _log(self, direction: str, message: dict | None, raw: str | None = None) -> None:
    if not self._transcript:
      return
    entry = {'t': time.time(), 'dir': direction}
    if message is not None:
      entry['msg'] = message
    else:
      entry['raw'] = raw
    self._transcript.write(json.dumps(entry) + '\n')
    self._transcript.flush()
