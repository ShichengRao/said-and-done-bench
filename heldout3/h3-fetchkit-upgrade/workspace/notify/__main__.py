"""notify's command line.

    python3 -m notify send --to +4915112345678 --text "Your order has shipped"

NOTIFY_PROVIDER_URL and NOTIFY_PROVIDER_TOKEN say where to send it (see notify/settings.py).
"""

import argparse
import sys

from notify.sender import SendFailed, send


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m notify')
    commands = parser.add_subparsers(dest='command', required=True)
    sending = commands.add_parser('send', help='send one text message')
    sending.add_argument('--to', required=True, help='phone number, international format')
    sending.add_argument('--text', required=True)
    args = parser.parse_args(argv)
    try:
        message_id = send(args.to, args.text)
    except SendFailed as error:
        print(f'not sent: {error}', file=sys.stderr)
        return 1
    print(f'sent {message_id}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
