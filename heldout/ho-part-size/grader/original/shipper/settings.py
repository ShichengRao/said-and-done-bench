"""Settings for an environment.

The built-in defaults (defaults.py), then config/base.toml, then
config/<env>.toml, each overriding the one before. The environment is
APP_ENV, or dev when it isn't set; dev has no file of its own.
"""

import dataclasses
import os
import re
import tomllib
from pathlib import Path

from shipper import defaults

CONFIG_DIR = Path(__file__).resolve().parent.parent / 'config'


class ConfigError(Exception):
    pass


@dataclasses.dataclass(frozen=True)
class Settings:
    env: str
    endpoint: str
    bucket: str
    part_size: int
    max_parts: int
    retries: int
    timeout_s: float


# Where each setting lives in the TOML files: (table, key) -> Settings field.
FIELDS = {
    ('store', 'endpoint'): 'endpoint',
    ('store', 'bucket'): 'bucket',
    ('transfer', 'chunk'): 'part_size',
    ('transfer', 'max_parts'): 'max_parts',
    ('transfer', 'retries'): 'retries',
    ('transfer', 'timeout'): 'timeout_s',
}
_SIZE = re.compile(r'^\s*(\d+)\s*(B|KiB|MiB|GiB)?\s*$')
_UNITS = {None: 1, 'B': 1, 'KiB': defaults.KiB, 'MiB': defaults.MiB, 'GiB': 1024 * defaults.MiB}


def parse_size(value):
    """A byte count: an integer, or a string such as "512KiB" or "8MiB"."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    match = _SIZE.match(value) if isinstance(value, str) else None
    if not match:
        raise ConfigError(f'not a size: {value!r}')
    return int(match.group(1)) * _UNITS[match.group(2)]


def _read(path):
    try:
        data = tomllib.loads(path.read_text(encoding='utf-8'))
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f'{path.name}: {error}') from None
    values = {}
    for table, entries in data.items():
        if not isinstance(entries, dict):
            raise ConfigError(f'{path.name}: [{table}] must be a table')
        for key, value in entries.items():
            field = FIELDS.get((table, key))
            if field is None:
                raise ConfigError(f'{path.name}: unknown setting {table}.{key}')
            values[field] = value
    return values


def load_settings(env=None, config_dir=CONFIG_DIR):
    env = env or os.environ.get('APP_ENV') or 'dev'
    values = {
        'endpoint': defaults.ENDPOINT,
        'bucket': defaults.BUCKET,
        'part_size': defaults.PART_SIZE,
        'max_parts': defaults.MAX_PARTS,
        'retries': defaults.RETRIES,
        'timeout_s': defaults.TIMEOUT_S,
    }
    for name in ('base', env):
        path = Path(config_dir) / f'{name}.toml'
        if path.exists():
            values.update(_read(path))
    values['part_size'] = parse_size(values['part_size'])
    values['timeout_s'] = float(values['timeout_s'])
    return Settings(env=env, **values)
