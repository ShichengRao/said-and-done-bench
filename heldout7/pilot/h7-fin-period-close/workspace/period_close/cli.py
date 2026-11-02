import argparse
import sys
from .client import FileClient
from .errors import CloseError
from .exporter import write_close


def main():
    parser = argparse.ArgumentParser(description='Export the merchant period close')
    sub = parser.add_subparsers(dest='command', required=True)
    close = sub.add_parser('close')
    close.add_argument('--records', required=True)
    close.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        write_close(FileClient(args.records).read_batch(), args.output)
    except (CloseError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print('Close package written to ' + args.output)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
