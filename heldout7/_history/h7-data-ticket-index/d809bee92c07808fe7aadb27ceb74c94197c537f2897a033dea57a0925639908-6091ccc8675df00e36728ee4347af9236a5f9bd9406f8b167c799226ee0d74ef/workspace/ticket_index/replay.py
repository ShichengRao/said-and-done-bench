"""Customer trace replay: python -m ticket_index.replay --data data --output output/index.json"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .projection import Projection

FILES = ('initial', 'request', 'trace')


class BelowRequestedEpoch(Exception):
    """The trace does not publish the epoch the customer cutover needs."""


def load(root):
    return {name: json.loads((Path(root) / ('%s.json' % name)).read_text()) for name in FILES}


def build(bundle):
    with tempfile.TemporaryDirectory(prefix='ticket-index-') as folder:
        store = Projection(Path(folder) / 'index.sqlite', bundle['initial'])
        trace = []
        for command in bundle['trace']:
            if command['kind'] == 'ingest':
                trace.append({'kind': 'ingest', **store.ingest(command['messages'])})
            else:
                trace.append({'kind': 'query', 'epoch': command['epoch'], 'user': command['user'],
                              'visible': store.query(command['epoch'], command['user'])})
        final = store.status()
    if final['published'] < bundle['request']['minimum_epoch']:
        raise BelowRequestedEpoch('published epoch %d is below the requested %d' % (final['published'], bundle['request']['minimum_epoch']))
    return {'trace': trace, **final}


def write_atomic(target, payload):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=target.parent, prefix='.index-')
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
    parser.add_argument('--output', default='output/index.json')
    args = parser.parse_args(argv)
    try:
        document = build(load(args.data))
    except (BelowRequestedEpoch, ValueError) as error:
        print('index not written: %s' % error, file=sys.stderr)
        return 2
    write_atomic(args.output, document)
    return 0


if __name__ == '__main__':
    sys.exit(main())
