"""hooks' command line.

    python3 -m hooks preview SUBSCRIBER [--event order.created]   the request a delivery would make
    python3 -m hooks send SUBSCRIBER [--event order.created]      deliver a sample event

Each subscriber's signing secret comes from the environment variable that
config/subscriptions.toml names. HOOKS_REDIRECT sends deliveries somewhere
else (see hooks.receiver).
"""

import argparse
import sys
import time

from hooks import delivery, events, subscriptions


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m hooks')
    commands = parser.add_subparsers(dest='command', required=True)
    for name, text in (('preview', 'print the request a delivery would make'), ('send', 'deliver a sample event')):
        command = commands.add_parser(name, help=text)
        command.add_argument('subscriber')
        command.add_argument('--event', default='order.created',
                             choices=['order.created', 'order.cancelled', 'shipment.dispatched'])
    args = parser.parse_args(argv)
    try:
        subscription = subscriptions.get(args.subscriber)
        body = events.sample(args.event, int(time.time()))
        if args.command == 'preview':
            url, headers, body = delivery.build(subscription, body)
            print(f'POST {url}')
            for name, value in headers.items():
                print(f'{name}: {value}')
            print()
            print(body.decode())
        else:
            print(f'{args.subscriber}: {delivery.deliver(subscription, body)}')
    except LookupError as error:
        print(error, file=sys.stderr)
        return 2
    except OSError as error:
        print(f'{args.subscriber}: delivery failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
