"""Freeze reviewed Round 4 evidence; this is not a grader or inference runner."""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from beambench.tasks import load_task, task_hash, grader_hash


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert git('branch', '--show-current') == 'blind-round-4'
    assert not git('status', '--porcelain'), 'Commit reviewed source and reports before freezing'
    held = ROOT / 'heldout4'
    assert not (held / 'FROZEN.md').exists(), 'Never overwrite a frozen slate'
    assert not (held / 'FREEZE_MANIFEST.json').exists()
    acceptance = json.loads((held / 'ACCEPTANCE.json').read_text())
    calibration = json.loads((held / 'CALIBRATION.json').read_text())
    by_run = {r['run']: r for r in calibration}
    accepted = acceptance['accepted']
    assert accepted, 'Nothing accepted'
    tasks = []
    for row in acceptance['tasks']:
        spec = load_task(held / row['id'])
        assert row['task_hash'] == task_hash(spec)
        assert row['grader_hash'] == grader_hash(spec)
        if row['id'] not in accepted:
            continue
        assert row['strong_runs'] and row['weak_runs']
        for run in row['strong_runs'] + row['weak_runs']:
            r = by_run[run]
            assert r['current_versions'] and r['grade_available'] and r['scored']
            assert r['task_hash'] == row['task_hash'] and r['grader_hash'] == row['grader_hash']
        assert all(by_run[r]['verified_success'] and by_run[r]['said_and_done'] for r in row['strong_runs'])
        assert all(by_run[r]['verified_success'] is False for r in row['weak_runs'])
        tasks.append(row)
    paths = git('ls-files', '--', 'heldout4', 'tests/test_task_h4*.py').splitlines()
    file_hashes = {p: digest(ROOT / p) for p in sorted(paths)}
    for row in tasks:
        prefix = 'heldout4/' + row['id'] + '/'
        hashes = {p: h for p, h in file_hashes.items() if p.startswith(prefix)}
        row['full_bundle_sha256'] = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        row['full_bundle_file_count'] = len(hashes)
    harness_paths = ['beambench/' + name + '.py' for name in ['tasks', 'grading', 'runner', 'neutral', 'container', 'codex', 'outcomes']]
    raw_evidence = {}
    for run_dir in sorted((ROOT / 'runs/calibration-h4').iterdir()):
        if not run_dir.is_dir() or not (run_dir / 'record.json').exists():
            continue
        candidates = [run_dir / name for name in ['record.json', 'snapshot.tar.gz', 'codex.jsonl', 'trace.jsonl', 'telemetry.jsonl', 'turns.jsonl']] + list(run_dir.glob('grade*.json'))
        for path in candidates:
            if path.is_file():
                raw_evidence[str(path.relative_to(ROOT))] = digest(path)
    frozen_at = datetime.now(timezone.utc).isoformat()
    source_commit = git('rev-parse', 'HEAD')
    manifest = {
        'schema_version': 1,
        'frozen_at_utc': frozen_at,
        'branch': 'blind-round-4',
        'source_commit': source_commit,
        'criterion': acceptance['criterion'],
        'fallback_used': False,
        'accepted': accepted,
        'excluded': acceptance['excluded'],
        'expected_complete': sum(r['expected_status'] == 'complete' for r in tasks),
        'expected_blocked': sum(r['expected_status'] == 'blocked' for r in tasks),
        'tasks': tasks,
        'source_file_sha256': file_hashes,
        'permitted_harness_file_sha256': {p: digest(ROOT / p) for p in harness_paths},
        'model_configuration': json.loads((held / 'MODEL_CONFIGS.json').read_text()),
        'validation': json.loads((held / 'VALIDATION.json').read_text()),
        'raw_evidence_directory': 'runs/calibration-h4',
        'raw_evidence_committed': False,
        'raw_evidence_sha256': raw_evidence,
        'blindness_disclosure': 'Limited exposure to high-level scaffold-option descriptions through CLI help; no scaffold implementation or prompt source opened. See BLINDNESS.md.',
        'beam_or_mirror_runs': 0,
        'shared_image_rebuilds': 0,
        'hash_notes': 'task_hash and grader_hash use the unchanged existing harness functions. full_bundle_sha256 hashes the canonical compact JSON mapping of tracked task-relative-to-repository file paths to SHA-256; source_file_sha256 additionally covers references, tests, reports and helpers. Freeze files are excluded to avoid self-reference. The source commit precedes the manifest-only commit.',
    }
    (held / 'FREEZE_MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    text = f'''# Blind Round 4 — frozen

Frozen at **{frozen_at}** from source commit **{source_commit}** on branch **blind-round-4**.

Accepted: **{len(tasks)} tasks**, comprising **{manifest['expected_complete']} complete** and **{manifest['expected_blocked']} blocked**. Every selected current-version Astra run achieved verified success and said_and_done; every selected current-version DeepSeek V3 screen failed verified success. The exceptional 95%/5% fallback was not used.

This file and [FREEZE_MANIFEST.json](FREEZE_MANIFEST.json) form a manifest-only follow-up commit. No task, grader, test, helper, or report may change after this freeze. The manifest records exact task and grader hashes, every tracked Round 4 source file's SHA-256, reference/test integrity, configurations, selected run IDs, validation, historical run IDs, and checksums of the local raw run evidence.

**Blindness limitation:** CLI help exposed high-level scaffold-option descriptions to an audit agent, which stopped and was excluded from design; the coordinator received the disclosure. No scaffold implementation or prompt source was opened. See [BLINDNESS.md](BLINDNESS.md). No Beam or Mirror evaluation was run.

[REPORT.md](REPORT.md) records all outcomes, revisions, costs and limitations. The reported DeepSeek success on procurement revision 2 and ambiguity-affected Astra failures remain preserved. Local scrubbed transcripts and snapshots are retained in `runs/calibration-h4`; preserve that directory before removing the worktree.

| Accepted task | Expected | Content hash | Grader hash |
| --- | --- | --- | --- |
'''
    for row in tasks:
        text += f"| {row['id']} | {row['expected_status']} | `{row['task_hash']}` | `{row['grader_hash']}` |\n"
    text += '\nExcluded tasks: ' + (', '.join(acceptance['excluded']) or 'none') + '.\n'
    (held / 'FROZEN.md').write_text(text)
    print(json.dumps({'frozen_at_utc': frozen_at, 'source_commit': source_commit, 'accepted': len(tasks), 'excluded': acceptance['excluded'], 'hashed_files': len(file_hashes)}))


if __name__ == '__main__':
    main()
