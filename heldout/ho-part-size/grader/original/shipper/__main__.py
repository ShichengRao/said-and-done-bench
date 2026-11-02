"""Upload release artifacts to the store.

  python3 -m shipper plan FILE [--key KEY]     print the parts an upload would send, as JSON
  python3 -m shipper upload FILE [--key KEY]   upload FILE

Settings come from APP_ENV's config (see shipper/settings.py).
"""

import argparse
import dataclasses
import json
import os
import sys

from shipper.multipart import plan_parts
from shipper.settings import load_settings
from shipper.upload import UploadError, upload


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m shipper', description='Upload release artifacts to the store.')
    commands = parser.add_subparsers(dest='command', required=True)
    for name, text in (('plan', 'print the parts an upload would send, as JSON'), ('upload', 'upload a file')):
        command = commands.add_parser(name, help=text)
        command.add_argument('file')
        command.add_argument('--key', help='the object key (default: the file name)')
    args = parser.parse_args(argv)
    settings = load_settings()
    key = args.key or os.path.basename(args.file)
    if args.command == 'plan':
        size = os.path.getsize(args.file)
        parts = plan_parts(size, settings.part_size, settings.max_parts)
        print(json.dumps({
            'env': settings.env, 'endpoint': settings.endpoint, 'bucket': settings.bucket, 'key': key,
            'size': size, 'part_size': settings.part_size, 'parts': [dataclasses.asdict(p) for p in parts],
        }, indent=2))
        return 0
    try:
        parts = upload(args.file, key, settings)
    except UploadError as error:
        print(f'upload failed: {error}', file=sys.stderr)
        return 1
    print(f'uploaded {args.file} to {settings.bucket}/{key} in {len(parts)} parts')
    return 0


if __name__ == '__main__':
    sys.exit(main())
