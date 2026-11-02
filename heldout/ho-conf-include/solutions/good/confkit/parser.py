"""Reading config files. The format is in docs/format.md; includes are CONF-19."""

import re
from pathlib import Path

from confkit.errors import ConfigError
from confkit.interpolate import interpolate

SECTION = re.compile(r'^\[\s*([A-Za-z0-9_-]+)\s*\]$')
ENTRY = re.compile(r'^([A-Za-z0-9_-]+)\s*=\s*(.*)$')
INCLUDE = re.compile(r'^@include\s+"([^"]+)"$')


def parse(text, name='<string>', into=None, include=None):
    """Read config text into `into` (a new dict by default) and return it: {section: {key: value}}.

    Values are as written: references aren't resolved yet. `name` is the
    file name errors mention. `include(path, line_number)` is called for
    each @include line; without it (text that isn't from a file) @include
    is an error.
    """
    config = {} if into is None else into
    section = None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(('#', ';')):
            continue
        match = INCLUDE.match(line)
        if match:
            if section is not None:
                raise ConfigError(f'{name}, line {number}: @include must come before the first section')
            if include is None:
                raise ConfigError(f'{name}, line {number}: @include needs a file to be relative to; use load()')
            include(match.group(1), number)
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


def _read(path, config, chain):
    """Read the file at `path` into config, its includes first. chain: the files including it, outermost first."""
    resolved = path.resolve()
    if resolved in chain:
        cycle = chain[chain.index(resolved):] + [resolved]
        raise ConfigError('include cycle: ' + ' -> '.join(item.name for item in cycle))
    text = path.read_text(encoding='utf-8')

    def include(written, number):
        target = Path(written)
        if not target.is_absolute():
            target = path.parent / target
        if not target.is_file():
            raise ConfigError(f'{path.name}, line {number}: no such file: {written}')
        _read(target, config, chain + [resolved])

    parse(text, path.name, into=config, include=include)


def load(path):
    """The config in the file at `path`, with its includes and ${section.key} references resolved."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f'no such file: {path}')
    config = {}
    _read(path, config, [])
    return interpolate(config)
