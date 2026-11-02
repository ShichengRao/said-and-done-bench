"""relay's command line.

    python3 -m relay run      start relaying (Ctrl-C stops it)
    python3 -m relay check    check the configuration and say what's wrong with it
    python3 -m relay config   print the effective settings, credentials masked

Settings come from relay.config.load(): the defaults, the config file
($RELAY_CONFIG or config/relay.toml), then RELAY_* environment variables.
"""

import argparse
import json
import sys

from relay import config, logs
from relay.redact import MASK, is_secret_key, mask_url


def run(settings, once=False):
    log = logs.setup(settings['log']['level'])
    service = settings['service']
    log.info('starting %s: %d workers, batches of %d, from %s to %s', service['name'], service['workers'],
             service['batch_size'], mask_url(settings['upstream']['url']), mask_url(settings['broker']['url']))
    if service['dry_run']:
        log.info('dry run: nothing will be published')
    if once:
        return 0
    from relay.loop import relay_forever
    return relay_forever(settings)


def effective_lines(settings):
    """Every setting as a `section.key = value` line, sorted, with credentials masked (SECURITY.md)."""
    lines = []
    for section in sorted(settings):
        for key in sorted(settings[section]):
            value = settings[section][key]
            if is_secret_key(key) and value:
                value = MASK
            lines.append(f'{section}.{key} = {json.dumps(value)}')
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m relay')
    commands = parser.add_subparsers(dest='command', required=True)
    running = commands.add_parser('run', help='start relaying')
    running.add_argument('--once', action='store_true', help='start up, log the settings, and stop')
    commands.add_parser('check', help='check the configuration')
    commands.add_parser('config', help='print the effective settings, credentials masked')
    args = parser.parse_args(argv)
    try:
        settings = config.load()
    except config.ConfigError as error:
        print(f'configuration error: {error}', file=sys.stderr)
        return 2
    if args.command == 'check':
        print('configuration OK')
        return 0
    if args.command == 'config':
        print('\n'.join(effective_lines(settings)))
        return 0
    return run(settings, once=args.once)


if __name__ == '__main__':
    sys.exit(main())
