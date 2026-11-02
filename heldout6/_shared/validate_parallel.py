"""Bounded, per-file validation; preserves the serial validator's eligibility schema."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = Path(__file__).resolve()
sys.path.insert(0, str(ROOT))
from beambench.tasks import grader_hash, harness_hash, load_task, task_hash

COUNT_KEYS = ('tests', 'failures', 'errors', 'skipped')
SHARED_TEST = 'tests/test_tasks.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(task_id):
    task = load_task(ROOT / 'heldout6' / task_id)
    test = ROOT / 'tests' / ('test_task_' + task_id.replace('-', '_') + '.py')
    return {'task_hash': task_hash(task), 'grader_hash': grader_hash(task),
            'test_file': str(test.relative_to(ROOT)), 'test_sha256': sha(test)}


def dependencies():
    paths = [WRAPPER, ROOT / SHARED_TEST, ROOT / 'tests/task_helpers.py',
             ROOT / 'pyproject.toml', ROOT / 'uv.lock', ROOT / 'conftest.py', ROOT / 'tests/conftest.py']
    return {'files': {str(p.relative_to(ROOT)): sha(p) if p.exists() else None for p in paths},
            'harness_hash': harness_hash()}


def xml_suites(path):
    tree = ET.parse(path).getroot()
    if tree.tag not in ('testsuite', 'testsuites'):
        raise ValueError('unexpected JUnit root')
    suites = [tree] if tree.tag == 'testsuite' else list(tree.findall('testsuite'))
    counts = {k: sum(int(s.attrib.get(k, 0)) for s in suites) for k in COUNT_KEYS}
    if any(n < 0 for n in counts.values()):
        raise ValueError('negative JUnit counts')
    return suites, counts


def write_json(path, value):
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        temporary = Path(stream.name)
    temporary.replace(path)


def validate(task_ids, workers=2, runner=None):
    if (not task_ids or len(set(task_ids)) != len(task_ids) or workers < 1
            or any(not re.fullmatch(r'h6-[a-z0-9]+(?:-[a-z0-9]+)*', t) for t in task_ids)):
        raise ValueError('provide distinct h6 task IDs and a positive worker count')
    runner = subprocess.run if runner is None else runner
    before = {t: identity(t) for t in task_ids}
    bound = dependencies()
    files = [entry['test_file'] for entry in before.values()] + [SHARED_TEST]
    if len(files) != len(set(files)):
        raise ValueError('test file would run more than once')
    target = ROOT / 'heldout6/validation'
    target.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    evidence = target / (run_id + '-files')
    evidence.mkdir()
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='h6-validation-') as temporary:
        def execute(item):
            index, test = item
            stem = f'{index:03d}-{Path(test).stem}'
            log, xml = evidence / (stem + '.log'), evidence / (stem + '.xml')
            command = ['uv', 'run', 'pytest', '-q', test, f'--junitxml={xml}',
                       f'--basetemp={Path(temporary) / stem}']
            result = {'test_file': test, 'command': command, 'exit_code': None}
            begin = time.monotonic()
            with log.open('x') as stream:
                try:
                    result['exit_code'] = runner(command, cwd=ROOT, stdout=stream,
                                                  stderr=subprocess.STDOUT).returncode
                except Exception as exc:
                    result['runner_error'] = repr(exc)
                    stream.write(f'Runner error: {exc!r}\n')
            result.update(seconds=round(time.monotonic() - begin, 3),
                          log=str(log.relative_to(ROOT)), log_sha256=sha(log),
                          xml=str(xml.relative_to(ROOT)), xml_sha256=sha(xml) if xml.exists() else None)
            try:
                _, result['counts'] = xml_suites(xml)
            except (OSError, ValueError, ET.ParseError) as exc:
                result['xml_error'] = repr(exc)
                result['counts'] = dict.fromkeys(COUNT_KEYS, 0)
            result['valid'] = (result['exit_code'] == 0 and not result.get('xml_error')
                               and result['counts']['tests'] > 0
                               and not any(result['counts'][k] for k in COUNT_KEYS[1:]))
            return result

        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(execute, enumerate(files)))
    after = {}
    for task_id in task_ids:
        try:
            after[task_id] = identity(task_id)
        except Exception as exc:
            after[task_id] = {'error': repr(exc)}
    try:
        after_bound = dependencies()
    except Exception as exc:
        after_bound = {'error': repr(exc)}
    unchanged = before == after and bound == after_bound
    valid = all(r['valid'] for r in results) and unchanged
    log, xml = target / (run_id + '.log'), target / (run_id + '.xml')
    merged = ET.Element('testsuites')
    with log.open('x') as stream:
        for result in results:
            stream.write(json.dumps(result, sort_keys=True) + '\n')
            stream.write((ROOT / result['log']).read_text())
            if not result.get('xml_error'):
                suites, _ = xml_suites(ROOT / result['xml'])
                merged.extend(suites)
    ET.ElementTree(merged).write(xml, encoding='utf-8', xml_declaration=True)
    _, counts = xml_suites(xml)
    record = {'at': datetime.now(timezone.utc).isoformat(), 'run_id': run_id,
              'command': [sys.executable, str(WRAPPER), '--workers', str(workers), *task_ids],
              'exit_code': 0 if valid else 1, 'counts': counts,
              'seconds': round(time.monotonic() - started, 3), 'valid': valid,
              'source_unchanged': unchanged, 'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log),
              'xml': str(xml.relative_to(ROOT)), 'xml_sha256': sha(xml), 'tasks': before, 'after': after,
              'workers': workers, 'file_runs': results, 'dependencies': bound, 'dependencies_after': after_bound}
    # Failed batches retain evidence, but never replace any task's eligibility pointer.
    write_json(target / (run_id + '.json'), record)
    if valid:
        for task_id in task_ids:
            write_json(target / (task_id + '.json'), record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('tasks', nargs='+')
    args = parser.parse_args()
    try:
        record = validate(args.tasks, args.workers)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps({k: record[k] for k in ('run_id', 'valid', 'exit_code', 'counts', 'seconds',
                                            'source_unchanged', 'log')}), flush=True)
    return 0 if record['valid'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
