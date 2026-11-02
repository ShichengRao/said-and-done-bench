import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from .errors import ScheduleError
from .records import load_bundle
from .scheduler import build_schedule, check_schedule


def write_schedule(bundle, output):
    schedule = build_schedule(bundle)
    problems = check_schedule(bundle, schedule)
    if problems:
        raise ScheduleError('schedule failed validation: ' + '; '.join(problems))
    path = Path(output); path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.schedule-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(schedule, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return schedule


def main(argv=None):
    parser = argparse.ArgumentParser(prog='funding_scheduler', description='Build the binding funding schedule')
    sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('schedule')
    command.add_argument('--data', required=True)
    command.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        write_schedule(load_bundle(args.data), args.output)
    except (ScheduleError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print('Funding schedule written to ' + args.output)
    return 0
