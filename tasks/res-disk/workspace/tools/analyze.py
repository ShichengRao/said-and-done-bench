#!/usr/bin/env python3
"""Analyze a gateway capture (a replay's or a production one).

    python3 tools/analyze.py /scratch/replay/<run>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gateway import analysis  # noqa: E402


def main(argv):
    if len(argv) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    stats = analysis.analyze(argv[0])
    if stats is None:
        print(f'error: no capture records in {argv[0]}', file=sys.stderr)
        return 1
    print(stats.summary())
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
