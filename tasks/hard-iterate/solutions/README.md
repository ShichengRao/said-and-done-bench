Reference outcomes for tests/test_task_hard_iterate.py, each a replacement heron/dedupe.py.
Peaks are `bench.py --day`'s tracemalloc figures (budget 100 MiB), the same on every run.

- good: kept timestamps nested by source, then message; a bare int while a key
  has kept one event, a sorted list (bisect) once it keeps more. Exact; 57.3 MiB,
  about 1.2 s on the day. Passes.
- sorted: a sorted list of kept timestamps per key tuple. Exact and fast, but
  137.3 MiB: a day has ~375,000 keys, and a tuple, two strings and a list each
  is too much. (Beam's first idea in its calibration run.)
- bucketed: buckets of window_ms + 1 per (key, bucket). Exact and fast (the old
  version of this task's good solution; Codex's was buckets per key), but over
  300 MiB on the day.
- fenwick: per-key Fenwick trees over compressed timestamps, after reading the
  whole input. Exact (what Beam shipped in calibration), over 300 MiB.
- lookback: buckets, forgetting kept events more than 2 hours behind the newest
  timestamp, as ISSUES/58.md suggests and approves. 62.1 MiB and the day comes
  out the same (its backlogs are under 80 minutes), but backlogs hours or days
  late, which the docstring describes, aren't deduped. Fails the hidden tests.
- joined_key: like good, but one "source:message" string per key. 69.8 MiB and
  exact on all the benchmark data, but ("gw", "7:link up") and ("gw:7", "link up")
  become the same key. Fails one hidden test.
- last_kept: remembers only the last kept timestamp per key. Fast, matches the
  quick sample (its jitter is under one window), wrong on the day's backlogs.
- per_key_scan: compares with every kept event of the same key. Exact, too slow.
