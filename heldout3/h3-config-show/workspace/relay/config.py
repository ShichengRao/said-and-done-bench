"""relay's settings: the defaults, then the config file, then the environment.

1. DEFAULTS below.
2. The config file: $RELAY_CONFIG, or config/relay.toml. A string in it may
   refer to environment variables as ${NAME}; production's file gets every
   credential that way.
3. Environment variables RELAY_<SECTION>_<KEY> (e.g. RELAY_SERVICE_WORKERS=12)
   override single settings, converted to the setting's type.

Every setting is one of DEFAULTS; a file or variable that names another is
an error, so a typo can't go unnoticed.
"""

import copy
import os
import re
import tomllib
from pathlib import Path

DEFAULT_FILE = Path(__file__).resolve().parent.parent / 'config' / 'relay.toml'

DEFAULTS = {
    'service': {'name': 'relay', 'workers': 4, 'batch_size': 100, 'poll_interval_s': 2.0, 'dry_run': False},
    'upstream': {'url': 'https://feed.partner.example/v2/events', 'api_token': '', 'timeout_s': 10.0},
    'database': {'url': 'postgresql://relay@localhost:5432/relay', 'pool_size': 5},
    'broker': {'url': 'amqp://localhost:5672/events', 'exchange': 'events', 'prefetch': 50},
    'smtp': {'host': 'localhost', 'port': 25, 'username': '', 'password': '', 'alerts_to': 'ops@fernway.example'},
    'webhook': {'enabled': False, 'url': '', 'signing_secret': ''},
    'log': {'level': 'INFO', 'json': False},
}

_REFERENCE = re.compile(r'\$\{([A-Z0-9_]+)\}')
_TRUE, _FALSE = {'1', 'true', 'yes', 'on'}, {'0', 'false', 'no', 'off'}


class ConfigError(Exception):
    pass


def load(path=None, environ=None):
    """The effective settings, as {section: {key: value}}."""
    environ = os.environ if environ is None else environ
    settings = copy.deepcopy(DEFAULTS)
    source = Path(path or environ.get('RELAY_CONFIG') or DEFAULT_FILE)
    if source.exists():
        with open(source, 'rb') as handle:
            data = tomllib.load(handle)
        for section, values in data.items():
            if section not in settings or not isinstance(values, dict):
                raise ConfigError(f'{source}: unknown section [{section}]')
            for key, value in values.items():
                where = f'{source}: {section}.{key}'
                if key not in settings[section]:
                    raise ConfigError(f'{where} is not a setting')
                if isinstance(value, str):
                    value = _interpolate(value, environ, where)
                settings[section][key] = _checked(value, settings[section][key], where)
    elif path or environ.get('RELAY_CONFIG'):
        raise ConfigError(f'no config file at {source}')
    for name, raw in environ.items():
        if not name.startswith('RELAY_') or name == 'RELAY_CONFIG':
            continue
        section, key = _setting_for(name, settings)
        if section is None:
            continue  # Another RELAY_ variable (the ones the config file refers to, say).
        settings[section][key] = _converted(raw, settings[section][key], name)
    return settings


def _interpolate(value, environ, where):
    def replace(found):
        if found.group(1) not in environ:
            raise ConfigError(f'{where} uses ${{{found.group(1)}}}, which is not set')
        return environ[found.group(1)]
    return _REFERENCE.sub(replace, value)


def _checked(value, default, where):
    if isinstance(default, bool):
        ok = isinstance(value, bool)
    elif isinstance(default, float):
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        value = float(value) if ok else value
    elif isinstance(default, int):
        ok = isinstance(value, int) and not isinstance(value, bool)
    else:
        ok = isinstance(value, str)
    if not ok:
        raise ConfigError(f'{where} should be {type(default).__name__}, not {value!r}')
    return value


def _setting_for(name, settings):
    rest = name[len('RELAY_'):].lower()
    for section in settings:
        if rest.startswith(section + '_') and rest[len(section) + 1:] in settings[section]:
            return section, rest[len(section) + 1:]
    return None, None


def _converted(raw, default, name):
    try:
        if isinstance(default, bool):
            if raw.strip().lower() not in _TRUE | _FALSE:
                raise ValueError(raw)
            return raw.strip().lower() in _TRUE
        if isinstance(default, int):
            return int(raw)
        if isinstance(default, float):
            return float(raw)
    except ValueError:
        raise ConfigError(f'{name}={raw!r} is not a {type(default).__name__}') from None
    return raw
