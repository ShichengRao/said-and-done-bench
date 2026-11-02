"""Checkpoint publisher: python -m checkpoint.publish --data data --output output/checkpoint.json"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .cut import consistent_cut, covers, reach
from .evidence import delivered, load, manifest
from .replay import replay


class BelowMinimum(Exception):
    """The greatest consistent checkpoint does not reach the requested minimum."""


def build(export):
    table = manifest(export)
    logs = delivered(export, table)
    cut = consistent_cut(table, reach(export, logs))
    minimum = export['request']['minimum']
    short = sorted(s for s in cut if cut[s] < minimum[s])
    if short:
        raise BelowMinimum('checkpoint %s is below the requested minimum on %s' % (cut, ', '.join(short)))
    included = sorted((t for t in table.values() if covers(t, cut)), key=lambda t: t['order'])
    customers, aliases = replay(export['snapshot'], included)
    return {'cut': cut, 'included': [t['id'] for t in included],
            'applied': [t['id'] for t in included if t['decision'] == 'commit'],
            'deferred': sorted(t for t in table if not covers(table[t], cut)),
            'customers': customers, 'aliases': aliases}


def write_atomic(target, payload):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=target.parent, prefix='.checkpoint-')
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
    parser.add_argument('--output', default='output/checkpoint.json')
    args = parser.parse_args(argv)
    try:
        document = build(load(args.data))
    except (BelowMinimum, ValueError) as error:
        print('checkpoint not published: %s' % error, file=sys.stderr)
        return 2
    write_atomic(args.output, document)
    return 0


if __name__ == '__main__':
    sys.exit(main())
