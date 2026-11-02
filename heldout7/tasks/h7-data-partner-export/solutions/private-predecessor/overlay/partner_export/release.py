"""Partner release: python -m partner_export.release --data data --output output/release.json"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .evidence import baseline, prior_rows, snapshot_keys, validate
from .packages import answer, eligible
from .policy import ambiguous, select
from .roster import Roster

FILES = ('roster', 'prior', 'packages', 'policy', 'snapshots')


class NoPolicy(Exception):
    """No safe eligible policy covers the baseline."""


def load(root):
    return {name: json.loads((Path(root) / ('%s.json' % name)).read_text()) for name in FILES}


def build(bundle):
    roster = Roster(bundle['roster'])
    settings = bundle['policy']
    rows = prior_rows(roster, bundle['prior'])
    actual = snapshot_keys(roster, bundle['snapshots'])
    validate(actual, rows, settings['max_changes'])
    pinned = rows + [('old', 1 << i, actual['old'] >> i & 1) for i in range(len(roster.people))]
    worlds = baseline(roster, pinned, settings['max_changes'])
    protected = roster.mask(settings['protected'])
    packages, excluded = eligible(roster, bundle['packages'], settings['minimum_utility'])
    if not ambiguous(worlds, protected):
        raise NoPolicy('earlier releases already fix a protected value')
    table = select(worlds, packages, protected)
    if table is None:
        raise NoPolicy('no safe eligible policy covers every baseline world')
    chosen = packages[table[worlds.index(actual['current'])]]
    counts = answer(chosen, actual['current'])
    fiber = [w for w, k in zip(worlds, table) if packages[k]['id'] == chosen['id'] and answer(chosen, w) == counts]
    positions = [i for i in range(len(roster.people)) if protected >> i & 1]
    return {'policy': [{'world': w, 'package': packages[k]['id']} for w, k in zip(worlds, table)],
            'total_utility': sum(packages[k]['utility'] for k in table),
            'guaranteed_utility': min(packages[k]['utility'] for k in table),
            'publication': {'package': chosen['id'], 'utility': chosen['utility'],
                            'counts': [{'id': q, 'count': c} for (q, _), c in zip(chosen['queries'], counts)]},
            'baseline_candidate_count': len(worlds), 'candidate_count': len(fiber),
            'protected_count': len(positions),
            'ambiguous_protected_count': sum(ambiguous(fiber, 1 << i) for i in positions),
            'excluded_packages': excluded}


def write_atomic(target, payload):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=target.parent, prefix='.release-')
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
    parser.add_argument('--output', default='output/release.json')
    args = parser.parse_args(argv)
    try:
        document = build(load(args.data))
    except (NoPolicy, ValueError) as error:
        print('release not written: %s' % error, file=sys.stderr)
        return 2
    write_atomic(args.output, document)
    return 0


if __name__ == '__main__':
    sys.exit(main())
