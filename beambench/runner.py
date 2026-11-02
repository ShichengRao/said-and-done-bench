"""The run loop every agent shares.

It sends the kickoff and "keep going" prompts, answers `submit`, enforces the
step cap and deadlines, and ends each run in one terminal outcome with a
workspace snapshot. An AgentSession (mirror.py, claude_code.py) only moves
prompts and events between this loop and one agent process.
"""

from __future__ import annotations

import abc
import asyncio
import dataclasses
import hashlib
import json
import os
import re
import traceback
from collections.abc import Awaitable, Callable
from pathlib import Path

from beambench import HARNESS_VERSION, prompts
from beambench.outcomes import Outcome, RunLimits, RunRecord, utc_now
from beambench.snapshot import snapshot_workspace
from beambench.submit_channel import SubmitChannel

CONTAINER_BIN = Path(__file__).resolve().parent.parent / 'container'
_POLL_S = 0.25

Approver = Callable[[dict], bool]


def approve_all(tool_call: dict) -> bool:
  del tool_call
  return True


def approve_matching(pattern: str) -> Approver:
  """Approve a tool call only if its JSON (title, input, ...) matches pattern."""
  regex = re.compile(pattern)
  return lambda tool_call: bool(regex.search(json.dumps(tool_call, sort_keys=True)))


def deny_all(tool_call: dict) -> bool:
  del tool_call
  return False


def host_agent_env(submit_dir: Path) -> dict[str, str]:
  """Environment for an agent running on this machine rather than in a container."""
  env = dict(os.environ)
  env['BEAMBENCH_SUBMIT_DIR'] = str(submit_dir)
  env['PATH'] = f'{CONTAINER_BIN}{os.pathsep}{env.get("PATH", "")}'
  return env


class AgentError(Exception):
  """The agent failed a turn."""


class ProviderError(AgentError):
  """The model's provider failed (overloaded, rate limited, at capacity, rejected the request).

  Always an infra error, never a turn ending the model chose, so the run
  loop doesn't nudge after one.
  """


@dataclasses.dataclass(frozen=True)
class TurnEnd:
  stop_reason: str
  usage: dict | None = None


class AgentSession(abc.ABC):
  """One agent conversation. The run loop sets the hooks before start()."""

  def __init__(self) -> None:
    # Called with the id of each tool call the model makes; the loop dedupes.
    self.on_step: Callable[[str], None] = lambda call_id: None
    # Called whenever the agent shows any sign of progress (an event, a tool
    # call, a finished command); a turn with none for stuck_turn_s is cancelled.
    self.on_activity: Callable[[], None] = lambda: None
    # Asked before a tool call that needs approval: True, False, or None when
    # the run is already over.
    self.on_permission: Callable[[dict], bool | None] = lambda tool_call: True
    # What the agent reports about itself, for the run record.
    self.info: dict = {}
    # Where the agent runs, if in a container; its state is recorded at the end.
    self.container = None

  @property
  @abc.abstractmethod
  def command(self) -> list[str]:
    """The agent command, for the run record."""

  @abc.abstractmethod
  async def start(self) -> None:
    """Start the agent, ready for the first prompt."""

  @abc.abstractmethod
  async def prompt(self, text: str) -> TurnEnd:
    """Run one turn and return when the agent ends it."""

  @abc.abstractmethod
  async def cancel(self) -> None:
    """Ask the agent to end the current turn now."""

  @abc.abstractmethod
  async def close(self) -> None:
    """Stop the agent and release everything it holds."""


@dataclasses.dataclass
class Task:
  run_id: str
  goal: str
  workspace: Path  # The workspace on this machine, for snapshots.
  submit_dir: Path
  run_dir: Path
  limits: RunLimits = dataclasses.field(default_factory=RunLimits)
  approve: Approver = approve_all
  extra_claims: tuple[str, ...] = ()
  extra_claim_fields: tuple[str, ...] = ()
  info: dict | None = None  # Recorded as the run record's `task`.
  restate_goal_in_nudges: bool = True
  submit_tool: bool = False  # The agent submits with a tool, not the command (a brain agent).
  kickoff_note: str = ''  # An extra paragraph in the first prompt (experiments).
  review_submit: bool = False  # Hold the first "complete" for one review (a mitigation).
  # An independent reviewer (scaffold.py): async (status, claims) -> feedback that holds the submission
  # for the agent to deal with, or None to accept it.
  reviewer: Callable[[str, dict], Awaitable[str | None]] | None = None


@dataclasses.dataclass(frozen=True)
class _TurnResult:
  outcome: Outcome | None = None
  detail: str = ''
  stuck: bool = False


