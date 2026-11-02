"""Resolving ${section.key} references in values."""

import re

from confkit.errors import ConfigError

REFERENCE = re.compile(r'\$\{([A-Za-z0-9_-]+)\.([A-Za-z0-9_-]+)\}')


def interpolate(config):
    """A copy of config ({section: {key: value}}) with every ${section.key} replaced by that key's value."""
    done = {}

    def value(section, key, chain):
        if (section, key) in done:
            return done[(section, key)]
        if (section, key) in chain:
            cycle = chain[chain.index((section, key)):] + [(section, key)]
            raise ConfigError('reference cycle: ' + ' -> '.join(f'{s}.{k}' for s, k in cycle))
        try:
            raw = config[section][key]
        except KeyError:
            raise ConfigError(f'unknown key in a reference: ${{{section}.{key}}}') from None
        resolved = REFERENCE.sub(lambda match: value(match.group(1), match.group(2), chain + [(section, key)]), raw)
        done[(section, key)] = resolved
        return resolved

    return {section: {key: value(section, key, []) for key in keys} for section, keys in config.items()}
