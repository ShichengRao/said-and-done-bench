"""Cutover migration command: python -m stewardship.migrate --data data --output output/assignments.json"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .ledger import load
from .planner import PlanningError, plan


def write_atomic(target, payload):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=target.parent, prefix='.assignments-')
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
    parser.add_argument('--data', default='data')
    parser.add_argument('--output', default='output/assignments.json')
    args = parser.parse_args(argv)
    try:
        cutover, entries = load(args.data)
        result = plan(cutover, entries)
    except (PlanningError, ValueError) as error:
        print('assignments not written: %s' % error, file=sys.stderr)
        return 2
    write_atomic(args.output, result)
    return 0


if __name__ == '__main__':
    sys.exit(main())
