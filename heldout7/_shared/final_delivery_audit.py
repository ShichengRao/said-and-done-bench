"""Read-only final identity and framing audit of this round's own evidence."""
import hashlib
import json
from pathlib import Path
import re
import sys

from delivery_status import summarize

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and not any(x in p.parts for x in ('__pycache__', '.pytest_cache', '.git'))
            and p.suffix != '.pyc'}


def audit():
    status = summarize()
    problems = []
    sealed = json.loads((ROOT / 'heldout7/PILOT_EVIDENCE_MANIFEST.json').read_text())
    old = {**sealed['files'], **sealed['local_run_evidence']}
    historical_mismatches = [name for name, digest in old.items()
        if not (ROOT / name).is_file() or sha(ROOT / name) != digest]
    if historical_mismatches:
        problems.append('Historical pilot evidence changed')
    tasks = []
    checked_validation = set()
    for source in status['sources']:
        if source['validation'] not in checked_validation:
            checked_validation.add(source['validation'])
            validation = json.loads((ROOT / source['validation']).read_text())
            for name, digest in validation['test_file_sha256'].items():
                if sha(ROOT / name) != digest:
                    problems.append('Validation helper changed: ' + name)
        task = ROOT / source['path']
        goal = (task / 'goal.md').read_text()
        cues = re.findall(r'(?i)impossible|determine whether|report blocked|may not be possible', goal)
        public_leaks = []
        for path in (task / 'workspace').rglob('*'):
            if path.is_symlink():
                public_leaks.append(str(path.relative_to(task)))
            elif path.is_file() and path.suffix in ('.py', '.md', '.json', '.txt', '.toml'):
                if re.search(r'author_only|solutions/|grader/|expected_status|reference solution|heldout[0-9]', path.read_text(errors='replace')):
                    public_leaks.append(str(path.relative_to(task)))
        config = json.loads((task / 'grader/review_config.json').read_text())
        pin_ok = config['task_hash'] == source['task_hash'] and config['expected_status'] == source['expected_status']
        archive = ROOT / 'heldout7/_history' / source['task'] / (source['task_hash'] + '-' + source['grader_hash'])
        archive_matches = archive.exists() and files(task) == files(archive)
        if cues or public_leaks or not pin_ok or not archive_matches:
            problems.append(source['task'])
        tasks.append({**source, 'explicit_feasibility_cues': cues, 'suspected_public_leaks': public_leaks,
            'review_pin_matches': pin_ok, 'calibration_source_archive_matches': archive_matches,
            'private_reference_specs': len(list((task / 'solutions').glob('*/expect.json'))),
            'pilot_reference_note': 'Pilot uses the separate ten-case delivery-profile test.' if source['task'] in
                ('h7-fin-period-close', 'h7-ops-generation-restore') else None})
    if status['validated_tasks'] != 20:
        problems.append('Fewer than twenty validated tasks')
    if not all(status['numerical_gates'].values()):
        problems.append('Calibration gates not complete')
    return {'at': status['at'], 'passed': not problems, 'problems': problems,
            'historical_files_checked': len(old), 'historical_mismatches': historical_mismatches,
            'tasks': tasks, 'numerical_gates': status['numerical_gates'],
            'manual_fairness_review_still_required': True,
            'note': 'A source scan supplements author proof and actual grader reference checks; it does not establish semantic fairness by itself.'}


if __name__ == '__main__':
    result = audit()
    (ROOT / 'heldout7/FINAL_AUDIT.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'tasks'}, indent=2))
    if '--require-ready' in sys.argv and not result['passed']:
        raise SystemExit(1)
