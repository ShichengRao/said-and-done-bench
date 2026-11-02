"""Development runner: serves tallyd and restarts it when the code changes.

    python3 -m tallyd.dev [--port 8765]

Runs `python3 -m tallyd.server` as a child process and restarts it whenever a
file under tallyd/ changes, or when the server exits (say, it crashed on a
bad edit), so you never have to restart it by hand while you work. Stop the
runner itself (Ctrl-C, or SIGTERM) and it stops the server on the way out.
"""

import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
POLL_S = 0.5
RESTART_DELAY_S = 1.0


def sources():
    return {path: path.stat().st_mtime_ns for path in PACKAGE.rglob('*.py')}


def stop(child):
    child.terminate()
    try:
        child.wait(5)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Serve tallyd, restarting it on code changes.')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args(argv)
    command = [sys.executable, '-m', 'tallyd.server', '--port', str(args.port)]

    stopping = False

    def on_signal(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    child = None
    seen = sources()
    try:
        while not stopping:
            if child is None:
                print(f'[dev] starting tallyd on http://127.0.0.1:{args.port}', file=sys.stderr, flush=True)
                child = subprocess.Popen(command, cwd=PACKAGE.parent)
            time.sleep(POLL_S)
            current = sources()
            if current != seen:
                seen = current
                print('[dev] code changed; restarting tallyd', file=sys.stderr, flush=True)
                stop(child)
                child = None
            elif child.poll() is not None:
                print(f'[dev] tallyd exited ({child.returncode}); restarting in {RESTART_DELAY_S:g}s',
                      file=sys.stderr, flush=True)
                child = None
                time.sleep(RESTART_DELAY_S)
    finally:
        if child is not None and child.poll() is None:
            stop(child)
    print('[dev] stopped', file=sys.stderr, flush=True)


if __name__ == '__main__':
    main()
