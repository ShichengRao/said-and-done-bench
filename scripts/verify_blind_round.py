"""Check a frozen blind round against its own FREEZE_MANIFEST.json, before its runs and again at later merges.

  uv run python scripts/verify_blind_round.py heldout4 [heldout5 ...]

For each round: every task's task and grader hashes, every source file's sha256, and the calibration criterion
(each accepted task has a verified success from the strong anchor and none from the weak one). Reads only the round's
own files. Exits non-zero on any mismatch.
"""

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from beambench.tasks import grader_hash, load_task, task_hash  # noqa: E402


def check(folder: Path) -> list[str]:
  manifest = json.loads((folder / 'FREEZE_MANIFEST.json').read_text())
  problems = []
  # Round 4 lists the accepted tasks and each one's strong and weak verified counts; rounds 5 and 6 accept every task in
  # the manifest (by `task`, not `id`) and keep each model's counts under `models` (astra the strong anchor, deepseek-v3
  # the weak one). A later round with another strong anchor names it in `strong_anchor`.
  strong_key = manifest.get('strong_anchor', 'astra')
  ident = lambda row: row.get('id') or row['task']  # noqa: E731
  accepted = set(manifest['accepted']) if 'accepted' in manifest else {ident(row) for row in manifest['tasks']}
  for row in manifest['tasks']:
    task = ident(row)
    spec = load_task(folder / task)
    if task_hash(spec) != row['task_hash']:
      problems.append(f'{task}: task hash changed')
    if grader_hash(spec) != row['grader_hash']:
      problems.append(f'{task}: grader hash changed')
    if 'models' in row:
      strong, weak = row['models'][strong_key]['verified_success'], row['models']['deepseek-v3']['verified_success']
    else:
      strong, weak = row['strong_verified'], row['weak_verified']
    if task in accepted and not (strong >= 1 and weak == 0):
      problems.append(f"{task}: accepted but fails calibration ({strong} strong, {weak} weak)")
  # A published copy may have had a local path replaced (scripts/make_public_snapshot.sh): PATH_SCRUB.json records each
  # such file's frozen and published sha256.
  published = json.loads((folder / 'PATH_SCRUB.json').read_text()) if (folder / 'PATH_SCRUB.json').exists() else {}
  scrub, omitted = published.get('files', {}), published.get('omitted', {})
  for path, digest in manifest['source_file_sha256'].items():
    file = REPO / path
    if not file.exists():
      if omitted.get(path) != digest:  # A compiled cache the published copy leaves out is listed with its digest.
        problems.append(f'{path}: missing')
      continue
    found = hashlib.sha256(file.read_bytes()).hexdigest()
    if found != digest and not (scrub.get(path, {}).get('manifest_sha256') == digest
                                and scrub[path]['published_sha256'] == found):
      problems.append(f'{path}: content changed')
  print(f"{folder.name}: {len(manifest['tasks'])} tasks ({len(accepted)} accepted, {len(manifest.get('excluded', []))} excluded), "
        f"{len(manifest['source_file_sha256'])} source files, frozen {manifest['frozen_at_utc']}: "
        f"{'OK' if not problems else f'{len(problems)} problems'}")
  return problems


def main() -> int:
  problems = [problem for name in sys.argv[1:] for problem in check(REPO / name)]
  for problem in problems:
    print('  ' + problem)
  return 1 if problems else 0


if __name__ == '__main__':
  sys.exit(main())
