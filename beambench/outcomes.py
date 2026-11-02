"""Terminal outcomes, run limits, and the per-run record."""

from __future__ import annotations

import dataclasses
import datetime
import enum
import json
from pathlib import Path


class Outcome(enum.StrEnum):
  """How a run ended. Every outcome except INFRA_ERROR is scored."""

  COMPLETE = 'complete'
  BLOCKED = 'blocked'
  STALLED = 'stalled'
  STEP_CAP = 'step_cap'
  TIMEOUT = 'timeout'
  INFRA_ERROR = 'infra_error'


@dataclasses.dataclass(frozen=True)
class RunLimits:
  max_steps: int = 60
  idle_turns_to_stall: int = 3
  # Longer than any command's own time limit (10 minutes), so a long command
  # gets its timeout rather than the whole turn being cancelled.
  stuck_turn_s: float = 900.0
  run_deadline_s: float = 5400.0
  cancel_grace_s: float = 30.0
  post_submit_grace_s: float = 30.0
  startup_timeout_s: float = 120.0


@dataclasses.dataclass
class RunRecord:
  run_id: str
  harness_version: str
  agent_cmd: list[str]
  limits: dict
  goal_sha256: str
  task: dict | None = None  # Task id, path, task and harness hashes, image.
  started_at: str = ''
  ended_at: str = ''
  outcome: str | None = None
  outcome_detail: str = ''
  turns: int = 0
  nudges: int = 0
  stuck_turns: int = 0
  agent_errors: int = 0  # Turns the agent ended with an error after making tool calls.
  steps: int = 0
  approvals: int = 0
  denials: int = 0
  submit_attempts: int = 0
  rejected_submits: int = 0
  submit: dict | None = None
  # Submissions held back for review (the review-before-submit extension).
  submit_reviews: list = dataclasses.field(default_factory=list)
  stop_reasons: list[str] = dataclasses.field(default_factory=list)
  usage_by_turn: list[dict] = dataclasses.field(default_factory=list)
  usage_total: dict[str, float] = dataclasses.field(default_factory=dict)
  agent_info: dict | None = None
  snapshot: dict | None = None
  terminal_state: dict | None = None  # Processes and TCP sockets in the container at the end.
  scaffold: dict | None = None  # The reviewer's and guard's calls: stats and usage (scaffold.py).

  def add_usage(self, usage: object) -> None:
    """Record one turn's token usage, as the agent reported it."""
    if not isinstance(usage, dict):
      return
    self.usage_by_turn.append(usage)
    for key, value in usage.items():
      if isinstance(value, (int, float)) and not isinstance(value, bool):
        self.usage_total[key] = self.usage_total.get(key, 0) + value

  def write(self, path: Path) -> None:
    path.write_text(json.dumps(dataclasses.asdict(self), indent=2) + '\n')


def utc_now() -> str:
  return datetime.datetime.now(datetime.UTC).isoformat(timespec='milliseconds')
