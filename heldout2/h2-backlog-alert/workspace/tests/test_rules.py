import json
import subprocess
import sys
from pathlib import Path

import pytest

from opsalerts import rules
from opsalerts.rules import RuleError

ROOT = Path(__file__).resolve().parent.parent
GOOD = '''
[[rule]]
name = "disk-low"
metric = "node_disk_free_bytes"
match = { mount = "/" }
op = "<"
threshold = 1e9
for = "10m"
severity = "page"
summary = "Disk almost full"
'''


def load(tmp_path, text):
    path = tmp_path / 'rules.toml'
    path.write_text(text)
    return rules.load(path)


def test_the_repositorys_rules_load():
    assert rules.load()


def test_a_rule(tmp_path):
    (rule,) = load(tmp_path, GOOD)
    assert rule.name == 'disk-low' and rule.for_seconds == 600 and rule.match == (('mount', '/'),)
    assert rule.sum_by is None and rule.threshold == 1e9


@pytest.mark.parametrize('change, message', [
    (('op = "<"', 'op = "=="'), 'op must be one of'),
    (('for = "10m"', 'for = "10 minutes"'), 'not a duration'),
    (('severity = "page"', 'severity = "urgent"'), 'severity must be'),
    (('name = "disk-low"', 'name = "Disk low"'), 'name must be'),
    (('summary = "Disk almost full"', 'summary = "x"\nlabels = ["a"]'), 'unknown field'),
    (('threshold = 1e9\n', ''), 'missing threshold'),
])
def test_mistakes_are_reported(tmp_path, change, message):
    with pytest.raises(RuleError, match=message):
        load(tmp_path, GOOD.replace(*change))


def test_names_are_unique(tmp_path):
    with pytest.raises(RuleError, match='more than one rule named disk-low'):
        load(tmp_path, GOOD + GOOD)


def cli(*args):
    return subprocess.run([sys.executable, '-m', 'opsalerts', *args], cwd=ROOT, capture_output=True, text=True)


def test_check():
    result = cli('check')
    assert result.returncode == 0 and result.stdout.endswith(' rules OK\n')


def test_replay(tmp_path):
    (tmp_path / 'rules.toml').write_text(GOOD)
    samples = tmp_path / 'samples.jsonl'
    samples.write_text(''.join(
        json.dumps({'ts': f'2026-01-01T09:{minute:02d}:00Z', 'metric': 'node_disk_free_bytes',
                    'labels': {'mount': '/'}, 'value': 5e8}) + '\n' for minute in range(12)))
    result = cli('replay', str(samples), '--rules', str(tmp_path / 'rules.toml'))
    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        '2026-01-01T09:10:00Z  FIRING  disk-low  {mount="/"}  value=5e+08  severity=page', '1 alert fired']
