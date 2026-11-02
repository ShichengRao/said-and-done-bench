"""Removes the run's real credentials from everything a run leaves behind.

Native agents run with a real token in their environment (Claude Code's, for
one), so an agent that prints its environment, or follows an injected
instruction to send it somewhere, can put that token into a transcript or
the canary log. Run directories may be published with the results, so after
each run every text file in it has known secret values replaced with
[REDACTED:<name>]. A binary file can't be rewritten safely (Mirror's SQLite
state, the snapshot tarball); one that contains a secret is listed instead,
so it can be withheld from publication.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

_MIN_SECRET_LENGTH = 12  # Shorter values would match ordinary text.


def codex_secrets(auth_file: Path) -> dict[str, str]:
  """The token strings in a Codex auth.json, which a run's copy also holds."""
  try:
    data = json.loads(auth_file.read_text())
  except (OSError, ValueError):
    return {}
  found = {}

  def walk(value, path):
    if isinstance(value, dict):
      for key, item in value.items():
        walk(item, f'{path}.{key}' if path else key)
    elif isinstance(value, str) and len(value) >= _MIN_SECRET_LENGTH and 'token' in path.lower():
      found[f'codex:{path}'] = value

  walk(data, '')
  return found


def scrub(run_dir: Path, secrets: Mapping[str, str]) -> dict:
  """Redact secret values in run_dir's text files; report what was changed or can't be."""
  secrets = {name: value for name, value in secrets.items() if value and len(value) >= _MIN_SECRET_LENGTH}
  redacted, unscrubbable = [], []
  if not secrets:
    return {'redacted': redacted, 'unscrubbable': unscrubbable}
  needles = {name: value.encode() for name, value in secrets.items()}
  for path in sorted(p for p in run_dir.rglob('*') if p.is_file() and not p.is_symlink()):
    try:
      data = path.read_bytes()
    except OSError:
      continue
    hits = [name for name, needle in needles.items() if needle in data]
    if not hits:
      continue
    relative = str(path.relative_to(run_dir))
    try:
      text = data.decode('utf-8')
    except UnicodeDecodeError:
      unscrubbable.append({'file': relative, 'secrets': hits})
      continue
    for name in hits:
      text = text.replace(secrets[name], f'[REDACTED:{name}]')
    path.write_text(text, encoding='utf-8')
    redacted.append({'file': relative, 'secrets': hits})
  return {'redacted': redacted, 'unscrubbable': unscrubbable}
