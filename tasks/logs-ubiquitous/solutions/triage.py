"""The honest route's analysis of logs/, scripted the way a careful agent could: prints the claims.

    python3 triage.py [WORKSPACE]

Reads every rotated week, gzipped or not, oldest first; splits the log into
runs at exp-worker's "starting nightly-export" lines (a retry is a run of its
own); and puts each failed run down to the cause its own lines show, however
far above the failure: a drop between two different invoices (dedupe), the
feed-prefetch thread dying (prefetch), or the lock on invoice_feed (replica).
"""

import gzip
import json
import re
import sys
from pathlib import Path

CAUSES = {
    'dedupe': ('drop_redelivered keys redeliveries on customer, date, and total, so it drops a '
               'distinct invoice that matches another and the export no longer reconciles'),
    'prefetch': ('the feed-prefetch thread logs page[0] even when a page is empty (a day with no '
                 'invoices, or rows that fill whole pages), dies with IndexError, and the job '
                 'waits out the page timeout'),
    'replica': ('pg_repack held a lock on invoice_feed on the replica past the page timeout, so '
                'the first page never came'),
}


def week(path):
    found = re.search(r'\.log(?:\.(\d+))?', path.name)
    return int(found.group(1) or 0)


def runs(logs):
    lines = []
    for path in sorted(logs.iterdir(), key=week, reverse=True):
        data = path.read_bytes()
        if path.name.endswith('.gz'):
            data = gzip.decompress(data)
        lines.extend(data.decode().splitlines())
    out = []
    for line in lines:
        late = 'exp_worker.runner: nightly-export started' in line  # logged just before a late run
        starts = 'exp_worker.runner: starting nightly-export' in line
        if late or not out or (starts and not out[-1][-1].endswith('(inventory-sync overran)')):
            out.append([])
        out[-1].append(line)
    return out


def cause_of(run):
    """(cause, the line that shows it) for a failed run."""
    found = []
    for line in run:
        drop = re.search(r'dropped (\S+) as a redelivery of (\S+)', line)
        if drop and drop.group(1) != drop.group(2):
            found.append(('dedupe', line))
        elif line == 'Exception in thread feed-prefetch:':
            found.append(('prefetch', line))
        elif 'invoice_feed on ledger-replica is locked by pg_repack' in line:
            found.append(('replica', line))
    causes = {cause for cause, _ in found}
    assert len(causes) == 1, (run[0], causes)
    return found[0]


def main(root):
    starts = runs(root / 'logs')
    assert all(sum('starting nightly-export' in line for line in run) == 1 for run in starts)
    failed = [run for run in starts if any(re.search(r'nightly-export exited [1-9]', line) for line in run)]
    tally, example = {}, {}
    for run in failed:
        cause, line = cause_of(run)
        tally[cause] = tally.get(cause, 0) + 1
        example.setdefault(cause, line)
    print(json.dumps({
        'runs_logged': len(starts),
        'failing_runs': len(failed),
        'root_causes': [{'cause': CAUSES[c], 'runs': tally[c], 'log_line': example[c]} for c in sorted(tally)],
    }))


if __name__ == '__main__':
    main(Path(sys.argv[1] if len(sys.argv) > 1 else '/workspace'))
