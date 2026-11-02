"""Reading config files. The format is in docs/format.md."""

import re
from pathlib import Path

from confkit.errors import ConfigError
from confkit.interpolate import interpolate

SECTION = re.compile(r'^\[\s*([A-Za-z0-9_-]+)\s*\]$')
ENTRY = re.compile(r'^([A-Za-z0-9_-]+)\s*=\s*(.*)$')


def parse(text, name='<string>', into=None):
    """Read config text into `into` (a new dict by default) and return it: {section: {key: value}}.

    Values are as written: references aren't resolved yet. `name` is the
    file name errors mention.
    """
    config = {} if into is None else into
    section = None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(('#', ';')):
            continue
        match = SECTION.match(line)
        if match:
            section = config.setdefault(match.group(1), {})
            continue
        match = ENTRY.match(line)
        if match:
            if section is None:
                raise ConfigError(f'{name}, line {number}: {match.group(1)} is outside any section')
            section[match.group(1)] = match.group(2).strip()
            continue
        raise ConfigError(f'{name}, line {number}: cannot read {line!r}')
    return config


def load(path):
    """The config in the file at `path`, with ${section.key} references resolved."""
    path = Path(path)
    try:
        text = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        raise ConfigError(f'no such file: {path}') from None
    return interpolate(parse(text, path.name))
