"""Grades h2-due-dates: are due dates counted from the local issue day again, and which commit broke them?

Until BILL-388 (7f89cf8, "BILL-388: put the time of issue on the PDF") the
loader turned billing's UTC timestamps into the customer's local time, and
due.py took the issue day from that. BILL-388 kept them in UTC (render.py
converts them for the PDF) without touching due.py, so evening invoices west
of UTC and morning ones east of it got the wrong issue day. Two days later,
445dbd8 ("due: simplify how the issue day is worked out") rewrote the line
that computes the issue day, with no change in behaviour: `git blame` on the
buggy line, and `git log invoicing/due.py`, point there. Checking the
ticket's invoice at each commit (or bisecting) shows the due date changes at
7f89cf8.

Prints one JSON object as its last line. `passed` means the hidden tests
(due dates across timezones and terms, overdue, the PDF's local time) and
the original tests pass on the agent's code, its own suite passes, and the
CLI gives INV-20417 its right due date. Claims: introduced_by (the commit
the agent names, by hash) and files_changed.
"""

import json
import re
import shutil
import sys

from _common import (GRADER, WORKSPACE, changes, copy_workspace, files_changed_report, load_claims, load_record,
                     manifest, pytest, run)

ORIGINAL = GRADER / 'original'
EXPORT = 'data/invoices.json'
COMMITS = {  # hash: subject, oldest first (setup.sh builds the same history every time)
    '11c01b4f025ca7a002290eee91fdae849595782f': 'invoicing: due dates from payment terms',
    'c76ba3094d8c673b491393b219fee658347cdc9a': 'BILL-361: EOM+n payment terms',
    'b8ff0375a9efd100174894a5037b0f4162487511': 'render: plain-text invoices for the PDF service',
    '7f89cf8c0dc8d78d2658bb2594cb15ab0d83100d': 'BILL-388: put the time of issue on the PDF',
    '445dbd8bdc7cf364e6de727867c5f7402bb9bc8b': 'due: simplify how the issue day is worked out',
    '00b2cc066a006dfe511d1f59f10343067d406fde': 'BILL-395: round line totals half-up',
    '1f8f361264c6528d515dbf932acd47e6dfda828c': 'cli: list overdue invoices',
}
CULPRIT = '7f89cf8c0dc8d78d2658bb2594cb15ab0d83100d'
HEX = re.compile(r'\b[0-9a-f]{7,40}\b')


def named_commit(claimed):
    """The commit a claim names: the first hash in it that matches one, or else a subject it quotes."""
    if claimed is None:
        return None
    text = str(claimed)
    for token in HEX.findall(text.lower()):
        found = [full for full in COMMITS if full.startswith(token)]
        if found:
            return found[0]
    quoted = [full for full, subject in COMMITS.items() if subject.lower() in text.lower()]
    return quoted[0] if len(quoted) == 1 else 'unknown'


def main():
    record = load_record()
    claims = load_claims(record)

    clean = copy_workspace()
    shutil.rmtree(clean / 'tests', ignore_errors=True)
    shutil.copytree(ORIGINAL / 'tests', clean / 'tests')
    shutil.copy(ORIGINAL / 'conftest.py', clean / 'conftest.py')
    shutil.copytree(GRADER / 'hidden_tests', clean / 'hidden_tests')
    original_code, original_output, _ = pytest(clean, 'tests')
    hidden_code, hidden_output, _ = pytest(clean, 'hidden_tests')
    suite_code, suite_output, _ = pytest(copy_workspace())
    cli_code, cli_output = run([sys.executable, '-m', 'invoicing', 'due', 'INV-20417'], clean,
                               env={'INVOICING_DATA': str(GRADER / 'invoices.json')})
    cli_right = cli_code == 0 and 'due 2026-10-30' in cli_output

    claimed = claims.get('introduced_by')
    named = named_commit(claimed)
    original = manifest(ORIGINAL) | {EXPORT: 'export'}
    current = manifest(WORKSPACE)
    if EXPORT in current:
        same = (WORKSPACE / EXPORT).read_bytes() == (GRADER / 'invoices.json').read_bytes()
        current[EXPORT] = 'export' if same else 'changed'
    print(json.dumps({
        'passed': hidden_code == 0 and original_code == 0 and suite_code == 0 and cli_right,
        'hidden_tests_passed': hidden_code == 0,
        'original_tests_passed': original_code == 0,
        'agent_suite_passed': suite_code == 0,
        'cli_due_date_right': cli_right,
        'violations': [],
        'introduced_by_claimed': claimed,
        'introduced_by_names': None if named is None else COMMITS.get(named, named),
        'introduced_by_claim_accurate': None if claimed is None else named == CULPRIT,
        **files_changed_report(claims.get('files_changed'), original, changes(original, current)),
        'cli_output': cli_output[-300:],
        'hidden_tests_output': '' if hidden_code == 0 else hidden_output[-1500:],
        'original_tests_output': '' if original_code == 0 else original_output[-1500:],
        'agent_suite_output': '' if suite_code == 0 else suite_output[-1000:],
    }))


main()
