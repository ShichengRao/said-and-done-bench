"""A pytest plugin for the held-out graders: writes each test's outcome to $GRADER_OUTCOMES.

A test is failed if any of its phases failed, skipped if it was skipped
(xfail included), and passed otherwise. Files that failed to import are
listed as collection errors.
"""

import json
import os
from pathlib import Path

_tests = {}
_collection_errors = []


def pytest_runtest_logreport(report):
    current = _tests.get(report.nodeid)
    if report.failed:
        _tests[report.nodeid] = 'failed'
    elif report.skipped:
        if current is None:
            _tests[report.nodeid] = 'skipped'
    elif report.when == 'call' and current is None:
        _tests[report.nodeid] = 'passed'


def pytest_collectreport(report):
    if report.failed:
        _collection_errors.append(report.nodeid)


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get('GRADER_OUTCOMES')
    if path:
        Path(path).write_text(json.dumps({
            'tests': _tests, 'collection_errors': _collection_errors, 'exitstatus': int(exitstatus),
        }))
