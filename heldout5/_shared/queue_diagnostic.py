"""Wait for the active batch to close, then start the requested M2.7 diagnostic.

No automatic retries, provider switching, task revision, or partial-slate selection.
If the anchors do not satisfy the criterion, the coordinator must review first.
"""
import fcntl
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calibrate
import summarize


def main():
    with (calibrate.RUNS / 'control/scheduler.lock').open('r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = summarize.collect()
        if result['strict_calibration_tasks'] != 20:
            raise SystemExit('Diagnostic not started: anchor outcomes require coordinator review.')
        ids = [row['task'] for row in result['tasks']]
        if any((calibrate.RUNS / task / 'v1-minimax-m2-7').exists() for task in ids):
            raise SystemExit('Diagnostic already attempted; preserve it and review explicitly.')
    command = [calibrate.PYTHON, str(calibrate.HERE / '_shared/calibrate.py'),
               *ids, '--revision', 'v1', '--models', 'minimax-m2-7', '--diagnostic-lane']
    return subprocess.call(command, cwd=calibrate.ROOT)


if __name__ == '__main__':
    raise SystemExit(main())
