"""Reading the access logs: logs/<ISO week>/access-<date>.log.

A line is a timestamp and key=value fields:

    2026-10-12T09:14:03.120Z svc=api route=/v1/orders status=200 dur_ms=87 sample_rate=1
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NUMBERS = ('status', 'dur_ms', 'sample_rate')


def parse(line):
    stamp, _, rest = line.strip().partition(' ')
    record = {'ts': stamp}
    for item in rest.split():
        key, _, value = item.partition('=')
        record[key] = int(value) if key in NUMBERS else value
    return record


def week_folder(week, root=ROOT):
    return Path(root) / 'logs' / week


def read_week(week, root=ROOT):
    """Every record in the week's logs, day by day."""
    folder = week_folder(week, root)
    paths = sorted(folder.glob('access-*.log'))
    if not paths:
        raise FileNotFoundError(f'no logs for {week} in {folder}')
    for path in paths:
        with open(path, encoding='utf-8') as handle:
            for line in handle:
                if line.strip():
                    yield parse(line)
