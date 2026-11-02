import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def data(tmp_path):
    path = tmp_path / 'invoices.json'
    path.write_text(json.dumps({
        'customers': [{'id': 'C-1', 'name': 'Acme', 'timezone': 'Europe/Berlin', 'terms': 'NET30'}],
        'invoices': [
            {'number': 'INV-1', 'customer': 'C-1', 'issued_at': '2026-09-14T10:30:00Z',
             'lines': [{'description': 'Crates', 'quantity': 4, 'unit_price': '12.50'}]},
            {'number': 'INV-2', 'customer': 'C-1', 'issued_at': '2026-10-02T09:00:00Z',
             'lines': [{'description': 'Crates', 'quantity': 1, 'unit_price': '12.50'}]},
        ],
    }))
    return path


def cli(data, *args):
    return subprocess.run([sys.executable, '-m', 'invoicing', *args], cwd=ROOT, capture_output=True, text=True,
                          env={**os.environ, 'INVOICING_DATA': str(data)})


def test_due(data):
    result = cli(data, 'due', 'INV-1')
    assert result.returncode == 0 and result.stdout == 'INV-1 Acme: due 2026-10-14 (NET30)\n'


def test_show(data):
    lines = cli(data, 'show', 'INV-1').stdout.splitlines()
    assert lines[2] == 'Issued: 2026-09-14 12:30' and lines[3] == 'Due:    2026-10-14 (NET30)'
    assert lines[-1].endswith(' 50.00')



def test_unknown_invoice(data):
    result = cli(data, 'due', 'INV-404')
    assert result.returncode == 1 and 'no invoice INV-404' in result.stderr
