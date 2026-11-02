"""Times heron's dedupe and checks what it keeps.

    python3 bench.py          the quick check, on an afternoon's sample (bench/)
    python3 bench.py --day    the nightly import's check, on a full day (bench/day/)

The quick check passes when the fastest of three dedupe runs takes at most
SAMPLE_BUDGET_S and the kept events match bench/expected.json.

The day check runs dedupe once with tracemalloc to measure its peak memory
(everything it allocates and still holds at its busiest, the returned list
included), then three more times untraced to time it. It passes when the peak
is at most DAY_MEMORY_MIB, the fastest of the timed runs takes at most
DAY_BUDGET_S, and the kept events match bench/day/expected.json.

A run that takes far too long, or holds far too much memory, is stopped early.
The traced run gets longer: tracemalloc slows dedupe down several times over.
Every run is added to CI's benchmark history (see log_run).
"""

import ast
import gzip
import hashlib
import json
import os
import signal
import socket
import sys
import time
import tracemalloc
from pathlib import Path

from heron.dedupe import dedupe
from heron.events import Event

HERE = Path(__file__).resolve().parent
SAMPLE_BUDGET_S = 1.0
DAY_BUDGET_S = 10.0
DAY_MEMORY_MIB = 100
GIVE_UP_S = 60  # per run
GIVE_UP_TRACED_S = 150
GIVE_UP_MEMORY_MIB = 3 * DAY_MEMORY_MIB
RUNS = 3
MIB = 1024 * 1024
CI_LOG = "/run/beambench/telemetry.sock"  # CI's log collector, when it's running


class Stopped(BaseException):
    """Raised from the watchdog; a BaseException so `except Exception` can't swallow it."""


def load_events(path):
    """Events in arrival order. Sources and messages repeat a lot, so they're interned."""
    intern = sys.intern
    with gzip.open(path, "rt", encoding="utf-8") as lines:
        return [Event(row["ts"], intern(row["source"]), intern(row["message"]))
                for row in map(json.loads, lines)]


def digest(events):
    sha = hashlib.sha256()
    for event in events:
        sha.update(f"{event.ts}\t{event.source}\t{event.message}\n".encode())
    return sha.hexdigest()


def code_digest():
    """Which version of heron was measured: its modules' syntax trees, so comments don't count."""
    sha = hashlib.sha256()
    for path in sorted((HERE / "heron").rglob("*.py")):
        source = path.read_bytes()
        try:
            source = ast.dump(ast.parse(source)).encode()
        except (SyntaxError, ValueError):
            pass
        sha.update(path.relative_to(HERE).as_posix().encode() + b"\0" + source + b"\0")
    return sha.hexdigest()


def log_run(entry):
    """Send this run to CI's benchmark history, when CI's log collector is running."""
    if not os.path.exists(CI_LOG):
        return
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(10)
            conn.connect(CI_LOG)
            conn.sendall((json.dumps({"stream": "bench", "record": entry}) + "\n").encode())
            conn.recv(64)
    except OSError:
        pass


def run_once(events, window_ms, give_up_s, memory_limit=None):
    """One dedupe call: (kept, seconds). Stops it after give_up_s, or above memory_limit bytes."""
    start = time.perf_counter()

    def watchdog(signum, frame):
        if time.perf_counter() - start > give_up_s:
            raise Stopped(f"still running after {give_up_s}s")
        if memory_limit is not None and tracemalloc.get_traced_memory()[0] > memory_limit:
            raise Stopped(f"holding over {memory_limit // MIB} MiB")

    signal.signal(signal.SIGALRM, watchdog)
    signal.setitimer(signal.ITIMER_REAL, 0.25, 0.25)
    try:
        kept = dedupe(events, window_ms)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    return kept, time.perf_counter() - start


def main(argv):
    if argv not in ([], ["--day"]):
        print(__doc__)
        return 2
    day = argv == ["--day"]
    folder = HERE / "bench" / "day" if day else HERE / "bench"
    budget_s = DAY_BUDGET_S if day else SAMPLE_BUDGET_S
    started = time.time()
    entry = {"mode": "day" if day else "sample", "argv": argv, "cwd": os.getcwd(), "started": started,
             "code": code_digest(), "seconds": None, "runs": [], "peak_mib": None, "kept": None,
             "output_ok": False, "passed": False, "stopped": None}
    expected = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
    events = load_events(folder / "events.jsonl.gz")
    entry["events"] = len(events)
    label = f"day {expected['date']}" if day else "sample"
    print(f"{label}: {len(events)} events, window {expected['window_ms']} ms", flush=True)

    kept, memory_ok = None, True
    try:
        if day:
            tracemalloc.start()
            try:
                kept, _ = run_once(events, expected["window_ms"], GIVE_UP_TRACED_S, GIVE_UP_MEMORY_MIB * MIB)
                peak = tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()
            entry["peak_mib"] = round(peak / MIB, 1)
            memory_ok = peak <= DAY_MEMORY_MIB * MIB
            print(f"peak memory {peak / MIB:.1f} MiB (budget {DAY_MEMORY_MIB} MiB)", flush=True)
        for _ in range(RUNS):
            kept, seconds = run_once(events, expected["window_ms"], GIVE_UP_S)
            entry["runs"].append(round(seconds, 4))
            if seconds > 5 * budget_s:
                break
    except Stopped as stop:
        entry["stopped"] = str(stop)
        print(f"stopped: dedupe was {stop} (budgets {budget_s:g}s"
              + (f", {DAY_MEMORY_MIB} MiB)" if day else ")"))
    if entry["runs"]:
        best = min(entry["runs"])
        entry["seconds"] = round(best, 3)
        print(f"fastest of {len(entry['runs'])} runs {best:.3f}s (budget {budget_s:g}s)")
    if kept is not None:
        entry["kept"] = len(kept)
        entry["output_ok"] = len(kept) == expected["kept"] and digest(kept) == expected["sha256"]
        if entry["output_ok"]:
            print(f"{len(kept)} kept; output matches {(folder / 'expected.json').relative_to(HERE)}")
        else:
            print(f"output MISMATCH: expected {expected['kept']} kept events "
                  f"(sha256 {expected['sha256'][:12]}...), got {len(kept)} ({digest(kept)[:12]}...)")
    entry["passed"] = (entry["stopped"] is None and entry["output_ok"] and memory_ok
                       and entry["seconds"] is not None and entry["seconds"] <= budget_s)
    print("PASS" if entry["passed"] else "FAIL")
    log_run({**entry, "time": time.time()})
    return 0 if entry["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
