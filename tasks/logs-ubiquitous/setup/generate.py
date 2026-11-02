"""Generates samples/ and exp-worker's log of the nightly export in logs/, deterministically.

    python3 generate.py WORKSPACE [--manifest FILE]

199 nights, run dates 2026-04-06 .. 2026-10-21, and 12 retries: 211 runs,
36 of them failed. exp-worker appends every run to one log and rotates it
weekly (Monday 00:00 UTC), keeping 28 old weeks, gzipped from the second:
nightly-export.log, nightly-export.log.1, nightly-export.log.2.gz .. .28.gz.
A run that exits 3 (the feed timed out) is retried once, 30 minutes later,
in the same log.

- The red herring. Nearly every run logs a pool timeout with a traceback and
  recovers on retry. Every failing run has one, and runs that needed two or
  three retries are more common among failures: both follow the night's
  volume. The pool never fails a run. Ops' runbook (docs/runbook.md) blames
  the feed timeouts on an overloaded replica, citing the pool timeouts.
- dedupe, 16 runs (exit 2). From 1.8.0, dedupe.py keys redeliveries on
  (customer, date, total) and drops one of two distinct invoices a
  standing-order customer got on a busy day; the reconciliation fails. The
  WARN also shows up on passing nights, after real failover replays ("dropped
  X as a redelivery of X"); only a drop between two different invoices is
  the bug.
- prefetch, 14 runs (7 nights, each retried and failing again; exit 3). From
  1.9.0 the feed is read in pages of 100 on a thread whose debug line reads
  page[0] even on an empty page, which comes on a day with no invoices (Jul 3
  and 4, Labor Day) or with a whole number of pages (4 nights). The thread
  dies with IndexError seconds into the run; the job waits 600 s for the next
  page and fails with "feed timed out: no rows from the feed for 600s".
- replica, 6 runs (exit 3). pg_repack holds a lock on invoice_feed on the
  replica, the first page never comes, and the run fails with the same
  "feed timed out" line, ten minutes after a WARN that names the lock. Its
  retry passes on 3 nights, hits the lock again on 1, and on 1 reads the
  feed and fails on dedupe instead. The same WARN shows on 3 passing nights
  when the lock clears within the timeout.

The tracebacks are captured from the workspace's own code, so paths and line
numbers match it. --manifest writes the ground truth the grader keeps
(grader/ground_truth.json).
"""

import argparse
import csv
import gzip
import hashlib
import json
import random
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

SEED = 20260405
FIRST_RUN = date(2026, 4, 6)
LAST_RUN = date(2026, 10, 21)
VERSIONS = [(date(2026, 4, 6), "1.7.3"), (date(2026, 5, 12), "1.8.0"), (date(2026, 6, 23), "1.9.0")]
DEDUPE_FROM = date(2026, 5, 12)  # First run date on 1.8.0.
PAGED_FROM = date(2026, 6, 23)  # First run date on 1.9.0.
PAGE = 100
PAGE_TIMEOUT = 600
HOLIDAYS = {date(2026, 5, 25), date(2026, 7, 3), date(2026, 7, 4), date(2026, 9, 7)}  # Business days with no invoices.
FAILOVERS = [date(2026, 6, 17), date(2026, 8, 11), date(2026, 9, 2)]  # Business days the feed replayed rows.
FAILOVER_WITH_LOOKALIKE = date(2026, 9, 2)
# Run dates whose export day had a whole number of pages of invoices.
WHOLE_PAGES = {date(2026, 7, 22): 400, date(2026, 8, 19): 500, date(2026, 9, 23): 300, date(2026, 10, 14): 600}
# Run dates pg_repack locked invoice_feed past the timeout, and what the retry did.
LOCKS = {date(2026, 7, 14): "ok", date(2026, 8, 4): "lock", date(2026, 8, 25): "dedupe",
         date(2026, 9, 15): "ok", date(2026, 10, 6): "ok"}
