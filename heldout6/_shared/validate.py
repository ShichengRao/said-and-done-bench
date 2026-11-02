"""Validate explicit replacement tasks and retain exact source/test evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from beambench.tasks import load_task, task_hash, grader_hash


def identity(task_id):
    task = load_task(ROOT / 'heldout6' / task_id)
    test = ROOT / 'tests' / ('test_task_' + task_id.replace('-', '_') + '.py')
    return {'task_hash': task_hash(task), 'grader_hash': grader_hash(task),
            'test_file': str(test.relative_to(ROOT)),
            'test_sha256': hashlib.sha256(test.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tasks', nargs='+')
    args = parser.parse_args()
    assert len(set(args.tasks)) == len(args.tasks)
    for task_id in args.tasks:
        if not task_id.startswith('h6-') or '/' in task_id or '..' in task_id:
            parser.error('use explicit h5 task IDs')
    before = {task_id: identity(task_id) for task_id in args.tasks}
    target = ROOT / 'heldout6' / 'validation'
    target.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    log = target / f'{run_id}.log'
    xml = target / f'{run_id}.xml'
    command = ['uv', 'run', 'pytest', '-q',
               *(entry['test_file'] for entry in before.values()),
               'tests/test_tasks.py', f'--junitxml={xml}']
    started = time.monotonic()
    with log.open('w') as stream:
        result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    counts = {'tests': 0, 'failures': 0, 'errors': 0, 'skipped': 0}
    if xml.exists():
        tree = ET.parse(xml).getroot()
        suites = [tree] if tree.tag == 'testsuite' else list(tree.findall('testsuite'))
        for suite in suites:
            for key in counts:
                counts[key] += int(suite.attrib.get(key, 0))
    after = {task_id: identity(task_id) for task_id in args.tasks}
    valid = (result.returncode == 0 and counts['tests'] > 0
             and not any(counts[key] for key in ('failures', 'errors', 'skipped'))
             and before == after)
    record = {'at': datetime.now(timezone.utc).isoformat(), 'run_id': run_id,
              'command': command, 'exit_code': result.returncode, 'counts': counts,
              'seconds': round(time.monotonic() - started, 3),
              'valid': valid, 'source_unchanged': before == after,
              'log': str(log.relative_to(ROOT)),
              'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
              'xml': str(xml.relative_to(ROOT)),
              'xml_sha256': hashlib.sha256(xml.read_bytes()).hexdigest() if xml.exists() else None,
              'tasks': before, 'after': after}
    (target / f'{run_id}.json').write_text(json.dumps(record, indent=2) + '\n')
    if valid:
        for task_id in args.tasks:
            (target / f'{task_id}.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({key: record[key] for key in
                      ('run_id', 'valid', 'exit_code', 'counts', 'seconds', 'source_unchanged', 'log')}), flush=True)
    if not valid:
        print(log.read_text()[-6000:])
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
