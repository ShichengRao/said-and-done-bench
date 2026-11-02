"""Host side of the in-container `submit` command (container/submit).

The command writes req-<id>.json into a shared directory and waits for
ack-<id>.json. The harness validates each request and, for an accepted one,
snapshots the workspace before writing the ack, so the agent can't keep
working between its claim and the snapshot.
"""

from __future__ import annotations

import dataclasses
import json
import os
from collections.abc import Sequence
from pathlib import Path

STATUSES = ('complete', 'blocked')


@dataclasses.dataclass(frozen=True)
class SubmitRequest:
  id: str
  raw: dict


@dataclasses.dataclass(frozen=True)
class Verdict:
  accepted: bool
  status: str | None
  claims: dict | None
  errors: tuple[str, ...]


def check_claims(claims: object, extra_fields: Sequence[str] = ()) -> list[str]:
  """Return what's wrong with a claims object; empty means it's well formed."""
  if not isinstance(claims, dict):
    return ['the claims must be a JSON object']
  errors = []
  summary = claims.get('summary')
  if not isinstance(summary, str) or not summary.strip():
    errors.append('"summary" must be a non-empty string')
  verified = claims.get('verified_end_to_end')
  if not isinstance(verified, bool):
    errors.append('"verified_end_to_end" must be true or false')
  commands = claims.get('verification_commands')
  if not isinstance(commands, list) or not all(
    isinstance(command, str) for command in commands
  ):
    errors.append('"verification_commands" must be a list of strings')
  elif verified is True and not commands:
    errors.append(
      "\"verification_commands\" can't be empty when \"verified_end_to_end\" is true"
    )
  for field in extra_fields:
    if field not in claims:
      errors.append(f'"{field}" is required for this task')
  return errors


class SubmitChannel:
  def __init__(self, directory: Path, extra_claim_fields: Sequence[str] = ()):
    self.directory = directory
    self.directory.mkdir(parents=True, exist_ok=True)
    self._extra_claim_fields = tuple(extra_claim_fields)
    self._seen: set[str] = set()
    self._unacked: set[str] = set()

  def poll(self) -> list[SubmitRequest]:
    """Return requests that arrived since the last poll, oldest first."""
    requests = []
    for path in sorted(self.directory.glob('req-*.json')):
      request_id = path.stem.removeprefix('req-')
      if request_id in self._seen:
        continue
      self._seen.add(request_id)
      self._unacked.add(request_id)
      try:
        raw = json.loads(path.read_text(encoding='utf-8'))
      except (OSError, ValueError) as error:
        raw = {'read_error': f"the harness couldn't read the request: {error}"}
      if not isinstance(raw, dict):
        raw = {'read_error': 'the request is not a JSON object'}
      requests.append(SubmitRequest(request_id, raw))
    return requests

  def validate(self, request: SubmitRequest) -> Verdict:
    raw = request.raw
    errors = [raw[key] for key in ('read_error', 'usage_error', 'claims_error') if raw.get(key)]
    status = raw.get('status')
    if status not in STATUSES:
      errors.append(f'--status must be "complete" or "blocked", not {status!r}')
    claims = None
    text = raw.get('claims_text')
    if text is None:
      if not raw.get('claims_error'):
        errors.append('--claims is required')
    else:
      try:
        claims = json.loads(text)
      except ValueError as error:
        errors.append(f"the claims aren't valid JSON: {error}")
      else:
        errors.extend(check_claims(claims, self._extra_claim_fields))
    if errors:
      return Verdict(False, None, None, tuple(errors))
    return Verdict(True, status, claims, ())

  def ack(self, request_id: str, accepted: bool, message: str) -> None:
    temporary = self.directory / f'.ack-{request_id}.tmp'
    temporary.write_text(json.dumps({'accepted': accepted, 'message': message}))
    os.replace(temporary, self.directory / f'ack-{request_id}.json')
    self._unacked.discard(request_id)

  def reject_pending(self, message: str) -> None:
    """Answer every unanswered request, so no `submit` call waits forever."""
    self.poll()
    for request_id in sorted(self._unacked):
      self.ack(request_id, False, message)
