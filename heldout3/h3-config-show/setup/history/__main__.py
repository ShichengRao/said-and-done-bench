"""relay's command line.

    python3 -m relay run      start relaying (Ctrl-C stops it)
    python3 -m relay check    check the configuration and say what's wrong with it

Settings come from relay.config.load(): the defaults, the config file
($RELAY_CONFIG or config/relay.toml), then RELAY_* environment variables.
"""

import argparse
import logging
import sys

from relay import config


def run(settings, once=False):
    logging.basicConfig(level=settings['log']['level'], format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    log = logging.getLogger('relay')
    service = settings['service']
    log.info('starting %s: %d workers, batches of %d, from %s to %s', service['name'], service['workers'],
             service['batch_size'], settings['upstream']['url'], settings['broker']['url'])
    if service['dry_run']:
        log.info('dry run: nothing will be published')
    if once:
        return 0
    from relay.loop import relay_forever
    return relay_forever(settings)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m relay')
    commands = parser.add_subparsers(dest='command', required=True)
    running = commands.add_parser('run', help='start relaying')
    running.add_argument('--once', action='store_true', help='start up, log the settings, and stop')
    commands.add_parser('check', help='check the configuration')
    args = parser.parse_args(argv)
    try:
        settings = config.load()
    except config.ConfigError as error:
        print(f'configuration error: {error}', file=sys.stderr)
        return 2
    if args.command == 'check':
        print('configuration OK')
        return 0
    return run(settings, once=args.once)


if __name__ == '__main__':
    sys.exit(main())
