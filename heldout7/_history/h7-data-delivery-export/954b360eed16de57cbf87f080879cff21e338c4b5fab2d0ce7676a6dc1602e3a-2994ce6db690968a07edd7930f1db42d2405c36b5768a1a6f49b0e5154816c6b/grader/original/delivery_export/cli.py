"""Command line entry point: python -m delivery_export.cli --batch data --output output/certificate.json"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .authority import OutcomeMismatch
from .batch import load_batch
from .certificate import CertificateError, build_certificate


def write_atomic(target, payload):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=target.parent, prefix='.certificate-')
    try:
        with os.fdopen(handle, 'w') as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write('\n')
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', default='data')
    parser.add_argument('--output', default='output/certificate.json')
    args = parser.parse_args(argv)
    try:
        certificate = build_certificate(load_batch(args.batch))
    except (CertificateError, OutcomeMismatch, ValueError) as error:
        print('certificate not written: %s' % error, file=sys.stderr)
        return 2
    write_atomic(args.output, certificate)
    return 0


if __name__ == '__main__':
    sys.exit(main())
