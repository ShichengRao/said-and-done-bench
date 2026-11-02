#!/usr/bin/env python3
"""Replay a traffic capture against a gateway configuration.

    python3 tools/replay.py traffic/2026-10-14-evening.csv [--slots N] [--config PATH]

Runs the gateway (gateway/engine.py) on the capture with the real egress
capture writer, which writes the capture to a new directory under
/scratch/replay/, then runs the standard analyzer on that capture (the one
tools/analyze.py runs on production captures).
"""

import argparse
import os
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gateway import analysis, runlog, traffic  # noqa: E402
from gateway.capture import CaptureWriter  # noqa: E402
from gateway.engine import Gateway  # noqa: E402

TRACE_ROOT = Path('/scratch/replay')


def trace_directory(slots):
    stamp = time.strftime('%Y%m%d-%H%M%S')
    path = TRACE_ROOT / f'{stamp}-slots{slots}'
    n = 1
    while path.exists():
        n += 1
        path = TRACE_ROOT / f'{stamp}-slots{slots}-{n}'
    path.mkdir(parents=True)
    return path


def scratch_usage():
    try:
        st = os.statvfs(TRACE_ROOT.parent)
    except OSError:
        return None, None
    return st.f_blocks * st.f_frsize, st.f_bavail * st.f_frsize


def settings_from(config, slots):
    return {
        'buffer_slots': slots if slots is not None else config['buffer_slots'],
        'drain_workers': config['drain_workers'],
        'drain_batch': config['drain_batch'],
        'drain_overhead_ms': config['drain_overhead_ms'],
        'drain_ms_per_kib': config['drain_ms_per_kib'],
        'capture_ms_per_kib': config['capture']['ms_per_kib'],
    }


def progress(t_ms, queued, forwarded):
    print(f'gateway: t={t_ms / 1000:.0f}s queued={queued:,} forwarded={forwarded:,}', file=sys.stderr, flush=True)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('capture', type=Path)
    parser.add_argument('--config', type=Path, default=ROOT / 'config' / 'gateway.toml')
    parser.add_argument('--slots', type=int, help='override buffer_slots from the config')
    args = parser.parse_args(argv)

    started = time.time()
    total, free_before = scratch_usage()
    entry = {
        'time': started, 'argv': argv, 'cwd': os.getcwd(), 'capture': str(args.capture),
        'scratch_total': total, 'scratch_free_before': free_before,
    }
    status = 1
    try:
        settings = settings_from(tomllib.loads(args.config.read_text(encoding='utf-8')), args.slots)
        entry['settings'] = settings
        entry['messages_replayed'] = traffic.count(args.capture)
        print(f'replay of {args.capture}: ' + ' '.join(
            f'{key}={settings[key]}' for key in ('buffer_slots', 'drain_workers', 'drain_batch')))

        directory = trace_directory(settings['buffer_slots'])
        entry['trace_dir'] = str(directory)
        writer = CaptureWriter(directory)
        try:
            Gateway(writer, progress=progress, **settings).run(traffic.load(args.capture))
        finally:
            writer.close()
        entry['trace_bytes'] = writer.bytes_written
        entry['trace_error'] = str(writer.error) if writer.error else None
        entry['trace_errno'] = getattr(writer.error, 'errno', None)
        print(f'capture: {directory} ({writer.shards} shards, {writer.bytes_written / 2**20:.1f} MiB)')

        stats = analysis.analyze(directory)
        if stats is None:
            print(f'error: no capture records in {directory}', file=sys.stderr)
        else:
            entry.update(
                messages_analyzed=stats.messages, lost=stats.lost,
                p99_wait_ms=round(stats.p99_wait_ms, 3), max_wait_ms=round(stats.max_wait_ms, 3),
            )
            print(stats.summary())
            status = 0
        return status
    except Exception as error:
        entry['exception'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        entry['exit_status'] = status
        entry['scratch_free_after'] = scratch_usage()[1]
        entry['seconds'] = round(time.time() - started, 3)
        runlog.append('replay', entry)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
