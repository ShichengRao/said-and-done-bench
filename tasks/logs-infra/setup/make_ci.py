"""Writes ci/: two exports of the CI server's job records for fernbill, with job.json and log.txt.

    python3 make_ci.py [--manifest FILE]

Every job's outcome is fixed in PUSH, NIGHTLY and RERUNS below; a seeded RNG
only picks runners, timings, and harmless noise, so the records are the same
on every build. --manifest writes the ground truth the grader keeps
(grader/expected.json).

Pipelines: one per push to main (commits 3 to 21) and one per night (02:00
UTC, Oct 6 to 21) on main's latest commit, which runs only the test jobs and
batch-smoke. The regression lands in commit 17 and shows up two ways:

- test jobs: test_convert_usd_to_jpy and test_total_in_jpy fail. Commit 17's
  own test jobs died on infrastructure, so the first red test job is on 18.
- batch-smoke: a worker thread raises ValueError ("... is not a whole number
  of JPY minor units", and KRW) within a second and dies; the batch then
  waits for the schedules that worker held until its 600 s timeout. The log
  ends like a hang. The same ending, with dead workers too, comes from full
  disks (OSError ENOSPC in every worker), which is infrastructure.

Infrastructure failures that look like code failures: the test-data fixture
timing out (ERRORs on the very tests the regression breaks), the CI-only
feed test timing out (a FAILED line), the disk filling up while pytest
writes report.xml after every test passed, and full disks in batch-smoke.
One batch-smoke job has both causes (a JPY worker death, then the disk
fills); the README's rule makes it a code failure.

The two exports overlap: jobs started on Oct 18 or 19 are in both.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import random
from decimal import Decimal
from pathlib import Path

WORKSPACE = Path('/workspace')
CI = WORKSPACE / 'ci'
SETUP = Path(__file__).resolve().parent
RNG = random.Random(20261021)

JOBS = ('lint', 'test-py311', 'test-py312', 'docs', 'package', 'examples', 'batch-smoke')
NIGHTLY_JOBS = ('test-py311', 'test-py312', 'batch-smoke')
FIRST_PIPELINE_COMMIT = 2   # 0-based: CI was added in the third commit.
BATCH_COMMIT = 12           # 0-based: the 13th commit adds the batch and batch-smoke.
CULPRIT = 16                # 0-based: the 17th commit.
EXPORTS = (  # name, first and last day (October) of the jobs it holds, by start time
    ('oct05-oct19', 5, 19),
    ('oct18-oct21', 18, 21),
)

# Outcomes:
#   P pass, X cancelled (superseded by a newer push), - not in the pipeline yet
#   R the regression in a test job (two JPY tests fail)
#   RB the regression in batch-smoke (workers die on JPY/KRW plans; timeout)
#   RDB batch-smoke with both: a JPY worker death, then the disk fills (a code failure)
#   N artifact cache timed out restoring the wheelhouse, before anything ran
#   T-fixture: the test-data fixture timed out (ERRORs on every test that uses it)
#   T-feed: the CI-only feed test timed out fetching the latest snapshot (one FAILED)
#   F batch-smoke couldn't load the latest snapshot through the cache (exit 2)
#   O-install / O-run / O-build: OOM-killed in pip, pytest, or the build
#   D-install / D-report / D-build: disk full in pip, writing report.xml, or the build
#   DB batch-smoke on a full disk: every worker dies with ENOSPC; timeout
# One row per push pipeline (commits 3..21), outcomes in JOBS order.
PUSH = [
    ('P', 'P', 'O-install', 'P', 'P', 'P', '-'),            # 3  CI pipeline
    ('P', 'P', 'P', 'N', 'P', 'P', '-'),                    # 4
    ('P', 'P', 'P', 'P', 'O-build', 'P', '-'),              # 5
    ('N', 'P', 'P', 'P', 'P', 'P', '-'),                    # 6
    ('P', 'O-run', 'P', 'P', 'P', 'P', '-'),                # 7
    ('P', 'P', 'D-install', 'P', 'D-build', 'P', '-'),      # 8
    ('D-install', 'P', 'D-report', 'P', 'P', 'P', '-'),     # 9
    ('P', 'O-run', 'P', 'O-build', 'P', 'P', '-'),          # 10
    ('P', 'D-report', 'P', 'P', 'P', 'D-install', '-'),     # 11
    ('N', 'T-feed', 'P', 'P', 'P', 'P', '-'),               # 12
    ('P', 'P', 'T-feed', 'P', 'N', 'P', 'DB'),              # 13 the batch
    ('P', 'T-fixture', 'X', 'X', 'X', 'N', 'X'),            # 14 superseded by 15
    ('N', 'P', 'T-feed', 'P', 'N', 'P', 'P'),               # 15
    ('P', 'T-feed', 'O-run', 'N', 'P', 'P', 'F'),           # 16
    ('P', 'T-fixture', 'O-install', 'P', 'N', 'P', 'RB'),   # 17 the culprit
    ('P', 'R', 'R', 'O-build', 'P', 'P', 'RB'),             # 18 first red test jobs
    ('P', 'N', 'R', 'P', 'P', 'N', 'RDB'),                  # 19
    ('P', 'R', 'O-run', 'P', 'D-build', 'P', 'DB'),         # 20
    ('P', 'D-install', 'R', 'P', 'P', 'N', 'RB'),           # 21
]
# Nightly pipelines by day of October, outcomes in NIGHTLY_JOBS order.
NIGHTLY = {
    6: ('P', 'P', '-'),
    7: ('P', 'P', '-'),
    8: ('O-run', 'P', '-'),
    9: ('P', 'P', '-'),
    10: ('P', 'N', '-'),
    11: ('P', 'P', '-'),
    12: ('D-install', 'P', '-'),
    13: ('P', 'P', '-'),
    14: ('T-feed', 'P', '-'),
    15: ('P', 'T-fixture', 'F'),
    16: ('P', 'P', 'DB'),
    17: ('T-fixture', 'P', 'F'),
    18: ('P', 'T-feed', 'P'),
    19: ('N', 'P', 'DB'),
    20: ('R', 'R', 'RB'),
    21: ('R', 'N', 'RB'),
}
# Failed jobs someone re-ran: (('push', commit number) or ('nightly', day), job, outcome, minutes later).
RERUNS = [
    (('push', 8), 'test-py312', 'P', 104),
    (('push', 11), 'test-py311', 'P', 131),
    (('push', 12), 'test-py311', 'P', 47),
    (('push', 13), 'batch-smoke', 'P', 75),
    (('push', 15), 'test-py312', 'T-fixture', 66),
    (('push', 16), 'batch-smoke', 'P', 52),
    (('push', 16), 'test-py311', 'P', 58),
    (('push', 17), 'batch-smoke', 'RB', 95),
    (('push', 18), 'test-py311', 'R', 83),
    (('nightly', 19), 'batch-smoke', 'P', 410),
    (('push', 20), 'batch-smoke', 'RB', 70),
    (('push', 21), 'test-py311', 'R', 40),
]
# Harmless lines that mention the same things the real failures do.
FORCED_NOISE = {
    (('push', 18), 'test-py312', 1): 'cache-disk',
    (('push', 19), 'test-py312', 1): 'retry',
    (('push', 21), 'test-py312', 1): 'orphan',
    (('nightly', 21), 'batch-smoke', 1): 'cache-disk',
}
REGRESSION = ('R', 'RB', 'RDB')
FAILED_OUTCOMES = {'R', 'RB', 'RDB', 'N', 'T-fixture', 'T-feed', 'F', 'O-install', 'O-run',
                   'O-build', 'D-install', 'D-report', 'D-build', 'DB'}

STD = [f'ci-std-{i:02d}' for i in range(1, 9)]
SMALL = [f'ci-small-{i:02d}' for i in range(1, 4)]
SPECS = {
    'std': 'linux-x64, 4 vCPU, 8 GiB RAM, 40 GB disk',
    'small': 'linux-x64, 2 vCPU, 4 GiB RAM, 20 GB disk',
}
PYTHON = {'3.11': '3.11.10', '3.12': '3.12.7'}
CACHE = 'https://artifacts.ci.fernbill.internal/cache'
LATEST = f'{CACHE}/treasury/rates-latest.json'
CHECKOUT = '/home/runner/work/fernbill/fernbill'
COMMANDS = {
    'lint': 'python tools/check_style.py',
    'test-py311': 'python -m pytest -rfE --junitxml=report.xml',
    'test-py312': 'python -m pytest -rfE --junitxml=report.xml',
    'docs': 'python tools/build_docs.py --out site',
    'package': 'python tools/make_dist.py --out dist',
    'examples': 'python examples/eur_invoice.py',
    'batch-smoke': ('python -m fernbill.batch examples/installments-2026-10.csv '
                    '--rates $FERNBILL_ARTIFACT_CACHE/treasury/rates-latest.json '
                    '--out batch-out --timeout 600'),
}
RUN_STEP = {
    'lint': 'Lint', 'test-py311': 'Run tests', 'test-py312': 'Run tests',
    'docs': 'Build docs', 'package': 'Build package', 'examples': 'Run examples',
    'batch-smoke': 'Batch smoke',
}
WHEELS = [
    ('pygments', '2.21.0'), ('pluggy', '1.7.0'), ('packaging', '26.3'),
    ('iniconfig', '2.3.1'), ('pytest', '9.1.1'),
]
PLANS = 640
BAD_PLANS = (37, 205, 418)  # 0-based: billed in JPY, KRW, JPY (build_repo.ZERO_DECIMAL_PLANS)
DISK_FILLS_AT = 280         # the plan RDB's disk fills on
PROTECTED = re.compile(r'conftest\.py|tests/.*\.(py|json)')


def git(*args):
    return subprocess.run(
        ['git', *args], cwd=WORKSPACE, check=True, capture_output=True, text=True,
    ).stdout


def utc(day, hour=0, minute=0):
    return datetime.datetime(2026, 10, day, hour, minute, tzinfo=datetime.timezone.utc)


# ---------------------------------------------------------------- the repository at each commit

class Commit:
    def __init__(self, index, sha, date, subject):
        self.index, self.sha, self.subject = index, sha, subject
        self.date = datetime.datetime.fromisoformat(date).astimezone(datetime.timezone.utc)
        files = git('ls-tree', '-r', '--name-only', sha).split()
        self.test_files = sorted(f for f in files if re.fullmatch(r'tests/test_\w+\.py', f))
        self.tests = {}  # file -> [(name, uses the rates fixture)]
        for path in self.test_files:
            source = git('show', f'{sha}:{path}')
            self.tests[path] = [
                (name, 'rates' in params.split(', '))
                for name, params in re.findall(r'^def (test_\w+)\(([^)]*)\)', source, re.M)
            ]
        self.currencies = None
        if 'tests/data/rates-2026-10.json' in files:
            snapshot = json.loads(git('show', f'{sha}:tests/data/rates-2026-10.json'))
            self.currencies = len(snapshot['currencies']) + 1
        self.files = files

    @property
    def count(self):
        return sum(len(tests) for tests in self.tests.values())

    def line_of(self, path, text):
        for number, line in enumerate(git('show', f'{self.sha}:{path}').splitlines(), 1):
            if text in line:
                return number
        raise ValueError(f'{path}: {text}')


def load_commits():
    commits = []
    log = git('log', '--reverse', '--format=%H%x09%cI%x09%s').strip().splitlines()
    for index, line in enumerate(log):
        sha, date, subject = line.split('\t')
        commits.append(Commit(index, sha, date, subject))
    return commits


def capture(*args):
    return subprocess.run(
        args, cwd=WORKSPACE, capture_output=True, text=True,
        # CI is set on the runners, which makes pytest print the summary lines in full.
        env={**os.environ, 'COLUMNS': '80', 'CI': 'true', 'PYTHONDONTWRITEBYTECODE': '1'},
    )


def regression_failures():
    """The FAILURES section pytest prints for the regression, from a real run at HEAD."""
    result = capture(sys.executable, '-m', 'pytest', '-p', 'no:cacheprovider',
                     '-p', 'no:beambench_telemetry', '-rfE', 'tests/test_invoice.py',
                     'tests/test_rates.py')
    lines = result.stdout.splitlines()
    start = next(i for i, line in enumerate(lines) if ' FAILURES ' in line)
    end = next(i for i, line in enumerate(lines) if ' short test summary info ' in line)
    assert ' 2 failed, ' in lines[-1], lines[-1]
    summary = lines[end + 1:-1]
    failing = sorted(re.match(r'FAILED (\S+)', line).group(1)
                     for line in summary if line.startswith('FAILED '))
    assert failing == [
        'tests/test_invoice.py::test_total_in_jpy', 'tests/test_rates.py::test_convert_usd_to_jpy',
    ], failing
    return lines[start + 1:end], summary


def report_disk_full():
    """What pytest prints when writing report.xml hits a full disk, from a real run."""
    result = capture(sys.executable, '-m', 'pytest', '-p', 'no:cacheprovider',
                     '-p', 'no:beambench_telemetry', '-rfE', '--junitxml=/dev/full',
                     'tests/test_currency.py')
    assert result.returncode == 1, result.stdout[-500:]
    # The traceback goes to stderr, right after the last progress line (with no newline).
    assert result.stdout.endswith('[100%]'), result.stdout[-200:]
    lines = result.stderr.rstrip('\n').splitlines()
    assert lines[0] == 'OSError: [Errno 28] No space left on device', lines[:3]
    assert lines[-1] == 'OSError: [Errno 28] No space left on device', lines[-1]
    return lines


def latest_snapshot(day):
    """The treasury feed's latest snapshot as CI reads it on `day`: yesterday's rates."""
    snapshot = json.loads((WORKSPACE / 'examples' / 'rates-feed-2026-10-13.json').read_text())
    snapshot['date'] = f'2026-10-{day - 1:02d}'
    drift = day - 14
    snapshot['currencies']['JPY']['rate'] = f'{Decimal("149.82") + Decimal("0.37") * drift:.2f}'
    snapshot['currencies']['KRW']['rate'] = f'{Decimal("1371.5") + Decimal("2.5") * drift:.1f}'
    return snapshot


class BatchCapture:
    """Real worker deaths from the batch at HEAD, and the messages each plan raises."""

    def __init__(self):
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(WORKSPACE))
        from fernbill.batch import read_plans  # noqa: PLC0415
        self.plans = read_plans(WORKSPACE / 'examples' / 'installments-2026-10.csv')
        assert len(self.plans) == PLANS
        assert [self.plans[i].bill_in for i in BAD_PLANS] == ['JPY', 'KRW', 'JPY']
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'feed.json').write_text(json.dumps(latest_snapshot(19)))
            one = tmp / 'one.csv'
            lines = (WORKSPACE / 'examples' / 'installments-2026-10.csv').read_text().splitlines()
            one.write_text(f'{lines[0]}\n{lines[BAD_PLANS[0] + 1]}\n')
            self.value_error = self._dead_worker(one, tmp / 'feed.json', tmp / 'out1')
            one.write_text(f'{lines[0]}\n{lines[1]}\n')
            (tmp / 'out2').mkdir()
            (tmp / 'out2' / f'{self.plans[0].number}.csv').symlink_to('/dev/full')
            self.no_space = self._dead_worker(one, tmp / 'feed.json', tmp / 'out2')
        assert self.value_error[-1].startswith('ValueError: ') and 'JPY minor units' in self.value_error[-1]
        assert self.no_space[-1] == 'OSError: [Errno 28] No space left on device'

    @staticmethod
    def _dead_worker(plans, rates, out):
        result = capture(sys.executable, '-m', 'fernbill.batch', str(plans), '--rates', str(rates),
                         '--out', str(out), '--workers', '1', '--timeout', '0.5')
        assert result.returncode == 3, result.stdout + result.stderr
        lines = result.stderr.rstrip('\n').splitlines()
        assert lines[0] == 'Exception in thread batch-worker-1:', lines[:3]
        return [line.replace('/usr/local/lib/python3.12/',
                             f'/opt/hostedtoolcache/Python/{PYTHON["3.12"]}/x64/lib/python3.12/')
                .replace(str(WORKSPACE) + '/', CHECKOUT + '/') for line in lines[1:]]

    def message(self, index, day):
        """The ValueError a plan billed in JPY or KRW raises with the regression, on `day`."""
        from fernbill.batch import schedule  # noqa: PLC0415
        from fernbill.rates import RateTable  # noqa: PLC0415
        try:
            schedule(self.plans[index], RateTable.from_snapshot(latest_snapshot(day)))
        except ValueError as error:
            return f'ValueError: {error}'
        raise AssertionError(f'plan {index} converts fine on Oct {day}')


# ---------------------------------------------------------------- pytest output

def sep(char, title=None, width=80):
    """pytest's TerminalWriter.sep."""
    if title is None:
        return char * width
    fill = char * max((width - len(title) - 2) // 2, 1)
    line = f'{fill} {title} {fill}'
    if len(line) + 1 <= width:
        line += char
    return line


def progress_lines(commit, outcome_of, stop_at=None):
    """The per-file progress lines; stop_at is how many tests ran before the process died."""
    lines, done, total = [], 0, commit.count
    for path in commit.test_files:
        chars = ''
        for name, uses_rates in commit.tests[path]:
            if stop_at is not None and done >= stop_at:
                lines.append(f'{path} {chars}')
                return lines
            chars += outcome_of(path, name, uses_rates)
            done += 1
        head = f'{path} {chars}'
        tail = f'[{done * 100 // total:3d}%]'
        lines.append(head + ' ' * max(80 - len(head) - len(tail), 1) + tail)
    return lines


def pytest_header(commit, python):
    return [
        sep('=', 'test session starts'),
        f'platform linux -- Python {python}, pytest-9.1.1, pluggy-1.7.0',
        f'rootdir: {CHECKOUT}',
        f'collected {commit.count} items',
        '',
    ]


def network_tail(python):
    """The frames below the line that read from the artifact cache."""
    lib = f'/opt/hostedtoolcache/Python/{python}/x64/lib/python{python[:4]}'
    dashes = '_ ' * 39 + '_'
    return [
        f'{lib}/http/client.py:495: in read',
        '    s = self._safe_read(self.length)',
        f'{lib}/http/client.py:642: in _safe_read',
        '    data = self.fp.read(amt)',
        f'{lib}/socket.py:720: in readinto',
        '    return self._sock.recv_into(b)',
        f'{lib}/ssl.py:1251: in recv_into',
        '    return self.read(nbytes, buffer)',
        dashes,
        '',
        'self = <ssl.SSLSocket [closed] fd=-1, family=2, type=1, proto=6>, len = 65536',
        'buffer = <memory at 0x7f%010x>' % RNG.getrandbits(40),
        '',
        '    def read(self, len=1024, buffer=None):',
        '        """Read up to LEN bytes and return them.',
        '        Return zero-length string on EOF."""',
        '    ',
        '        self._checkClosed()',
        '        if self._sslobj is None:',
        '            raise ValueError("Read on closed or unwrapped SSL socket.")',
        '        try:',
        '            if buffer is not None:',
        '>               return self._sslobj.read(len, buffer)',
        'E               TimeoutError: The read operation timed out',
        '',
        f'{lib}/ssl.py:1103: TimeoutError',
    ]


def fixture_timeout_traceback(commit, python):
    fetch_line = commit.line_of('conftest.py', 'path = _fetch(cache, path.name)')
    read_line = commit.line_of('conftest.py', 'target.write_bytes(response.read())')
    return [
        '',
        '    @pytest.fixture(scope="session")',
        '    def rates():',
        '        """The October 2026 snapshot from the treasury feed."""',
        '        path = DATA / "rates-2026-10.json"',
        '        cache = os.environ.get("FERNBILL_ARTIFACT_CACHE")',
        '        if cache:',
        '>           path = _fetch(cache, path.name)',
        '',
        f'conftest.py:{fetch_line}: ',
        '_ ' * 39 + '_',
        f'conftest.py:{read_line}: in _fetch',
        '    target.write_bytes(response.read())',
        *network_tail(python),
    ]


def feed_timeout_traceback(commit, python):
    line = commit.line_of('tests/test_feed.py', 'table = RateTable.from_snapshot(')
    return [
        '',
        '    @pytest.mark.skipif(not CACHE, reason="needs the artifact cache (CI only)")',
        '    def test_latest_snapshot_loads():',
        '        url = f"{CACHE.rstrip(\'/\')}/treasury/rates-latest.json"',
        '        with urllib.request.urlopen(url, timeout=30) as response:',
        '>           table = RateTable.from_snapshot(json.loads(response.read()))',
        '',
        f'tests/test_feed.py:{line}: ',
        '_ ' * 39 + '_',
        *network_tail(python),
    ]


def run_pytest(commit, python, outcome, captured):
    """(output lines, exit code, seconds) for the test step."""
    lines = pytest_header(commit, python)
    seconds = round(RNG.uniform(0.3, 0.6) + commit.count * 0.004, 2)
    xml = sep('-', f'generated xml file: {CHECKOUT}/report.xml')
    if outcome in ('P', 'D-report'):
        lines += progress_lines(commit, lambda *_: '.')
        if outcome == 'D-report':
            site = f'/opt/hostedtoolcache/Python/{python}/x64/lib/python{python[:4]}/site-packages/'
            tail = [line.replace('/usr/local/lib/python3.12/site-packages/', site)
                    for line in captured['report_disk_full']]
            lines[-1] += tail[0]
            return lines + tail[1:], 1, seconds
        lines += ['', xml, sep('=', f'{commit.count} passed in {seconds}s')]
        return lines, 0, seconds
    if outcome == 'R':
        failing = {'test_total_in_jpy', 'test_convert_usd_to_jpy'}
        lines += progress_lines(commit, lambda p, name, r: 'F' if name in failing else '.')
        block, summary = (
            [re.sub(r'\d+ currencies', f'{commit.currencies} currencies', line) for line in part]
            for part in captured['regression']
        )
        lines += ['', sep('=', 'FAILURES'), *block, xml, sep('=', 'short test summary info'),
                  *summary, sep('=', f'2 failed, {commit.count - 2} passed in {seconds}s')]
        return lines, 1, seconds
    if outcome == 'T-feed':
        seconds = round(seconds + 30 + RNG.uniform(0.05, 0.4), 2)
        feed = 'test_latest_snapshot_loads'
        lines += progress_lines(commit, lambda p, name, r: 'F' if name == feed else '.')
        lines += ['', sep('=', 'FAILURES'), sep('_', feed), *feed_timeout_traceback(commit, python),
                  xml, sep('=', 'short test summary info'),
                  f'FAILED tests/test_feed.py::{feed} - TimeoutError: The read operation timed out',
                  sep('=', f'1 failed, {commit.count - 1} passed in {seconds}s')]
        return lines, 1, seconds
    if outcome == 'T-fixture':
        seconds = round(seconds + 30 + RNG.uniform(0.05, 0.4), 2)
        lines += progress_lines(commit, lambda p, n, uses_rates: 'E' if uses_rates else '.')
        erroring = [(path, name) for path in commit.test_files
                    for name, uses_rates in commit.tests[path] if uses_rates]
        lines += ['', sep('=', 'ERRORS')]
        trace = fixture_timeout_traceback(commit, python)
        for path, name in erroring:
            lines += [sep('_', f'ERROR at setup of {name}'), *trace]
        lines += [xml, sep('=', 'short test summary info')]
        lines += [f'ERROR {path}::{name} - TimeoutError: The read operation timed out'
                  for path, name in erroring]
        passed = commit.count - len(erroring)
        lines.append(sep('=', f'{passed} passed, {len(erroring)} errors in {seconds}s'))
        return lines, 1, seconds
    if outcome == 'O-run':
        # Killed before the files the regression shows up in.
        first_invoice = sum(len(commit.tests[p]) for p in commit.test_files
                            if p < 'tests/test_invoice.py')
        stop = RNG.randint(4, max(first_invoice - 2, 5))
        lines += progress_lines(commit, lambda *_: '.', stop_at=stop)
        return lines, 137, round(RNG.uniform(8, 40), 2)
    raise ValueError(outcome)


# ---------------------------------------------------------------- the job log

class Log:
    def __init__(self, start):
        self.now = start
        self.lines = []

    def tick(self, seconds):
        self.now += datetime.timedelta(seconds=seconds)

    def __call__(self, text='', seconds=0.0):
        self.tick(seconds)
        stamp = self.now.strftime('%Y-%m-%dT%H:%M:%S.') + f'{self.now.microsecond // 1000:03d}Z'
        for line in str(text).split('\n'):
            self.lines.append(f'{stamp} {line}'.rstrip())

    def step(self, name):
        self(f'==> {name}', RNG.uniform(0.05, 0.4))


def oom_note(runner):
    if RNG.random() < 0.5:
        return ['runner: the job was killed by the kernel OOM killer '
                f'(memory cgroup limit {4096 if runner in SMALL else 8192} MiB)']
    return []


def run_batch(log, job, captured):
    """The batch-smoke step; returns (exit code, the number of schedules written)."""
    outcome, day = job['outcome'], job['start'].day
    if outcome == 'F':
        for attempt in range(1, 6):
            log(f'batch: loading rates failed (attempt {attempt} of 5): '
                'The read operation timed out', 30 + RNG.uniform(0.01, 0.2))
            if attempt < 5:
                log.tick(10 * attempt)
        log(f'batch: could not load rates from {LATEST}: The read operation timed out')
        return 2, None
    load = RNG.uniform(0.25, 0.7)
    log(f'batch: rates from {LATEST} (snapshot of 2026-10-{day - 1:02d}) in {load:.2f}s', load)
    log(f'batch: {PLANS} invoices on 4 workers, writing to batch-out', 0.01)
    per_plan = RNG.uniform(1.1, 1.6) / PLANS * (1.8 if job['runner'] in SMALL else 1)
    started = log.now
    events = []  # (seconds after start, order, lines)
    live, written = 4, 0
    workers = RNG.sample(range(1, 5), 4)
    fills = {'DB': 0, 'RDB': DISK_FILLS_AT}.get(outcome)
    regression = outcome in ('RB', 'RDB')
    for index in range(PLANS):
        if not live:
            break
        at = index * per_plan + RNG.uniform(0, 0.004)
        if regression and index in BAD_PLANS:
            text = captured['batch'].value_error[:-1] + [captured['batch'].message(index, day)]
        elif fills is not None and index >= fills:
            text = captured['batch'].no_space
        else:
            written += 1
            if written % 160 == 0:
                events.append((at, 1, [f'batch: {written}/{PLANS} schedules written']))
            continue
        live -= 1
        events.append((at, 0, [f'Exception in thread batch-worker-{workers.pop()}:', *text]))
    for at, _, lines in sorted(events, key=lambda e: (e[0], e[1])):
        log.now = max(log.now, started + datetime.timedelta(seconds=at))
        log('\n'.join(lines))
    if written == PLANS:
        took = PLANS * per_plan + RNG.uniform(0.01, 0.05)
        log(f'batch: wrote {PLANS} schedules to batch-out in {took:.1f}s',
            max(0.0, took - (log.now - started).total_seconds()))
        return 0, written
    for after in range(30, 600, 30):
        log.now = started + datetime.timedelta(seconds=after + RNG.uniform(0.001, 0.012))
        log(f'batch: still waiting for {PLANS - written} of {PLANS} schedules after {after}s')
    log.now = started + datetime.timedelta(seconds=600 + RNG.uniform(0.001, 0.012))
    log(f'batch: timed out after 600s: {PLANS - written} of {PLANS} schedules not written')
    return 3, written


def write_job(job, captured):
    name, outcome, runner, commit = job['job'], job['outcome'], job['runner'], job['commit']
    python = PYTHON['3.11' if name == 'test-py311' else '3.12']
    log = Log(job['start'])
    noise = job['noise']
    exit_code, failed_step, step_lines, written = None, None, [], None

    log.step('Set up job')
    log(f"Job {job['id']} · {name} · pipeline {job['pipeline']} ({job['trigger']}) · "
        f"attempt {job['attempt']}")
    if outcome == 'X':
        log(f'Waiting for a runner (queue: {RNG.randint(14, 31)} jobs ahead)', 0.01)
        log(f'Job cancelled before it started: pipeline {job["superseded_by"]} superseded this one '
            '(a newer push to main)', (job['cancel_at'] - log.now).total_seconds())
        return log, None, None, []
    kind = 'small' if runner in SMALL else 'std'
    log(f'Runner {runner} ({SPECS[kind]}), image ubuntu-22.04 2026.10.06', 0.01)
    if noise == 'orphan':
        log(f'Killed orphan process {RNG.randint(1800, 4200)} (sccache) left over from a previous job', 0.3)

    log.step('Checkout')
    log(f"$ git fetch --depth=1 origin {commit.sha}")
    log(f'HEAD is now at {commit.sha[:7]} {commit.subject}', RNG.uniform(0.4, 1.2))

    log.step(f'Set up Python {python[:4]}')
    log(f'Using Python {python} from /opt/hostedtoolcache/Python/{python}/x64', 0.4)

    log.step('Restore wheelhouse')
    key = f'wheelhouse-py{python[:4].replace(".", "")}-5d41c2'
    log(f'GET {CACHE}/{key}.tar.zst')
    if outcome == 'N':
        received = 0
        for attempt in (1, 2, 3):
            log(f'curl: (28) Operation timed out after 60000 milliseconds with {received} out of '
                f'4299161 bytes received', 60 + RNG.uniform(0, 0.4))
            if attempt < 3:
                log(f'attempt {attempt}/3 failed, retrying in {10 * attempt}s')
                log.tick(10 * attempt)
            received = RNG.choice([0, 0, 65536, 1835008])
        log('attempt 3/3 failed')
        log(f'##[error]Could not restore {key} from the artifact cache after 3 attempts')
        exit_code, failed_step = 28, 'Restore wheelhouse'
        step_lines = log.lines[-8:]
    else:
        if noise == 'retry':
            log('curl: (28) Operation timed out after 30000 milliseconds with 1835008 out of '
                '4299161 bytes received', 30.0)
            log('attempt 1/3 failed, retrying in 10s')
            log.tick(10)
        log(f'restored {key} (4.1 MB) in {RNG.uniform(0.8, 3.5):.1f}s', RNG.uniform(0.8, 3.5))

    if failed_step is None:
        log.step('Install')
        log('$ python -m pip install --no-index --find-links wheelhouse -r requirements-dev.txt')
        log('Looking in links: wheelhouse', 0.6)
        for package, version in reversed(WHEELS):
            log(f'Processing ./wheelhouse/{package}-{version}-py3-none-any.whl', 0.05)
        log('Installing collected packages: ' + ', '.join(p for p, _ in WHEELS), 0.4)
        if outcome == 'O-install':
            log('##[error]Process completed with exit code 137.', RNG.uniform(3, 9))
            for line in oom_note(runner):
                log(line)
            exit_code, failed_step = 137, 'Install'
        elif outcome == 'D-install':
            log('ERROR: Could not install packages due to an OSError: [Errno 28] No space left '
                "on device: '/home/runner/.cache/pip/wheels/3c/pytest-9.1.1.dist-info'", 2.1)
            log('##[error]Process completed with exit code 1.')
            exit_code, failed_step = 1, 'Install'
        else:
            log('Successfully installed ' + ' '.join(f'{p}-{v}' for p, v in sorted(WHEELS)), 2.4)
        step_lines = log.lines[-4:]

    if failed_step is None:
        step = RUN_STEP[name]
        log.step(step)
        mark = len(log.lines)
        log(f'$ {COMMANDS[name]}')
        if name.startswith('test-'):
            lines, code, seconds = run_pytest(commit, python, outcome, captured)
            log('\n'.join(lines[:5]), 0.3)
            log.tick(seconds)
            log('\n'.join(lines[5:]))
        elif name == 'batch-smoke':
            code, written = run_batch(log, job, captured)
        else:
            code = build_step(log, name, outcome, commit, runner)  # logs its own errors
        if code and (name.startswith('test-') or name == 'batch-smoke'):
            log(f'##[error]Process completed with exit code {code}.')
            if code == 137:
                for line in oom_note(runner):
                    log(line)
        if code:
            exit_code, failed_step = code, step
        step_lines = log.lines[mark:]

    # Post steps run whatever happened before them.
    if name.startswith('test-') and outcome in ('P', 'R', 'T-fixture', 'T-feed'):
        log.step('Upload report.xml (always)')
        log(f'uploaded report.xml ({RNG.uniform(4, 9):.1f} kB)', 0.6)
    if name == 'batch-smoke' and written is not None:
        log.step('Upload batch-out (always)')
        log(f'uploaded batch-out ({written} files, {written * 0.131:.1f} kB)', 0.4 + written / 900)
    log.step('Save cache (always)')
    if noise == 'cache-disk' or outcome.startswith('D') or outcome == 'RDB':
        log("warning: could not save the pip cache: [Errno 28] No space left on device: "
            "'/home/runner/.cache/pip/http-v2/a/3/e'", 1.2)
        log('warning: cache not saved; this does not affect the job result')
    elif failed_step == 'Restore wheelhouse':
        log('nothing to save', 0.1)
    else:
        log(f'saved pip cache ({RNG.uniform(9, 14):.1f} MB)', RNG.uniform(1, 3))
    log.step('Complete job')
    if failed_step:
        log(f'Job failed: step "{failed_step}" exited with code {exit_code}')
    else:
        log('Job succeeded')
    return log, exit_code, failed_step, step_lines


def build_step(log, name, outcome, commit, runner):
    if outcome == 'O-build':
        log('##[error]Process completed with exit code 137.', RNG.uniform(5, 20))
        for line in oom_note(runner):
            log(line)
        return 137
    if outcome == 'D-build':
        tool = 'make_dist.py' if name == 'package' else 'build_docs.py'
        statement = ('archive.write(path, path.relative_to(ROOT))' if name == 'package'
                     else '(out / "api.md").write_text("\\n".join(lines), encoding="utf-8")')
        source = git('show', f'{commit.sha}:tools/{tool}').splitlines()
        number = next(i for i, line in enumerate(source, 1) if statement in line)
        log('Traceback (most recent call last):', RNG.uniform(0.5, 2))
        log(f'  File "{CHECKOUT}/tools/{tool}", line {number}, in <module>')
        log(f'    {statement}')
        log('OSError: [Errno 28] No space left on device')
        log('##[error]Process completed with exit code 1.')
        return 1
    if outcome != 'P':
        raise ValueError(outcome)
    if name == 'lint':
        log('checked 4 folders: 0 problems', RNG.uniform(0.4, 0.9))
    elif name == 'docs':
        modules = 6 if commit.index >= 13 else 2
        log(f'wrote site/api.md ({18 + 8 * modules + commit.index} lines)', RNG.uniform(0.5, 1))
    elif name == 'package':
        version = '0.9.0' if commit.index >= 20 else '0.8.0'
        size = 2900 + 140 * commit.index + RNG.randint(0, 60)
        log(f'built dist/fernbill-{version}.zip ({size} bytes)', RNG.uniform(0.4, 0.8))
    elif name == 'examples':
        log('subtotal 1352.40 EUR\ntax      216.60 EUR\ntotal    1569.00 EUR', RNG.uniform(0.3, 0.6))
    return 0


def auto_triage(status, exit_code, failed_step, step_lines):
    """The CI triage bot: the failed step, its exit code, and the step's last lines."""
    if status != 'failure':
        return None
    tail = ' '.join(step_lines[-12:])
    if exit_code == 137:
        return 'infra: out of memory'
    if 'No space left on device' in tail:
        return 'infra: disk full'
    if 'timed out' in tail.lower():
        return 'infra: timeout'
    if failed_step in ('Restore wheelhouse', 'Install'):
        return 'infra'
    if failed_step == 'Run tests':
        return 'test failure'
    return 'needs triage'


# ---------------------------------------------------------------- scheduling

def pick_runner(outcome, start):
    if outcome.startswith('O-'):
        return RNG.choice(SMALL)
    if outcome.startswith('D') or outcome == 'RDB':
        return 'ci-std-04' if start.day <= 15 else 'ci-std-07'
    return RNG.choice(STD + SMALL)


def pick_noise(job):
    forced = FORCED_NOISE.get((job['key'], job['job'], job['attempt']))
    if forced:
        return forced
    if job['outcome'] not in ('P', 'T-fixture', 'T-feed', 'R'):
        return None
    if job['runner'] in ('ci-std-04', 'ci-std-07') and RNG.random() < 0.5:
        return 'cache-disk' if job['outcome'] in ('P', 'R') else None
    roll = RNG.random()
    if job['start'].day >= 14 and roll < 0.14:
        return 'retry'
    if roll > 0.94:
        return 'orphan'
    return None


def head_at(commits, moment):
    return [c for c in commits if c.date <= moment][-1]


def plan_jobs(commits):
    pipelines = []
    for row, outcomes in enumerate(PUSH):
        commit = commits[FIRST_PIPELINE_COMMIT + row]
        start = commit.date + datetime.timedelta(seconds=RNG.randint(40, 120))
        pipelines.append((start, ('push', commit.index + 1), commit, 'push', JOBS, outcomes))
    for day, outcomes in NIGHTLY.items():
        start = utc(day, 2) + datetime.timedelta(seconds=RNG.randint(5, 50))
        pipelines.append((start, ('nightly', day), head_at(commits, start), 'nightly',
                          NIGHTLY_JOBS, outcomes))
    pipelines.sort(key=lambda p: p[0])
    jobs = []
    for number, (start, key, commit, trigger, names, outcomes) in enumerate(pipelines, 5101):
        for name, outcome in zip(names, outcomes):
            if outcome == '-':
                assert name == 'batch-smoke' and commit.index < BATCH_COMMIT, (key, name)
                continue
            assert name != 'batch-smoke' or commit.index >= BATCH_COMMIT, key
            begin = start + datetime.timedelta(seconds=RNG.randint(2, 30))
            jobs.append({'pipeline': number, 'key': key, 'trigger': trigger, 'job': name,
                         'outcome': outcome, 'commit': commit, 'attempt': 1, 'start': begin})
    for key, name, outcome, minutes in RERUNS:
        original = next(j for j in jobs if j['key'] == key and j['job'] == name)
        assert original['outcome'] in FAILED_OUTCOMES, (key, name)
        begin = original['start'] + datetime.timedelta(minutes=minutes, seconds=RNG.randint(0, 59))
        jobs.append({**original, 'outcome': outcome, 'attempt': 2, 'start': begin,
                     'rerun_of': original})
    jobs.sort(key=lambda j: j['start'])
    next_id, last_pipeline = 48207, None
    for job in jobs:
        if job['pipeline'] != last_pipeline or job['attempt'] == 2:
            next_id += RNG.randint(3, 41)   # Other repositories share the CI server.
            last_pipeline = job['pipeline']
        else:
            next_id += 1
        job['id'] = str(next_id)
        job['runner'] = None if job['outcome'] == 'X' else pick_runner(job['outcome'], job['start'])
        job['noise'] = pick_noise(job)
        if job['outcome'] == 'X':
            job['superseded_by'] = job['pipeline'] + 1
            newer = commits[job['commit'].index + 1].date
            job['cancel_at'] = newer + datetime.timedelta(seconds=RNG.randint(45, 80))
    return jobs


def check_plan(jobs):
    for job in jobs:
        index, outcome, name = job['commit'].index, job['outcome'], job['job']
        if outcome in REGRESSION:
            assert index >= CULPRIT
            assert (name == 'batch-smoke') == (outcome != 'R')
        if outcome in ('D-report', 'T-feed', 'F'):
            assert index < CULPRIT, 'the job would have hit the regression too'
        if outcome == 'T-feed':
            assert 'tests/test_feed.py' in job['commit'].test_files
        if index >= CULPRIT and outcome == 'P':
            assert not (name.startswith('test-') or name == 'batch-smoke'), 'a job after the culprit passed'
    test_reds = [j for j in jobs if j['outcome'] == 'R']
    assert min(j['commit'].index for j in test_reds) == CULPRIT + 1
    assert min(j['commit'].index for j in jobs if j['outcome'] in ('RB', 'RDB')) == CULPRIT


README = """\
# CI job records

Two exports of the CI server's job history for fernbill, each holding every
job of the pipelines on `main` that started in its date range (UTC):

- `oct05-oct19/`: Oct 5 to Oct 19, pulled on Oct 20 for the INC-2291 review;
- `oct18-oct21/`: Oct 18 to Oct 21, pulled on Oct 21.

They overlap: a job that started on Oct 18 or 19 is in both, as the same
record. Pipelines run on every push to `main` and nightly at 02:00 UTC on
`main`'s latest commit; the jobs are in `.ci/pipeline.yml`.

Each export has one folder per job, named by the job's id:

- `job.json`: pipeline, trigger (`push` or `nightly`), job name, commit,
  runner, status (`success`, `failure`, or `cancelled`), exit code, the step
  that failed, timings, and `attempt` (2 for a manual re-run of a failed job,
  which gets its own job id and record).
- `log.txt`: the job's full log.

`auto_triage` is filled in by the CI triage bot from the step that failed,
its exit code, and the step's last lines.

## Triage

Classify each failed job by what made it fail, as its log shows: the code
(the repository's code or tests) or the infrastructure (runners, the
artifact cache, the network, disks, memory limits). A job whose log shows a
problem in the code counts as a code failure even if the infrastructure
failed it too.
"""

INCIDENT = """\
# INC-2291: artifact cache degraded

Oct 14 to Oct 21 · CI on-call: Tomás Ferreira · resolved Oct 21, 10:40 UTC

## What happened

From Oct 14 the artifact cache (`artifacts.ci.fernbill.internal`) was moving
its objects to a new storage pool. Until the move finished on Oct 21, reads
of some objects stalled or timed out, on and off. Over the same days the
disks of ci-std-04 and ci-std-07 kept filling up with old image layers;
ci-std-04 was wiped on Oct 16 and ci-std-07 on Oct 21.

## Impact on fernbill

Nearly all of fernbill's red CI in this window is the incident:

- `Restore wheelhouse` timing out (curl exit 28);
- `ERROR at setup` on every test that uses the `rates` fixture, and
  `test_latest_snapshot_loads` failing, both with `TimeoutError: The read
  operation timed out`: the fixture and the feed test read through the cache;
- `batch-smoke` failing to load the treasury feed's snapshot, or hanging
  until its 600 s timeout: it reads `rates-latest.json` through the cache,
  and its workers sit waiting when that read stalls;
- `No space left on device` on ci-std-04 and ci-std-07.

The only real failures are `test_convert_usd_to_jpy` and `test_total_in_jpy`
in the test jobs, which started with the change to how JPY is formatted on
Oct 19. Marta is looking at those.

## Follow-ups

- Re-run the jobs that failed with the symptoms above (some done).
- Give the batch's rates fetch a timeout.
"""


def protected_versions():
    """Every version of the tests, conftest.py, and the test data in the history."""
    versions = {}
    for sha in git('rev-list', 'HEAD').split():
        for path in git('ls-tree', '-r', '--name-only', sha).split():
            if PROTECTED.fullmatch(path):
                blob = subprocess.run(['git', 'show', f'{sha}:{path}'], cwd=WORKSPACE,
                                      check=True, capture_output=True).stdout
                versions.setdefault(path, set()).add(hashlib.sha256(blob).hexdigest())
    return {path: sorted(digests) for path, digests in sorted(versions.items())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()

    commits = load_commits()
    assert len(commits) == 21 and commits[CULPRIT].subject == 'Take minor units from the rates snapshot'
    assert commits[BATCH_COMMIT].subject.startswith('Add the monthly installment batch')
    captured = {'regression': regression_failures(), 'report_disk_full': report_disk_full(),
                'batch': BatchCapture()}
    jobs = plan_jobs(commits)
    check_plan(jobs)
    CI.mkdir()
    (CI / 'README.md').write_text(README, encoding='utf-8')
    (CI / 'INC-2291.md').write_text(INCIDENT, encoding='utf-8')
    records = {}
    for job in jobs:
        log, exit_code, failed_step, step_lines = write_job(job, captured)
        status = {'P': 'success', 'X': 'cancelled'}.get(job['outcome'], 'failure')
        record = {
            'id': job['id'],
            'pipeline': job['pipeline'],
            'trigger': job['trigger'],
            'job': job['job'],
            'commit': job['commit'].sha,
            'branch': 'main',
            'attempt': job['attempt'],
            'runner': job['runner'],
            'started_at': job['start'].strftime('%Y-%m-%dT%H:%M:%SZ'),
            'duration_s': round((log.now - job['start']).total_seconds()),
            'status': status,
            'exit_code': exit_code,
            'failed_step': failed_step,
            'auto_triage': auto_triage(status, exit_code, failed_step, step_lines),
        }
        if job['attempt'] == 2:
            record['rerun_of'] = job['rerun_of']['id']
        files = {'job.json': json.dumps(record, indent=2) + '\n',
                 'log.txt': '\n'.join(log.lines) + '\n'}
        records[job['id']] = (job, record, files)
        exported = 0
        for export, first, last in EXPORTS:
            if first <= job['start'].day <= last:
                folder = CI / export / job['id']
                folder.mkdir(parents=True)
                for name, text in files.items():
                    (folder / name).write_text(text, encoding='utf-8')
                exported += 1
        assert exported in (1, 2), job['id']

    if args.manifest:
        failed = {i: job for i, (job, record, _) in records.items() if record['status'] == 'failure'}
        regression = sorted(i for i, job in failed.items() if job['outcome'] in REGRESSION)
        both = {i for i, (job, _, _) in records.items() if 18 <= job['start'].day <= 19}
        first_red = min((job for job in failed.values() if job['outcome'] == 'R'),
                        key=lambda job: job['start'])
        manifest = {
            'jobs_recorded': len(records),
            'records_with_duplicates': len(records) + len(both),
            'infra_failures': len(failed) - len(regression),
            'regression_failures': len(regression),
            'regression_jobs': regression,
            'batch_regression_jobs': sorted(i for i in regression if failed[i]['job'] == 'batch-smoke'),
            'test_regression_jobs': sorted(i for i in regression if failed[i]['job'] != 'batch-smoke'),
            'two_cause_jobs': sorted(i for i, job in failed.items() if job['outcome'] == 'RDB'),
            'batch_disk_full_jobs': sorted(i for i, job in failed.items() if job['outcome'] == 'DB'),
            'batch_timeout_jobs': sorted(i for i, job in failed.items()
                                         if job['outcome'] in ('RB', 'RDB', 'DB')),
            'failed_jobs': sorted(failed),
            'failed_jobs_in_both_exports': sorted(set(failed) & both),
            'jobs_in_both_exports': sorted(both),
            'culprit_commit': commits[CULPRIT].sha,
            'first_red_test_commit': first_red['commit'].sha,
            'first_red_test_job': first_red['id'],
            'outcomes': {i: job['outcome'] for i, (job, _, _) in sorted(records.items())},
            'protected_file_versions': protected_versions(),
        }
        args.manifest.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