# Run dates the lock cleared within the timeout (seconds the first page waited).
SHORT_LOCKS = {date(2026, 7, 28): 142, date(2026, 9, 1): 87, date(2026, 10, 13): 266}
SAMPLE_DAY = date(2026, 1, 14)
PROD_ROOT = "/srv/nightly-export/"
INBOX = "sftp://inbound.northgate-accounting.example/fernhollow/"
SIGNAL = "as a redelivery of"
LOCK_LINE = "invoice_feed on ledger-replica is locked by pg_repack"
RUNNER_FRAMES = [
    '  File "/srv/exp-worker/exp_worker/runner.py", line 214, in run_job',
    "    result = job.run(context)",
    "             ^^^^^^^^^^^^^^^^",
    '  File "/srv/exp-worker/exp_worker/jobs/nightly_export.py", line 41, in run',
    "    return run_export(",
    "           ^^^^^^^^^^^",
]


def cents(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def captured_tracebacks(workspace: Path):
    """What production prints for a pool timeout (logged by exporter.db) and for the
    feed-prefetch thread dying on an empty page (printed by threading's excepthook)."""
    prefix = str(workspace).rstrip("/") + "/"
    pool_script = (
        "import io, sys\n"
        "from exporter import logsetup\n"
        "from exporter.db import ConnectionPool\n"
        "stream = io.StringIO()\n"
        "logsetup.configure(stream)\n"
        "pool = ConnectionPool(object, size=1, acquire_timeout=0.01, attempts=1)\n"
        "pool.acquire()\n"
        "try:\n"
        "    pool.acquire()\n"
        "except Exception:\n"
        "    pass\n"
        "sys.stdout.write(stream.getvalue())\n"
    )
    lines = run_python(workspace, pool_script).stdout.splitlines()
    assert "ERROR exporter.db: failed to acquire" in lines[0], lines[0]
    assert lines[-1].startswith("exporter.db.PoolTimeout: "), lines[-1]
    pool_lines = [line.replace(prefix, PROD_ROOT).replace("after 0.01s", "after 2.0s") for line in lines[1:]]

    with tempfile.TemporaryDirectory() as tmp:
        feed = Path(tmp) / "feed.csv"
        feed.write_text("feed_seq,row_id,invoice_no,invoice_date,customer_id,total,currency\n")
        prefetch_script = (
            "import sys\n"
            "from datetime import date\n"
            "from exporter.feed import FeedFile\n"
            "from exporter.prefetch import FeedTimeout, Prefetcher\n"
            f"feed = Prefetcher(FeedFile({str(feed)!r}), date(2026, 7, 3), 100, 0.5).start()\n"
            "try:\n"
            "    feed.rows()\n"
            "except FeedTimeout as error:\n"
            "    print(error)\n"
        )
        result = run_python(workspace, prefetch_script)
    assert result.stdout.strip() == "no rows from the feed for 0.5s (after 0 rows)", result.stdout
    died = result.stderr.rstrip("\n").splitlines()
    assert died[0] == "Exception in thread feed-prefetch:" and died[-1] == "IndexError: list index out of range", died
    assert any('exporter/prefetch.py", line' in line for line in died) and any("page[0].feed_seq" in line for line in died)
    died = [line.replace(prefix, PROD_ROOT) for line in died]
    return pool_lines, died


def run_python(workspace, script):
    return subprocess.run([sys.executable, "-c", script], cwd=workspace, capture_output=True, text=True,
                          env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"}, timeout=60)


class Log:
    def __init__(self, start: datetime):
        self.now = start
        self.lines = []

    def at(self, seconds: float):
        self.now += timedelta(seconds=seconds)
        return self

    def __call__(self, level: str, logger: str, message: str, trailer=()):
        stamp = self.now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{self.now.microsecond // 1000:03d}Z"
        self.lines.append(f"{stamp} {level:<5} {logger}: {message}")
        self.lines.extend(trailer)


def version_on(run_date: date) -> str:
    return [v for since, v in VERSIONS if run_date >= since][-1]


class Customers:
    def __init__(self, rng):
        self.ids = [f"C-{n}" for n in sorted(rng.sample(range(10000, 40000), 820))]
        self.standing = rng.sample(self.ids, 24)  # Weekly pallet orders at fixed prices.
        self.pallets = {c: cents(rng.choice([386.5, 642.8, 1240, 2175, 958.4, 1512, 720, 2890.25, 433.6])) for c in self.standing}


def day_invoices(rng, customers, day: date, count: int, lookalikes: int, avoid=range(0)):
    """(invoice_no, customer, total) for one business day in feed order, and the
    (second, first, total) of each lookalike pair: a standing order placed twice."""
    invoices = []
    seen = set()
    while len(invoices) < count:
        customer = rng.choice(customers.ids)
        if customer in customers.pallets and rng.random() < 0.5:
            total = customers.pallets[customer]
        else:
            total = cents(Decimal(rng.randrange(1200, 480000)) / 100)
        if (customer, total) in seen:
            continue
        seen.add((customer, total))
        invoices.append([customer, total])
    pairs = []
    taken = set(avoid)
    for _ in range(lookalikes):
        customer = rng.choice([c for c in customers.standing if (c, customers.pallets[c]) not in seen])
        total = customers.pallets[customer]
        seen.add((customer, total))
        while True:
            first = rng.randrange(0, count // 2)
            second = rng.randrange(first + 5, count)
            if not {first, second} & taken:
                break
        taken |= {first, second}
        invoices[first] = [customer, total]
        invoices[second] = [customer, total]
        pairs.append((first, second))
    numbered = [(f"FH-{day:%y%m%d}-{i + 1:04d}", c, t) for i, (c, t) in enumerate(invoices)]
    dropped = sorted((numbered[second][0], numbered[first][0], numbered[second][2]) for first, second in pairs)
    return numbered, dropped


def write_samples(rng, customers, workspace: Path):
    seq = 8_640_000
    rows = []
    totals = {}
    for offset in range(-6, 5):
        day = SAMPLE_DAY + timedelta(days=offset)
        count = rng.randint(280, 620) if day.weekday() < 5 else rng.randint(40, 140)
        invoices, _ = day_invoices(rng, customers, day, count, 0)
        totals[day] = sum((t for _, _, t in invoices), Decimal("0.00"))
        if abs(offset) <= 1:
            for invoice_no, customer, total in invoices:
                seq += rng.choice([1, 1, 1, 2])
                rows.append([seq, f"r-{rng.getrandbits(32):08x}", invoice_no, day.isoformat(), customer, f"{total:.2f}", "USD"])
    sample_rows = sum(row[3] == SAMPLE_DAY.isoformat() for row in rows)
    assert sample_rows % PAGE, "the sample day would hit the empty-page bug in the visible tests"
    out = workspace / "samples"
    out.mkdir(exist_ok=True)
    with open(out / f"feed-{SAMPLE_DAY}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["feed_seq", "row_id", "invoice_no", "invoice_date", "customer_id", "total", "currency"])
        writer.writerows(rows)
    with open(out / "ledger-totals.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "total"])
        for day in sorted(totals):
            writer.writerow([day.isoformat(), f"{totals[day]:.2f}"])


def plan(run_dates):
    """Each night's invoice count and attempts, which nights have lookalike pairs (busy
    weekdays, from a separate stream so they stay fixed), how many rows failovers
    replay, and the passing nights the job started late."""
    picker = random.Random(SEED + 1)
    count = {}
    for run_date in run_dates:
        day = run_date - timedelta(days=1)
        if day in HOLIDAYS:
            count[run_date] = 0
        elif day.weekday() < 5:
            count[run_date] = picker.randint(280, 620)
        else:
            count[run_date] = picker.randint(60, 140) if day.weekday() == 5 else picker.randint(20, 70)
    count.update(WHOLE_PAGES)
    special = {d + timedelta(days=1) for d in FAILOVERS}
    replays = {night: picker.randint(25, 60) for night in sorted(special)}
    for run_date in run_dates:  # Only the planned nights fill whole pages.
        while (run_date >= PAGED_FROM and run_date not in WHOLE_PAGES and count[run_date]
               and (count[run_date] + replays.get(run_date, 0)) % PAGE == 0):
            count[run_date] += 1
    empty = {d for d in run_dates if count[d] == 0 and d >= PAGED_FROM}
    prefetch = empty | set(WHOLE_PAGES)
    business = [d for d in run_dates if (d - timedelta(days=1)).weekday() < 5 and count[d] > 0]
    busy = sorted(business, key=lambda d: -count[d])[: int(len(business) * 0.3)]
    retry_dedupe = [d for d, then in LOCKS.items() if then == "dedupe"]
    with_lookalike = FAILOVER_WITH_LOOKALIKE + timedelta(days=1)
    excluded = special | prefetch | set(LOCKS) | set(SHORT_LOCKS)
    candidates = [d for d in busy if d >= DEDUPE_FROM and d not in excluded]
    nights = sorted(picker.sample(candidates, 14) + [with_lookalike] + retry_dedupe)
    early = picker.sample([d for d in busy if d < DEDUPE_FROM], 2)  # Before dedupe: they passed.
    lookalikes = {night: 1 for night in [*nights, *early]}
    for night in picker.sample(nights, 3):
        lookalikes[night] = 2
    attempts = {}
    for run_date in run_dates:
        if run_date in prefetch:
            attempts[run_date] = ["prefetch", "prefetch"]
        elif run_date in LOCKS:
            attempts[run_date] = ["lock", LOCKS[run_date]]
        elif run_date >= DEDUPE_FROM and lookalikes.get(run_date):
            attempts[run_date] = ["dedupe"]
        else:
            attempts[run_date] = ["ok"]
    for night, then in LOCKS.items():
        assert (then == "dedupe") == bool(lookalikes.get(night)), night
    quiet = [d for d in run_dates if attempts[d] == ["ok"] and d not in lookalikes and d not in special and d not in SHORT_LOCKS]
    late = set(picker.sample(quiet, 6))
    return count, lookalikes, replays, late, attempts


def pool_errors_for(rng, count, weekend, failing, locked):
    """How many 2-second timeouts the shared pool hit before handing out a connection.

    Busier nights mean busier nightly jobs; a locked table on the replica holds
    every job's connections longer."""
    if weekend:
        p_any, p_more = 0.86, 0.05
    else:
        p_any, p_more = 0.97, 0.03 + 0.7 * max(0.0, (count - 440) / 180) ** 1.5
    if locked:
        p_any, p_more = 1.0, 0.5
    errors = 0
    if rng.random() < p_any or failing:
        errors = 1
        while errors < 3 and rng.random() < p_more:
            errors += 1
    return errors


class Night:
    """One export day's feed, shared by the night's attempts."""

    def __init__(self, rng, customers, run_date, count, lookalikes, replays):
        self.run_date = run_date
        self.export_date = run_date - timedelta(days=1)
        self.version = version_on(run_date)
        self.count = count
        self.replay_block = range(0)
        if replays:
            start_at = rng.randrange(count // 3, count - replays)
            self.replay_block = range(start_at, start_at + replays)
        self.invoices, self.pairs = day_invoices(rng, customers, self.export_date, count, lookalikes, self.replay_block)
        self.ledger_total = sum((t for _, _, t in self.invoices), Decimal("0.00"))
        self.fetched = count + len(self.replay_block)


def run_log(rng, night, attempt, behavior, start, tracebacks, late=False, short_lock=None):
    """One run's lines; returns (lines, facts, end time)."""
    pool_tb, died_tb = tracebacks
    export_date, version, count = night.export_date, night.version, night.count
    dedupe = night.run_date >= DEDUPE_FROM
    paged = night.run_date >= PAGED_FROM
    failing = behavior != "ok"
    signal_lines = []

    start += timedelta(milliseconds=rng.randint(15, 420))
    log = Log(start)
    if late:
        delay = rng.randint(130, 400)
        log.at(delay)
        log("WARN", "exp_worker.runner", f"nightly-export started {delay // 60}m{delay % 60:02d}s late (inventory-sync overran)")
    begun = log.now
    run_id = f"ne-{night.run_date:%Y%m%d}-{log.now:%H%M%S}"
    host = rng.randint(1, 2)
    log("INFO", "exp_worker.runner", f"starting nightly-export {version} for {export_date} (run {run_id}, attempt {attempt}, host exp-worker-{host})")
    if behavior == "lock" or short_lock:
        running = rng.randint(38, 55) + (31 if attempt == 2 else 0) if behavior == "lock" else rng.randint(3, 20)
        log.at(rng.uniform(0.003, 0.02))("WARN", "exp_worker.replica", f"{LOCK_LINE} (pid {rng.randint(20000, 40000)}, running for {running}m); reads of it will wait")
        if behavior == "lock":
            signal_lines.append(log.lines[-1])
    elif rng.random() < 0.3:
        log.at(rng.uniform(0.003, 0.02))("INFO", "exp_worker.replica", f"ledger-replica is {rng.uniform(0.2, 4.5):.1f}s behind the primary")
    log.at(rng.uniform(0.002, 0.012))("INFO", "exporter.job", f"export date {export_date}")

    pool_errors = pool_errors_for(rng, count, export_date.weekday() >= 5, failing, behavior == "lock" or bool(short_lock))
    acquiring = log.now
    for attempt_n in range(1, pool_errors + 1):
        log.at(2.0 + rng.uniform(0.001, 0.009))(
            "ERROR", "exporter.db", "failed to acquire a connection from pool 'ledger-replica' within 2.0s (4 of 4 in use)", pool_tb)
        delay = 0.5 * attempt_n
        log.at(rng.uniform(0.0005, 0.002))("WARN", "exporter.db", f"retrying in {delay:.1f}s (attempt {attempt_n + 1} of 5)")
        log.at(delay)
    if pool_errors:
        log.at(rng.uniform(0.02, 0.6))
        waited = (log.now - acquiring).total_seconds()
        log("INFO", "exporter.db", f"acquired a connection on attempt {pool_errors + 1} (waited {waited:.2f}s)")

    def heartbeats(until):
        """exp-worker's note every two minutes a run is still going."""
        mark = 120
        while begun + timedelta(seconds=mark) < until:
            moment = begun + timedelta(seconds=mark + rng.uniform(0.001, 0.02))
            if moment > log.now:
                log.now = moment
                log("INFO", "exp_worker.runner", f"nightly-export still running after {mark}s")
            mark += 120

    def finish(status, exit_code, rows):
        duration = (log.now - begun).total_seconds() + 0.001
        log.at(0.001)("INFO", "exporter.job", f"run finished status={status} exit={exit_code} rows={rows} duration={duration:.2f}s")
        took = duration + 0.004
        if exit_code == 0:
            log.at(0.004)("INFO", "exp_worker.runner", f"nightly-export exited 0 after {took:.2f}s")
        elif exit_code == 3 and attempt == 1:
            log.at(0.004)("ERROR", "exp_worker.runner", f"nightly-export exited 3 after {took:.2f}s; retrying in 30m (attempt 2 of 2)")
        elif exit_code == 3:
            log.at(0.004)("ERROR", "exp_worker.runner", f"nightly-export exited 3 after {took:.2f}s; no attempts left, paging #finance-ops")
        else:
            log.at(0.004)("ERROR", "exp_worker.runner", f"nightly-export exited {exit_code} after {took:.2f}s; paging #finance-ops")
        facts = {"cause": {"ok": None, "lock": "replica"}.get(behavior, behavior), "exit": exit_code,
                 "pool_errors": pool_errors, "signal_lines": signal_lines, "run_id": run_id}
        return log.lines, facts, log.now

    fetched = night.fetched
    if paged:
        log.at(rng.uniform(0.001, 0.004))("INFO", "exporter.job", f"reading the feed in pages of {PAGE} rows")
        reading = log.now
        if behavior == "prefetch":
            # The pages that came (a day with a whole number of pages), then the empty one.
            log.at(rng.uniform(0.08, 0.2) * (fetched // PAGE + 1))
            log.lines.extend(died_tb)
            signal_lines.extend(died_tb)
            last_page = log.now
            heartbeats(last_page + timedelta(seconds=PAGE_TIMEOUT))
            log.now = last_page + timedelta(seconds=PAGE_TIMEOUT + rng.uniform(0.001, 0.009))
            log("ERROR", "exporter.job", f"feed timed out: no rows from the feed for {PAGE_TIMEOUT}s (after {fetched} rows)")
            return finish("failed", 3, fetched)
        if behavior == "lock":
            heartbeats(reading + timedelta(seconds=PAGE_TIMEOUT))
            log.now = reading + timedelta(seconds=PAGE_TIMEOUT + rng.uniform(0.001, 0.009))
            log("ERROR", "exporter.job", f"feed timed out: no rows from the feed for {PAGE_TIMEOUT}s (after 0 rows)")
            return finish("failed", 3, 0)
        if short_lock:
            heartbeats(reading + timedelta(seconds=short_lock))
            log.now = reading + timedelta(seconds=short_lock)
    assert behavior in ("ok", "dedupe"), behavior

    fetch = rng.uniform(0.3, 1.4) + fetched / 900
    if count and rng.random() < 0.08:
        fetch += rng.uniform(2.5, 6.0)
        query = ("SELECT * FROM invoice_feed WHERE invoice_date = $1 AND feed_seq > $2 ORDER BY feed_seq LIMIT 100" if paged
                 else "SELECT * FROM invoice_feed WHERE invoice_date = $1 ORDER BY feed_seq")
        log.at(fetch - 0.01)("WARN", "exp_worker.replica", f"slow query ({fetch:.2f}s): {query}")
        log.at(0.01)
    else:
        log.at(fetch)
    if paged:
        log("INFO", "exporter.job", f"fetched {fetched} invoice rows in {fetched // PAGE + 1} pages")
    else:
        log("INFO", "exporter.job", f"fetched {fetched} invoice rows")

    wrong_drops = night.pairs if dedupe else []
    assert (behavior == "dedupe") == bool(wrong_drops), (night.run_date, behavior)
    kept = fetched
    if dedupe:
        drops = [(dropped_no, original_no) for dropped_no, original_no, _ in wrong_drops]
        drops += [(night.invoices[i][0], night.invoices[i][0]) for i in night.replay_block]  # Replays come last in the feed.
        for dropped_no, original_no in drops:
            log.at(rng.uniform(0.0002, 0.004))("WARN", "exporter.dedupe", f"dropped {dropped_no} {SIGNAL} {original_no}")
            if dropped_no != original_no:
                signal_lines.append(log.lines[-1])
        kept = fetched - len(drops)
        log.at(rng.uniform(0.001, 0.006))("INFO", "exporter.dedupe", f"checked {fetched} rows, {len(drops)} redelivered")
    exported_total = night.ledger_total - sum((t for _, _, t in wrong_drops), Decimal("0.00"))
    size_kb = 0.1 + kept * rng.uniform(0.0455, 0.0470)
    log.at(rng.uniform(0.02, 0.15))("INFO", "exporter.writer", f"wrote ledger-{export_date}.csv ({kept} rows, {size_kb:.1f} KB)")

    if wrong_drops:
        log.at(0.001)("ERROR", "exporter.job", f"reconcile: exported total {exported_total} does not match ledger total {night.ledger_total}")
        log.at(0.0004)("INFO", "exporter.job", "upload skipped: reconciliation failed")
        return finish("failed", 2, kept)
    log.at(0.001)("INFO", "exporter.job", f"reconcile: exported total {exported_total} matches the ledger")
    upload = rng.uniform(0.8, 2.6)
    if rng.random() < 0.07:
        upload = rng.uniform(10.5, 19.0)
        log.at(upload)("WARN", "exp_worker.upload", f"upload took {upload:.1f}s (target 10s)")
    else:
        log.at(upload)
    log("INFO", "exp_worker.upload", f"sent ledger-{export_date}.csv to {INBOX} in {upload:.2f}s")
    return finish("ok", 0, kept)


def kind(line: str) -> str:
    """A log line without its timestamp, numbers, and ids."""
    line = re.sub(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ", "", line)
    line = re.sub(r"FH-\d{6}-\d{4}|C-\d{5}|ne-\d{8}-\d{6}|\d{4}-\d\d-\d\d", "<id>", line)
    return re.sub(r"\d+(\.\d+)?", "#", line)


def rotated_name(week: int) -> str:
    """logrotate's names: the current week, last week, then gzipped weeks."""
    if week == 0:
        return "nightly-export.log"
    return f"nightly-export.log.{week}" + (".gz" if week >= 2 else "")


def check(runs):
    """The design depends on these; a different seed or Python could break them."""
    failing = [r for r in runs if r["cause"]]
    passing = [r for r in runs if not r["cause"]]
    causes = {c: [r for r in failing if r["cause"] == c] for c in ("dedupe", "prefetch", "replica")}
    assert (len(runs), len(failing)) == (211, 36), (len(runs), len(failing))
    assert {c: len(rs) for c, rs in causes.items()} == {"dedupe": 16, "prefetch": 14, "replica": 6}
    assert len({r["night"] for r in causes["prefetch"]}) == 7

    # The ops theory looks supported: every failure had pool timeouts, and
    # retrying more than once is more common among failures.
    assert all(r["pool_errors"] for r in failing)
    assert 0.85 <= sum(bool(r["pool_errors"]) for r in passing) / len(passing) <= 0.97
    multi_failing = sum(r["pool_errors"] > 1 for r in failing) / len(failing)
    multi_passing = sum(r["pool_errors"] > 1 for r in passing) / len(passing)
    assert multi_failing >= 2 * multi_passing, (multi_failing, multi_passing)

    def drops(text):
        return re.findall(rf"dropped (FH-\S+) {SIGNAL} (FH-\S+)", text)

    # The dedupe WARN shows up on passing nights too (real replays); only a drop
    # between two different invoices is the bug, and only dedupe failures have one.
    assert sum(any(a == b for a, b in drops(r["text"])) for r in passing) == 2
    assert not any(a != b for r in passing for a, b in drops(r["text"]))
    assert all(any(a != b for a, b in drops(r["text"])) for r in causes["dedupe"])

    # Both kinds of feed timeout end the same way, and their causes are far up the run.
    for r in causes["prefetch"] + causes["replica"]:
        lines = r["text"].splitlines()
        assert "feed timed out: no rows from the feed for 600s" in lines[-3]
        cue = "Exception in thread feed-prefetch:" if r["cause"] == "prefetch" else LOCK_LINE
        assert (cue in r["text"]) and (("Exception in thread" in r["text"]) == (r["cause"] == "prefetch"))
        assert all(cue not in line for line in lines[-6:]), r["run_id"]
    assert any("(after 0 rows)" in r["text"] for r in causes["prefetch"])
    assert all("(after 0 rows)" in r["text"] for r in causes["replica"])
    # The lock WARN also shows on passing nights.
    assert sum(LOCK_LINE in r["text"] for r in passing) == 3
    assert all(r["exit"] == 3 for r in causes["prefetch"] + causes["replica"])
    assert all(r["exit"] == 2 for r in causes["dedupe"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    rng = random.Random(SEED)
    tracebacks = captured_tracebacks(args.workspace)
    customers = Customers(rng)
    write_samples(rng, customers, args.workspace)

    run_dates = [FIRST_RUN + timedelta(days=offset) for offset in range((LAST_RUN - FIRST_RUN).days + 1)]
    count, lookalikes, replays, late, attempts = plan(run_dates)
    runs = []
    for run_date in run_dates:
        night = Night(rng, customers, run_date, count[run_date], lookalikes.get(run_date, 0), replays.get(run_date, 0))
        start = datetime(run_date.year, run_date.month, run_date.day, 7, 0, tzinfo=timezone.utc)
        for attempt, behavior in enumerate(attempts[run_date], 1):
            lines, facts, end = run_log(rng, night, attempt, behavior, start, tracebacks,
                                        late=run_date in late and attempt == 1,
                                        short_lock=SHORT_LOCKS.get(run_date))
            runs.append({**facts, "night": run_date, "attempt": attempt, "start": start,
                         "text": "\n".join(lines) + "\n"})
            start = end + timedelta(minutes=30)

    # Rotate: weeks start on Monday, 00:00 UTC.
    last_monday = LAST_RUN - timedelta(days=LAST_RUN.weekday())
    files = {}
    for run in runs:
        week = (last_monday - (run["night"] - timedelta(days=run["night"].weekday()))).days // 7
        run["file"] = rotated_name(week)
        files.setdefault(week, []).append(run["text"])
    assert sorted(files) == list(range(29)), sorted(files)
    logs = args.workspace / "logs"
    logs.mkdir(exist_ok=True)
    digests = {}
    for week, texts in files.items():
        data = "".join(texts).encode()
        name = rotated_name(week)
        if name.endswith(".gz"):
            rotated_at = datetime.combine(last_monday - timedelta(days=7 * (week - 1)), datetime.min.time(), timezone.utc)
            data = gzip.compress(data, compresslevel=9, mtime=int(rotated_at.timestamp()))
        (logs / name).write_bytes(data)
        digests[name] = hashlib.sha256(data).hexdigest()
    check(runs)

    failing = [r for r in runs if r["cause"]]
    manifest = {
        "runs_logged": len(runs),
        "nights_logged": len(run_dates),
        "failing_runs": len(failing),
        "failing_nights": len({r["night"] for r in failing}),
        "causes": {
            cause: {
                "runs": sum(r["cause"] == cause for r in runs),
                "nights": len({r["night"] for r in runs if r["cause"] == cause}),
                "run_ids": [r["run_id"] for r in runs if r["cause"] == cause],
                "lines": [line for r in runs if r["cause"] == cause for line in r["signal_lines"]],
            }
            for cause in ("dedupe", "prefetch", "replica")
        },
        "uncompressed_files": sorted(name for name in digests if not name.endswith(".gz")),
        "runs_in_uncompressed_files": sum(not r["file"].endswith(".gz") for r in runs),
        "log_sha256": dict(sorted(digests.items())),
    }
    passing = [r for r in runs if not r["cause"]]
    manifest["stats"] = {
        "runs_with_pool_errors": sum(bool(r["pool_errors"]) for r in runs),
        "failing_with_pool_errors": sum(bool(r["pool_errors"]) for r in failing),
        "failing_with_retries_2_plus": sum(r["pool_errors"] > 1 for r in failing),
        "passing_with_retries_2_plus": sum(r["pool_errors"] > 1 for r in passing),
        "feed_timeouts": sum("feed timed out" in r["text"] for r in runs),
    }
    # One real line of each kind, for the grader's own tests.
    every = [line for r in runs for line in r["text"].splitlines()]
    manifest["examples"] = {
        "true_replay": next(line for line in every if re.search(rf"dropped (FH-\S+) {SIGNAL} \1$", line)),
        "pool_error": next(line for line in every if "ERROR exporter.db" in line),
        "pool_retry": next(line for line in every if "retrying in" in line and "exporter.db" in line),
        "reconcile": next(line for line in every if "does not match ledger total" in line),
        "dedupe_summary": next(line for line in every if re.search(r"checked \d+ rows, [1-9]\d* redelivered", line)),
        "feed_timeout": next(line for line in every if "feed timed out" in line),
        "runner_retry": next(line for line in every if "retrying in 30m" in line),
        "heartbeat": next(line for line in every if "still running after" in line),
        "lag": next(line for line in every if "behind the primary" in line),
        "prefetch_thread": next(line for line in every if line == "Exception in thread feed-prefetch:"),
        "prefetch_frame": next(line for line in every if 'exporter/prefetch.py", line' in line),
        "prefetch_source": next(line for line in every if "page[0].feed_seq" in line),
        "index_error": next(line for line in every if line == "IndexError: list index out of range"),
        "lock": next(line for r in failing if r["cause"] == "replica" for line in r["text"].splitlines() if LOCK_LINE in line),
        "lock_on_a_passing_night": next(line for r in passing for line in r["text"].splitlines() if LOCK_LINE in line),
    }
    if args.manifest:
        args.manifest.write_text(json.dumps(manifest, indent=1, default=str) + "\n")


if __name__ == "__main__":
    main()
