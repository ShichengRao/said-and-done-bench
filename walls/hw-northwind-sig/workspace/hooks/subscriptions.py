"""Who gets webhooks: config/subscriptions.toml, with each signing secret from the environment."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / 'config' / 'subscriptions.toml'


@dataclass(frozen=True)
class Subscription:
    name: str
    url: str
    events: tuple
    secret_env: str

    @property
    def secret(self):
        secret = os.environ.get(self.secret_env)
        if not secret:
            raise LookupError(f'{self.name}: no signing secret in ${self.secret_env}')
        return secret


def load(path=CONFIG):
    with open(path, 'rb') as handle:
        data = tomllib.load(handle)
    return {name: Subscription(name, entry['url'], tuple(entry['events']), entry['secret_env'])
            for name, entry in data.items()}


def get(name, path=CONFIG):
    found = load(path)
    if name not in found:
        raise LookupError(f'no subscription named {name!r} (have: {", ".join(sorted(found))})')
    return found[name]