async def run_task(task: Task, session: AgentSession) -> RunRecord:
  return await _Run(task, session).run()


class _Run:
  def __init__(self, task: Task, session: AgentSession):
    self._task = task
    self._limits = task.limits
    self._session = session
    task.run_dir.mkdir(parents=True, exist_ok=True)
    self._record = RunRecord(
      run_id=task.run_id,
      harness_version=HARNESS_VERSION,
      agent_cmd=list(session.command),
      limits=dataclasses.asdict(task.limits),
      goal_sha256=hashlib.sha256(task.goal.encode()).hexdigest(),
      task=task.info,
    )
    self._channel = SubmitChannel(task.submit_dir, task.extra_claim_fields)
    self._tool_call_ids: set[str] = set()
    self._finished = False
    self._last_activity = 0.0
    session.on_step = self._on_step
    session.on_activity = self._on_activity
    session.on_permission = self._on_permission

  async def run(self) -> RunRecord:
    record = self._record
    record.started_at = utc_now()
    try:
      outcome, detail = await self._drive()
    except asyncio.CancelledError:
      # Stopped from outside (Ctrl-C, SIGTERM, a batch shutting down): clean up
      # the agent's container and record nothing, so the batch reruns the cell.
      self._finished = True
      await self._session.close()
      self._channel.reject_pending('The run was stopped.')
      raise
    except Exception as error:  # Unattended runs must still end with a record.
      outcome, detail = Outcome.INFRA_ERROR, f'{type(error).__name__}: {error}'
      (self._task.run_dir / 'harness-error.txt').write_text(traceback.format_exc())
    self._finished = True
    await self._session.close()
    self._channel.reject_pending('The run is already over.')
    if record.snapshot is None:
      await self._snapshot()
    record.agent_info = self._session.info
    record.outcome = outcome.value
    record.outcome_detail = detail
    record.ended_at = utc_now()
    record.write(self._task.run_dir / 'record.json')
    return record

  async def _drive(self) -> tuple[Outcome, str]:
    loop = asyncio.get_running_loop()
    await asyncio.wait_for(self._session.start(), self._limits.startup_timeout_s)
    run_deadline = loop.time() + self._limits.run_deadline_s
    text = prompts.kickoff(
      self._task.goal, self._task.extra_claims, submit_tool=self._task.submit_tool, note=self._task.kickoff_note,
    )
    idle_turns = 0
    while True:
      self._record.turns += 1
      steps_before = self._record.steps
      result = await self._turn(text, run_deadline)
      if result.outcome is not None:
        return result.outcome, result.detail
      idle_turns = idle_turns + 1 if self._record.steps == steps_before else 0
      if idle_turns >= self._limits.idle_turns_to_stall:
        await self._snapshot()
        return Outcome.STALLED, f'{idle_turns} turns in a row without a tool call'
      self._record.nudges += 1
      text = prompts.nudge(
        self._task.goal if self._task.restate_goal_in_nudges else None,
        turn=self._record.turns + 1,
        stuck_minutes=self._limits.stuck_turn_s / 60 if result.stuck else None,
        submit_tool=self._task.submit_tool,
      )

  async def _turn(self, text: str, run_deadline: float) -> _TurnResult:
    loop = asyncio.get_running_loop()
    steps_before = self._record.steps
    self._last_activity = loop.time()
    prompt = asyncio.ensure_future(self._session.prompt(text))
    try:
      while True:
        outcome = await self._check_submits()
        if outcome is not None:
          await self._end_turn_after_submit(prompt)
          return _TurnResult(outcome)
        if self._record.steps > self._limits.max_steps:
          self._finished = True
          await self._cancel(prompt)
          await self._snapshot()
          return _TurnResult(
            Outcome.STEP_CAP,
            f'started tool call {self._record.steps}; the cap is {self._limits.max_steps}',
          )
        if prompt.done():
          try:
            end = prompt.result()
          except AgentError as error:
            # A turn the agent's own scaffold ended with an error after making
            # tool calls (Mirror aborts a turn after five failed tool calls) is
            # nudged like any other turn end. A provider failure, or a failure
            # before doing anything, means the run can't go on: infra error.
            if isinstance(error, ProviderError) or self._record.steps == steps_before:
              raise
            self._record.agent_errors += 1
            self._record.stop_reasons.append(f'error: {str(error)[:200]}')
            return _TurnResult(await self._check_submits())
          self._record.stop_reasons.append(end.stop_reason)
          self._record.add_usage(end.usage)
          # A backgrounded `submit` can land just as the turn ends.
          return _TurnResult(await self._check_submits())
        now = loop.time()
        if now >= run_deadline:
          self._finished = True
          await self._cancel(prompt)
          await self._snapshot()
          return _TurnResult(
            Outcome.TIMEOUT, f'ran past the {self._limits.run_deadline_s:g} s deadline'
          )
        if now >= self._last_activity + self._limits.stuck_turn_s:
          self._record.stuck_turns += 1
          if not await self._cancel(prompt):
            return _TurnResult(Outcome.INFRA_ERROR, "the agent didn't stop when its turn was cancelled")
          self._record.stop_reasons.append('stuck')
          return _TurnResult(stuck=True)
        await asyncio.wait({prompt}, timeout=_POLL_S)
    finally:
      if not prompt.done():
        prompt.cancel()
      elif not prompt.cancelled():
        prompt.exception()  # Mark any error as retrieved.

  async def _check_submits(self) -> Outcome | None:
    for request in self._channel.poll():
      self._record.submit_attempts += 1
      verdict = self._channel.validate(request)
      if not verdict.accepted:
        self._record.rejected_submits += 1
        self._channel.ack(request.id, False, prompts.submit_rejected(verdict.errors))
        continue
      feedback = await self._task.reviewer(verdict.status, verdict.claims) if self._task.reviewer else None
      if self._task.reviewer:
        self._last_activity = asyncio.get_running_loop().time()  # A review isn't the agent being stuck.
      if feedback:
        self._record.submit_reviews.append({
          'status': verdict.status, 'claims': verdict.claims, 'at': utc_now(), 'feedback': feedback,
        })
        self._channel.ack(request.id, False, feedback)
        continue
      if self._task.review_submit and verdict.status == 'complete' and not self._record.submit_reviews:
        self._record.submit_reviews.append({
          'status': verdict.status, 'claims': verdict.claims, 'at': utc_now(),
        })
        self._channel.ack(request.id, False, prompts.submit_review())
        continue
      self._finished = True
      await self._snapshot()
      self._record.submit = {
        'request_id': request.id,
        'status': verdict.status,
        'claims': verdict.claims,
        'argv': request.raw.get('argv'),
        'accepted_at': utc_now(),
      }
      self._channel.ack(request.id, True, prompts.submit_accepted(verdict.status))
      return Outcome(verdict.status)
    return None

  async def _end_turn_after_submit(self, prompt: asyncio.Future) -> None:
    """Give the agent a moment to end its turn, so the turn's usage is recorded.

    Some agents (Claude Code) report usage only when a turn ends normally.
    The snapshot is already taken, so nothing the agent does now is scored.
    """
    try:
      end = await asyncio.wait_for(asyncio.shield(prompt), self._limits.post_submit_grace_s)
    except TimeoutError:
      await self._cancel(prompt)
      return
    except Exception:  # The turn failed after the submit; the run is over anyway.
      return
    self._record.stop_reasons.append(end.stop_reason)
    self._record.add_usage(end.usage)

  async def _cancel(self, prompt: asyncio.Future) -> bool:
    """Cancel the current turn; return whether the agent ended it within the grace period."""
    if prompt.done():
      return True
    try:
      await self._session.cancel()
      end = await asyncio.wait_for(asyncio.shield(prompt), self._limits.cancel_grace_s)
    except TimeoutError:
      return False
    except Exception:  # The turn ended, if badly; the run is ending anyway.
      return True
    self._record.add_usage(end.usage)
    return True

  async def _snapshot(self) -> None:
    """Archive the workspace with every process in the agent's container frozen.

    Otherwise a command still running at submit (a backgrounded fix, say) could
    write into the archive while it's being made, or after its timestamp, which
    graders use as the evidence cutoff. The process list comes after: a paused
    container can't run `ps`, and the agent's turn is over either way.
    """
    if self._record.snapshot is not None:
      return
    container = self._session.container
    frozen = await container.pause() if container is not None else False
    try:
      snapshot = await asyncio.to_thread(
        snapshot_workspace, self._task.workspace, self._task.run_dir / 'snapshot.tar.gz'
      )
    finally:
      if frozen:
        await container.unpause()
    self._record.snapshot = {**snapshot, 'writers_frozen': frozen}
    if container is not None:
      self._record.terminal_state = await container.terminal_state()

  def _on_activity(self) -> None:
    self._last_activity = asyncio.get_running_loop().time()

  def _on_step(self, call_id: str) -> None:
    if call_id not in self._tool_call_ids:
      self._tool_call_ids.add(call_id)
      self._record.steps += 1

  def _on_permission(self, tool_call: dict) -> bool | None:
    if self._finished:
      return None
    allowed = self._task.approve(tool_call)
    if allowed:
      self._record.approvals += 1
    else:
      self._record.denials += 1
    return allowed
