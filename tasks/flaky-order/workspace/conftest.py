"""Shared test setup.

Lets the tests import `tallyboard` from the repository root, and runs the
tests in a random order, as CI does, so tests that depend on each other show
up. The order comes from TEST_SEED (picked at random when it isn't set) and is
printed at the end of every run; set TEST_SEED to that value to rerun the
same order.
"""

import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

_seed = None
_exported = False


def pytest_configure(config):
    global _seed, _exported
    _seed = os.environ.get("TEST_SEED") or str(random.SystemRandom().randrange(1_000_000))
    if "TEST_SEED" not in os.environ:
        # Export it for the rest of this session, so tools that read TEST_SEED see the same seed.
        os.environ["TEST_SEED"] = _seed
        _exported = True


def pytest_unconfigure(config):
    global _exported
    if _exported:
        os.environ.pop("TEST_SEED", None)
        _exported = False


def pytest_report_header(config):
    return f"test order: shuffled with TEST_SEED={_seed}"


def pytest_collection_modifyitems(session, config, items):
    random.Random(_seed).shuffle(items)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    terminalreporter.write_line(f"test order: TEST_SEED={_seed} (set TEST_SEED to this value to rerun in the same order)")
