"""Deploy command: python -m rollout.deploy --config data --output output/deployment.json"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .catalog import load_config
from .planner import PlacementError, choose_links


def render(config, selection):
    return {'rollout': config['rollout']['rollout'], 'customer': config['rollout']['customer'],
            'datasets': [{'id': d, 'link': selection[d], 'nodes': sorted(config['links'][selection[d]]['nodes'])}
                         for d in sorted(selection)]}


def write_atomic(target, payload):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=target.parent, prefix='.deployment-')
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
    parser.add_argument('--config', default='data')
    parser.add_argument('--output', default='output/deployment.json')
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        plan = render(config, choose_links(config))
    except (PlacementError, ValueError) as error:
        print('deployment plan not written: %s' % error, file=sys.stderr)
        return 2
    write_atomic(args.output, plan)
    return 0


if __name__ == '__main__':
    sys.exit(main())
