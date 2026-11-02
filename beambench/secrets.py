"""Agent credentials, kept in a user-only file outside the repo.

`python -m beambench login <agent>` stores a credential once; runs read it
from there whenever it isn't already in the environment. Containers still
get each credential by name only.
"""

from __future__ import annotations

import getpass
import os
import sys
from collections.abc import Iterable
from pathlib import Path

SECRETS_FILE = Path(
  os.environ.get('BEAMBENCH_SECRETS', Path.home() / '.config' / 'beambench' / 'secrets.env')
)


def read_all(path: Path = SECRETS_FILE) -> dict[str, str]:
  values = {}
  if path.exists():
    for line in path.read_text(encoding='utf-8').splitlines():
      name, sep, value = line.partition('=')
      if sep and name.strip() and not name.lstrip().startswith('#'):
        values[name.strip()] = value.strip()
  return values


def save(name: str, value: str, path: Path = SECRETS_FILE) -> None:
  """Store one credential; the file is readable only by this user."""
  path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
  values = read_all(path)
  values[name] = value
  temporary = path.with_name(path.name + '.tmp')
  fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
  with os.fdopen(fd, 'w', encoding='utf-8') as f:
    f.write(''.join(f'{key}={val}\n' for key, val in sorted(values.items())))
  os.replace(temporary, path)


def load_into_environ(names: Iterable[str], path: Path = SECRETS_FILE) -> list[str]:
  """Fill unset names from the secrets file; return the ones still missing."""
  stored = read_all(path)
  missing = []
  for name in names:
    if os.environ.get(name, '').strip():
      continue
    if stored.get(name):
      os.environ[name] = stored[name]
    else:
      missing.append(name)
  return missing


def read_pasted(prompt: str) -> str:
  """Read a pasted secret without echoing it, until an empty line.

  A narrow terminal can wrap a long token onto several lines, and copying it
  then includes the breaks; all whitespace is dropped.
  """
  parts = [getpass.getpass(prompt)]
  while parts[-1].strip():
    parts.append(getpass.getpass(''))
  return ''.join(''.join(parts).split())


def clear_screen() -> None:
  """Clear the screen and the scrollback, so a token shown earlier doesn't linger."""
  sys.stdout.write('\033[2J\033[3J\033[H')
  sys.stdout.flush()
