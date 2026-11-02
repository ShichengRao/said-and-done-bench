"""Batch runner: python -m reconcile.runner --data data --output output/schedule.json"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .records import load
from .reservations import availability, replay
from .routing import route_options
from .scheduler import ScheduleError, schedule


def build(batch, ledger):
    available = availability(batch, replay(batch, ledger))
    chosen = schedule(batch, route_options(batch), available)
    return {'batch': batch['batch'], 'customer': batch['customer'], 'as_of': batch['as_of'],
            'calls': [{'request': r, 'route': chosen[r]['route'], 'start': chosen[r]['start'], 'pools': chosen[r]['pools']}
                      for r in sorted(chosen)]}


def write_atomic(target, payload):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=target.parent, prefix='.schedule-')
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
    parser.add_argument('--output', default='output/schedule.json')
    args = parser.parse_args(argv)
    try:
        plan = build(*load(args.data))
    except (ScheduleError, ValueError) as error:
        print('schedule not written: %s' % error, file=sys.stderr)
        return 2
    write_atomic(args.output, plan)
    return 0


if __name__ == '__main__':
    sys.exit(main())
