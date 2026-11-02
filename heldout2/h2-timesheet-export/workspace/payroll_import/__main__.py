"""python3 -m payroll_import [EXPORT]: load the timesheet export (default: settings.SOURCE) into payroll.

Payroll's scheduler runs this every night after the export. Rows that don't
parse are skipped and reported; the rest are loaded.
"""

import sys
from pathlib import Path

from payroll_import import settings
from payroll_import.load import ExportError, read, store


def main(argv):
    source = Path(argv[0]) if argv else settings.SOURCE
    try:
        rows, problems = read(source)
    except (OSError, ExportError) as error:
        print(f'payroll_import: {error}', file=sys.stderr)
        return 2
    for problem in problems:
        print(f'payroll_import: {problem}; row skipped', file=sys.stderr)
    store(rows, settings.DATABASE)
    print(f'payroll_import: loaded {len(rows)} rows from {source} ({len(problems)} skipped)')
    return 0


sys.exit(main(sys.argv[1:]))
