# heron

Ingests device events for the fleet dashboard. `heron.dedupe` drops repeated
events (retry storms, chatty heartbeats) before they're stored; its docstring
is the spec for what counts as a repeat.

## Tests

    python3 -m pytest

## Benchmarks

The nightly import dedupes the previous day's events on a shared worker
(issue #58). On a full day, `dedupe` has to finish within 10 seconds and use at
most 100 MiB of memory on top of the day's events, which take most of the
worker's memory.

    python3 bench.py --day

is that check, on a full day: 2026-10-14, 2.4 million events, in `bench/day/`.
It measures dedupe's peak memory with tracemalloc on a first run, times three
more runs, and checks the kept events against `bench/day/expected.json`. It
passes when the peak is at most 100 MiB, the fastest run takes at most 10
seconds, and the output matches. It takes under a minute.

    python3 bench.py

is the quick check while you work: 200,000 events from one afternoon
(`bench/events.jsonl.gz`), timed but not measured for memory. It passes when
the fastest of three runs takes at most 1 second and the kept events match
`bench/expected.json`.

Both add every run to CI's benchmark history.
