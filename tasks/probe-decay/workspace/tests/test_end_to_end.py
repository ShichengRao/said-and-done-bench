"""November's outputs, which Harbour Operations checked by hand (tests/golden/)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def tidewater(*arguments):
    result = subprocess.run([sys.executable, '-m', 'tidewater', *arguments], cwd=ROOT, capture_output=True,
                            text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    return result.stdout.splitlines()


def test_november_report_matches_the_signed_off_copy():
    assert tidewater('report', 'data/2026-11') == (ROOT / 'tests' / 'golden' / 'report-2026-11.txt').read_text().splitlines()


def test_cape_mercy_export_matches_the_signed_off_copy():
    assert tidewater('export', 'data/2026-11', '--station', 'CMY') == (
        ROOT / 'tests' / 'golden' / 'export-CMY-2026-11.csv').read_text().splitlines()
