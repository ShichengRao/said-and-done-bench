"""Erasure migration: python -m erasure.migrate --data data --output output/migration.json"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .holds import retained
from .identity import erased_payloads, requests_for
from .planner import PlanError, choose, clean_views
from .policy import current_policies
from .store import load, original_views, replay


def build(bundle):
    catalog = bundle['catalog']
    nodes, heads = replay(catalog, bundle['changes'])
    views = original_views(nodes)
    erased = erased_payloads(nodes, bundle['identity'], bundle['requests'])
    held = retained(nodes, bundle['holds'], catalog['at'])
    policies = current_policies(bundle['policies'], catalog['at'])
    clean = clean_views(views, lambda row: bool(requests_for(row, bundle['identity'], bundle['requests'])))
    plan = choose(nodes, heads, clean, {r['node'] for r in erased}, policies, held)
    return {'current_heads': [{'object': o, 'node': n} for o, n in sorted(heads.items())],
            'erased_payloads': erased,
            'retained_for_hold': [{'node': n, 'holds': ids} for n, ids in held.items()],
            'plan': plan}


def write_atomic(target, payload):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=target.parent, prefix='.migration-')
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
    parser.add_argument('--output', default='output/migration.json')
    args = parser.parse_args(argv)
    try:
        document = build(load(args.data))
    except (PlanError, ValueError) as error:
        print('migration not written: %s' % error, file=sys.stderr)
        return 2
    write_atomic(args.output, document)
    return 0


if __name__ == '__main__':
    sys.exit(main())
