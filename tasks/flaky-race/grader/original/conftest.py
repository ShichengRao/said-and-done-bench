"""Shared test setup.

Lets the tests import `holdfast` from the repository root, and seeds the
global `random` generator before each test from TEST_SEED (picked at random
when it isn't set). Every run prints its seed at the end; set TEST_SEED to
that value to replay a run's random choices.
"""

import os
import random
import sys
from pathlib import Path

import pytest

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
    return f"TEST_SEED={_seed}"


@pytest.fixture(autouse=True)
def _seeded_random(request):
    random.seed(f"{_seed}:{request.node.name}")


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    terminalreporter.write_line(f"TEST_SEED={_seed} (set TEST_SEED to this value to replay this run's random choices)")
