"""Agent CLIs run headless, one process per turn, printing JSONL events.

Claude Code and Codex both work this way: a turn is one process that reads
the prompt from stdin, streams events, and exits; the next turn resumes the
same conversation by id. Subclasses supply the arguments and read the events.
"""

from __future__ import annotations

import abc
import asyncio
import contextlib
import json
import signal
import time
from collections.abc import Sequence
from pathlib import Path

from beambench.container import Container
from beambench.runner import AgentSession, TurnEnd

_LINE_LIMIT = 64 * 1024 * 1024


class HeadlessCliSession(AgentSession):
  transcript_name: str  # The event log in the run directory, e.g. 'claude.jsonl'.

  def __init__(
    self,
    *,
    run_dir: Path,
    container: Container | None,
    executable: Sequence[str],
    env: dict[str, str] | None,
    cwd: Path | None,
    activity_files: Sequence[Path] = (),
  ):
    """With a container, each turn runs in it; otherwise on this machine (tests only).

    activity_files are files that grow while the agent works without printing
    anything, such as a worker's telemetry during a long tool call; their
    growth counts as activity, so the turn isn't taken for stuck.
    """
    super().__init__()
    self._activity_files = list(activity_files)
    self._run_dir = run_dir
    self._container = container
    self.container = container
    self._executable = list(executable)
    self._env = env
    self._cwd = cwd
    self._turns = 0
    self._proc: asyncio.subprocess.Process | None = None
    self._cancelling = False
    self._transcript = None
    self._stderr = None

  @abc.abstractmethod
  def turn_args(self, *, first_turn: bool) -> list[str]:
    """Arguments after the executable for one turn's process."""

  def begin_turn(self) -> None:
    """Reset per-turn state before a turn's process starts."""

  @abc.abstractmethod
  def on_event(self, event: dict) -> None:
    """Handle one event the turn printed."""

  @abc.abstractmethod
  def end_turn(self, returncode: int, cancelled: bool) -> TurnEnd:
    """Return how the turn ended, or raise AgentError."""

  @property
  def command(self) -> list[str]:
    return self._wrap([*self._executable, *self.turn_args(first_turn=True)])

  async def start(self) -> None:
    self._transcript = open(self._run_dir / self.transcript_name, 'a', encoding='utf-8')
    self._stderr = open(self._run_dir / 'agent-stderr.log', 'ab')
    if self._container:
      await self._container.start()
      self.info['version'] = (
        await self._container.output([*self._executable, '--version'])
      ).strip()

  async def prompt(self, text: str) -> TurnEnd:
    self._turns += 1
    self._cancelling = False
    self.begin_turn()
    first_turn = self._turns == 1
    proc = await asyncio.create_subprocess_exec(
      *self._wrap([*self._executable, *self.turn_args(first_turn=first_turn)]),
      stdin=asyncio.subprocess.PIPE,
      stdout=asyncio.subprocess.PIPE,
      stderr=self._stderr,
      env=self._env,
      cwd=self._cwd,
      limit=_LINE_LIMIT,
    )
    self._proc = proc
    proc.stdin.write(text.encode())
    await proc.stdin.drain()
    proc.stdin.close()
    watcher = asyncio.create_task(self._watch_activity()) if self._activity_files else None
    try:
      while line := await proc.stdout.readline():
        self.on_activity()
        event = self._log(line)
        if event is not None:
          self.on_event(event)
    finally:
      if watcher:
        watcher.cancel()
    returncode = await proc.wait()
    self._proc = None
    return self.end_turn(returncode, self._cancelling)

  async def _watch_activity(self) -> None:
    def sizes():
      return [path.stat().st_size if path.exists() else 0 for path in self._activity_files]
    last = sizes()
    while True:
      await asyncio.sleep(2)
      if (now := sizes()) != last:
        last = now
        self.on_activity()

  async def cancel(self) -> None:
    self._cancelling = True
    if self._container:
      await self._container.interrupt()
    elif self._proc and self._proc.returncode is None:
      self._proc.send_signal(signal.SIGINT)

  async def close(self) -> None:
    if self._proc and self._proc.returncode is None:
      with contextlib.suppress(ProcessLookupError):
        self._proc.kill()
      await self._proc.wait()
    if self._container:
      await self._container.remove()
    for handle in (self._transcript, self._stderr):
      if handle:
        handle.close()

  @property
  def turn_number(self) -> int:
    return self._turns

  def _wrap(self, command: list[str]) -> list[str]:
    return self._container.exec_command(command) if self._container else command

  def _log(self, line: bytes) -> dict | None:
    entry: dict = {'t': time.time(), 'turn': self._turns}
    try:
      event = json.loads(line)
    except ValueError:
      event = None
    if isinstance(event, dict):
      entry['event'] = event
    else:
      entry['raw'] = line.decode(errors='replace')
      event = None
    if self._transcript:
      self._transcript.write(json.dumps(entry) + '\n')
      self._transcript.flush()
    return event
